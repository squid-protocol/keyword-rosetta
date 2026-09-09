# AGENTS.md — keyword-rosetta

Vendor-neutral guidance for any coding agent (Claude, Antigravity/Gemini, ...) working in this
repo. Repo-specific rules live here; the multi-repo picture lives in the gitgalaxy engine repo's
**`docs/ecosystem.md`** (canonical constellation map: every sibling repo's purpose, the skills
inventory, cross-repo workflow merge ordering, and PR conventions). Read that before cross-repo
work; don't duplicate it here.

## What this repo is

The GitGalaxy **control corpus**: one identical 12-probe program shell authored in all 46
signature-bearing languages, with exact planted signal-keyword counts, so the engine's
extraction can be checked for cross-language equivalence and its risk scores for language bias.
`SPEC.md` is the authoring contract; `docs/GATING.md` governs how any number gets into (or
changed in) an `expected_signals.json` manifest — **no deviation is ever baked in without a
`status: "validated"` entry in `deviation_ledger.json`**.

## Hard rules

1. **Commit before verifying.** GalaxyScope's census walks git-tracked files only — an
   uncommitted shell edit silently verifies the OLD content.
2. **Never bless an unexplained number.** `tools/verify_language.py <lang> --report` first;
   every delta from planted intent gets accounted (overlap? decoy surface? engine semantic?
   engine bug?) before the manifest changes. An unexplainable delta is a stop-and-investigate.
3. **Manifest edits require a ledger entry** (new or updated) justifying them — GATING.md's
   core rule.
