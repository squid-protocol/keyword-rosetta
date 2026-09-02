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
   but this repo's CI checks out gitgalaxy **main**. A corpus PR that depends on unmerged
   engine rules stays **draft**, with its body naming the engine PR, until that PR merges;
   then `gh run rerun <run-id> --failed` + `gh pr ready`.
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

## Tools & skills

- `tools/verify_language.py <lang> [--report]` — the per-language gate.
- `tools/language_deviations.py <lang>` — vs-median band table from the cached
  `docs/bias_data.json` (run `tools/bias_report.py` to refresh the cache; it rescans all 46
  languages and regenerates the report/chart/findings docs).
- Skills live in `.claude/skills/` (`.agents/skills` is a symlink to the same directory):
  **`rosetta-language-sweep`** — the end-to-end workflow for working one language's
  cross-language-consistency tracking issue (gitgalaxy epic #2560's children), including the
  five-cause deviation taxonomy and the cross-repo choreography above.

Env: `GALAXYSCOPE_BIN=<gitgalaxy>/.crucible_venvs/full_precision/bin/galaxyscope`,
`GITGALAXY_PATH` for the registry loader (defaults to the sibling checkout). The
`zero_dependency` venv exists for degraded-engine investigation only — never for
regenerating the report (hard rule 6).

## What the bias report scores

Three groups, all of them "the same program in 46 languages — does the engine describe it
the same way?": the planted signals (SPEC probe table), the `risk_*` formulas over them, and
the **engine measures** (topology, size, shape, function morphology). Non-planted signal
columns (`pointers`, `macros`, `generics`, the `sec_*` family, ...) are deliberately excluded:
the SPEC plants no intent for them, so a C-vs-Python divergence there is language expression,
not measurement bias. To make one comparable, plant it in `SPEC.md` and add it to `PLANTED` —
never score it unplanted.

Metrics are scored two ways. A positive median scores on the ±25% band; a **zero** median
scores on *exact agreement* (marked `‖`), because a relative deviation against zero is
undefined — that is what keeps `class_start`, `classes_found`, `risk_concurrency` and
`risk_dead_code` in the report instead of silently dropped. A metric that records 0 in every
language is **inert**, excluded from the average entirely: it asked no question, so scoring it
100% would only inflate the headline.