4. **Engine version matters.** Tools run whatever `GALAXYSCOPE_BIN` points at (default: the
   sibling gitgalaxy checkout's venv, an editable install of that checkout's current branch) —
   but this repo's CI always checks out the engine at **`main`**, and gitgalaxy's `rosetta-audit`
   always checks out this repo at **`main`**; there is no pin in either direction (gitgalaxy#2682).
   So a corpus PR that re-blesses after an engine change opens **after** that engine PR merges,
   and is green by construction. See `docs/GATING.md`'s "Cross-repo flow". To verify against an
   unmerged engine PR in CI, dispatch `verify.yml` with `engine_ref=pull/<N>/head` — a run
   parameter, nothing committed, nothing to reset.

   **Two things resolve the engine and they must agree.** `GITGALAXY_PATH` supplies the
   registry a tool imports; `GALAXYSCOPE_BIN` is a separate binary whose editable install points
   at whatever checkout created it. Point them at different trees and a report reads one
   engine's rules over another engine's measurements, silently — on 2026-09-07 that turned 6
   unexplained cells into 32 and a 1.5% open-defect share into 2.5%, with nothing in the output
   saying why. `bias_report.py` now checks this before the first scan and aborts (override:
   `--allow-engine-mismatch`), and stamps `engine_commit` into `docs/bias_data.json` so the
   artifact records WHICH engine produced it, not just how it was built. When measuring a
   worktree, put it on `PYTHONPATH` so it shadows the binary's editable install:

   ```sh
   PYTHONPATH=<worktree> GITGALAXY_PATH=<worktree> \
       GALAXYSCOPE_BIN=<gitgalaxy>/.crucible_venvs/full_precision/bin/galaxyscope \
       python tools/bias_report.py
   ```
5. **Cross-repo PRs carry a "Cross-repo" note** (companion PR links, merge order, what re-runs
   after) — see the ecosystem doc's PR convention.
6. **Always regenerate the bias report at full precision.** In Zero-Dependency Mode (any of
   networkx / tiktoken / numpy / pandas / xgboost / pyyaml missing) the recorder nulls every
   network metric, so pagerank, blast radius, betweenness, closeness and producer ratio drop
   out of the comparison with no error and no note — two reports then differ by five whole
   columns for reasons nothing in them explains. Three things enforce it now, so it cannot
   happen by accident: `bias_report.py` reads the mode from the scan DB and **aborts** unless
   it is full precision (`--allow-zero-dependency` to override on purpose), the mode is
   stamped in the report header and recorded as `engine_mode` in `docs/bias_data.json`, and
   `verify.yml` fails any PR whose committed cache says anything but `full-precision`.

   ```sh
   GALAXYSCOPE_BIN=<gitgalaxy>/.crucible_venvs/full_precision/bin/galaxyscope \
       GITGALAXY_PATH=<gitgalaxy> python tools/bias_report.py
   ```

   You no longer have to ship the regenerated artifacts in a corpus PR: `bias-history.yml`
   regenerates them at full precision against engine main after every push to main (and daily),
   commits them, and keeps the *"corpus owes a re-bless against engine main"* issue in sync.
   Regenerate locally when you want to see the effect before merging, not because CI needs it.

7. **A green corpus does NOT mean a green engine golden master.** These are two different
   corpora asking two different questions. This repo's manifests pin what the engine measures
   on a *planted* 12-probe shell; gitgalaxy's `tests/golden_master_*.json` pin what it measures
   on ~80 *real* repositories. An engine fix routinely holds every planted value here while
   rewriting hundreds of golden-master entries there — a rule that only ever fired on real-world
   syntax the shell doesn't contain moves nothing here and plenty there. "`verify_language.py`
   PASS" is therefore never evidence that an engine PR needs no bless. Check both, and say which
   one you checked.

8. **Adding a missing rule is a corpus-visible change, even though it adds no keyword.**
   `docs/GATING.md`'s n/a semantics make a cell incomparable *because its rule is `None`*. The
   moment a rule exists, the cell becomes comparable — and if the corpus plants nothing that
   the new rule matches, it lands as a measured **0**, which against a positive median is a
   fresh red cell. So an engine PR that fills a `None` rule must ship with a corpus PR planting
   the idiom, or it converts an honest n/a into a manufactured deviation. Check what the corpus
   actually contains before assuming a rule addition is inert (`grep` the `data/<lang>/` folder
   for the idiom the new rule matches).

9. **Measure over the language's whole file set, not just its canonical extension.** Several
   languages own more than one: groovy owns `.gradle` (and `Jenkinsfile`) as well as `.groovy`,
   and in the real-world crucible corpus the `.gradle` files are 40% of the sample. A
   before/after count taken over one extension can be right in direction and wrong in
   magnitude — and a magnitude quoted in an issue is what the next session builds on.

## Tools & skills

- `tools/verify_language.py <lang> [--report]` — the per-language gate. `api` reads the
  engine's raw rule count (`raw_arch_api`), and `api_orphan_credit` pins the orphan→api
  conversion on its own (gitgalaxy#2729; docs/GATING.md "What `api` asserts").
- `tools/language_deviations.py <lang>` — vs-median band table from the cached
  `docs/bias_data.json` (run `tools/bias_report.py` to refresh the cache; it rescans all 46
  languages and regenerates the report/chart/findings docs).
- **An out-of-band cell is not automatically a defect** (gitgalaxy#2669 E.1). Both tools
  tag each red/amber cell with a verdict, and only `unexplained` counts as work remaining:
  - `ledgered` — a validated `deviation_ledger.json` entry names this language *and* this
    metric (its `signal` field is the `|`-joined list normalised in Batch A.4);
  - `undefined` — a per-function descriptor (`avg_func_*`, `max_func_complexity`,
    `func_complexity_gini`, `func_internal_density`) for a language with
    `functions_found = 0`; the quotient has no value, the same way `docs/GATING.md` treats
    a `None` rule as `n/a` rather than as a zero;
  - `derived` — a composite (`cog_raw`, `structural_mass`, `control_flow_ratio`, the
    per-function family) whose deviation entered through an input that is itself out of
    band, so counting it again is counting one finding twice. The metric→inputs table is
    `DERIVED_INPUTS` in `bias_report.py`, with the engine formula each row came from cited
    beside it — check it against the engine when a formula changes.
  - **context** (gitgalaxy#2669 F.1) — `total_loc`, `coding_loc`, `token_mass`, `keyword_hits`,
    `avg_func_loc` and `comment_lines` measure how long the program came out, which the SPEC
    never plants (test: a perfect engine would still give different values at different
    lengths; a metric that *should* be invariant stays gated — its spread is an engine finding). They
    are charted without a badge, excluded from the consistency average and from `--gate`,
    and never get a verdict of their own; a `derived` cell may still inherit from one. A
    ledger entry saying "this program is shorter" is not a valid explanation for any cell.
    `coding_loc` is also the x-axis of the report's **length-leak check**: a derived metric
    that rank-correlates with `coding_loc` (|rho| ≥ 0.6 over ≥ 8 languages) across languages
    whose measured inputs are all in band *and* that share the engine's strictness stratum
    (the #2653/#2718 constants would otherwise read as length — the map is `strata` in the
    cache, read off `analysis_lens.strictness_constants`) is reading length, not content — one engine
    finding per formula (`LENGTH_TERMS` cites where length enters), filed as an engine design
    issue in the #2655 shape, never used to change a cell's verdict.

  - **strictness stratum** (gitgalaxy#2669 F.3, re-pointed at #2718 by F.4) — the risk formulas
    that read a language-level constant (`constant_sensitive` in the cache, off the engine
    source) are banded against the median of their own strictness stratum (`strata`, `irc0`…
    `irc4` = the language's count of `False` strictness columns), and the per-stratum medians
    are printed as the documented offset (docs/GATING.md "The language-level constant is
    design"). Never ledger a cell as "this language is loose".
  - **unplanted inputs / temporal** — registry signals the risk formulas read but the SPEC never
    plants (`unplanted_inputs`), plus `risk_stability`/`risk_churn` (commit age), are reported
    but never gated (`ungated_metrics` is the full set every tool skips). A derived risk cell may
    inherit from one (`inherits immutability_locks`) — that names the cause; it does not close
    the question of whether the shell should be carrying that keyword.

  `tools/bias_report.py --gate` exits nonzero while any cell is unexplained: that is the
  epic close criterion, and it is off by default so a routine regen still writes its
  artifacts and exits 0. `language_deviations.py` fails per-language on the same basis.
- `tools/decoy_check.py [--gate]` — SPEC §Decoys 1: does each language's designated
  comment decoy (`main.<ext>`) actually assert anything? It scores the prose with the
  **comment marker stripped**, because a rule that fires only with the marker is
  comment-anchored (`dead_code`, `spec_exposure`, the debt family, `doc`, `ownership`) and
  is *supposed* to read comments — counting those let 67 of the corpus's 180 `decoy:` lines
  pass while asserting nothing about stripping (keyword-rosetta#73). `markdown` is the one
  entry in `EXEMPT`: every rule it defines is `lit_*`, so no comment could shield anything.
- `tools/issue_status.py <lang> [--post]` — the per-language tracking issue's status comment,
  generated from `bias_data.json` + the ledger with the same verdicts the gate uses, so an
  issue can never disagree with `bias_report.py --gate` about what is left. `--all --post`
  after each batch regen (gitgalaxy#2669 E.2); it resolves each issue by title search rather
  than storing a mapping that would go stale.
- `tools/ledger_orphan_check.py [--ci|--regenerate]` (keyword-rosetta#75) — the ledger-decay
  audit. A collective entry's `signal` union is read as the token×`languages_seen`
  cross-product; a token whose last out-of-band cell went green is an **orphan** excusing a
  dead cell nobody looks at, which the `_doc` rule forbids ("a token must hold for EVERY
  language listed"). Flags every token of a validated, **still-reproducing** entry that has a
  comparable cell but is in band on all of them, resolving `api`→`raw_arch_api` (the engine's own
  column map) and skipping retired entries (they excuse nothing since #81) plus n/a and ungated
  tokens. Scan-free — reuses `bias_report.out_of_band_cells`, so it can never
  disagree with the gate about which cells are out of band. Baseline-gated like `na_check.py`
  (`docs/orphan_token_baseline.json`, `--ci` fails only on NEW orphans); the report highlights
  **partial-decay** entries (some tokens dead while others still hold) as the scope-down
  candidates. `bias-history.yml` re-baselines it in lockstep with the cache, so engine drift
  re-baselines on its own and a PR's `--ci` only sees orphans the PR introduced.
- `tools/ledger_issue_check.py [--ci|--refresh|--regenerate]` — the ledger **issue-state**
  audit, the third on that pattern and the one axis the other two cannot see: whether the issue
  an entry blames is still open. Closing an issue on GitHub moves nothing by itself — the entry
  stays live and its cell keeps its disposition's colour — so an entry can go on reporting a
  defect somebody already fixed (the sweep that built this found 19). **Disposition-aware**: an
  `upstream-bug`/`upstream-question`/`engine-defect` entry citing a CLOSED issue fails the gate
  (the debt was paid → retire it, or declined → re-disposition it), while an
  `engine-semantic`/`intended-morphology` entry is *correct* to outlive an issue closed "by
  design" and is reported only. Audits fully-qualified `owner/repo#N` refs only — a bare `#N` in
  prose is ambiguous (`fixed by PR #2837`) — and marks an entry that is also decayed
  (`bias_report.decayed_entries`) as dead on both axes. `--refresh` is the only part that needs
  the network; `bias-history.yml` runs it daily into `docs/issue_states.json` and re-baselines
  in the same step, so the PR gate is scan-free, API-free, and only ever sees staleness the PR
  itself introduced.
- `tools/rebless.py <lang> --engine <worktree> --note "..." [--retire <id> --resolved-by
  <issue> --verdict "..."] [--add-keys k1,k2] [--dry-run]` (keyword-rosetta#113) — the
  scan/diff/apply/note/retire/re-verify loop a rebless PR does by hand, in one command.
  Applies only the cells that moved (never a blind overwrite), refuses to write a file that
  doesn't already round-trip under its committed formatting (manifest: `indent=2,
  ensure_ascii=False`; ledger: `ensure_ascii=True`) so a rebless diff is never reformatting
  noise, and exits with `verify_language.py`'s own status. `--dry-run` prints the diff and,
  with `--retire`, the ledger entry that would close, without writing anything.
- `tools/ledger_show.py <id> [--short] [--grep <text>]` — a condensed view of one ledger
  entry (id, signal, languages_seen, disposition, status, still_reproduces, upstream_issue,
  resolved_by, verdict head/tail) instead of reading the whole ~3 KB JSON object to check one
  field. `--grep <text>` without an id searches every entry's id/signal/verdict instead.
- `tools/open_rebless_pr.sh <gitgalaxy-issue-number> [--dry-run]` — given a merged engine
  issue, confirms engine `origin/main` actually carries a commit naming it, finds the pushed
  `rebless/<N>-*` / `replant/<N>-*` branch, and opens the PR with the standard body (a "what
  moved" table diffed straight from the branch's manifests against `origin/main`, the ledger
  ids it touched, a verification line, and the Cross-repo note rule 5 requires) — the step
  that has been leaving re-bless branches pushed but unopened.
- `--engine <worktree>` on `tools/verify_language.py` and `tools/screen_plant.py`
  (`_registry.apply_engine`) sets GALAXYSCOPE_BIN/GITGALAXY_PATH/PYTHONPATH together instead
  of the export recipe every rule-contract-audit session was hand-writing — that skill's
  Phase 2 told agents to bypass `screen_plant.py` with an inline rules loop for exactly this
  reason, no longer necessary.
- Skills live in `.claude/skills/` (`.agents/skills` is a symlink to the same directory):
  **`rosetta-language-sweep`** — the end-to-end workflow for working one language's
  cross-language-consistency tracking issue (gitgalaxy epic #2560's children), including the
  five-cause deviation taxonomy and the cross-repo flow above.

Env: `GALAXYSCOPE_BIN=<gitgalaxy>/.crucible_venvs/full_precision/bin/galaxyscope`,
`GITGALAXY_PATH` for the registry loader (defaults to the sibling checkout). The
`zero_dependency` venv exists for degraded-engine investigation only — never for
regenerating the report (hard rule 6).

## What the bias report scores

Four gated groups, in pipeline order, all of them "the same program in 46 languages — does the
engine describe it the same way?": **planted keyword signals** (SPEC probe table — the
extraction layer), **structure counts** (functions, classes, dependency edges, pagerank),
**shape descriptors** (per-function and graph measures derived from the signals), and **risk
scores** (the `risk_*` formulas, mean per file). Four more groups are reported but never gated —
**program length**, **vocabulary** (`control_flow_ratio`, `structural_mass`: token tallies that
measure how the language spells the program), **unplanted inputs** and **commit age**; see
`docs/GATING.md`. The chart (`docs/bias_variance_chart.svg`) orders rows best → worst inside each
group and prints each gated group's average. Non-planted signal
columns (`pointers`, `macros`, `generics`, the `sec_*` family, ...) are deliberately excluded:
the SPEC plants no intent for them, so a C-vs-Python divergence there is language expression,
not measurement bias. To make one comparable, plant it in `SPEC.md` and add it to `PLANTED` —
never score it unplanted.

Metrics are scored two ways. A positive median scores on the ±25% band; a **zero** median
scores on *exact agreement* (marked `‖` in the tables, `· exact` on the chart), because a relative deviation against zero is
undefined — that is what keeps `class_start`, `classes_found`, `risk_concurrency` and
`risk_dead_code` in the report instead of silently dropped. A metric that records 0 in every
language is **inert**, excluded from the average entirely: it asked no question, so scoring it
100% would only inflate the headline.
