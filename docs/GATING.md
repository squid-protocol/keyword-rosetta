# The Self-Improvement Gate

How a number gets into (or changed in) an `expected_signals.json` manifest. Modeled
deliberately on GitGalaxy's tri-comparison system (`docs/self_scan/tri_comparison_README.md`
in the gitgalaxy repo): no raw number is ever trusted just because a tool printed it, and no
deviation is ever baked into a baseline without a recorded, human-checkable verdict.

## The core rule

**A manifest may only encode numbers whose every deviation from planted intent has a
`status: "validated"` entry in `deviation_ledger.json`.** "Deviation from planted intent"
means: the observed count differs from what the SPEC's probe table says was planted —
an overlap, a decoy that counted, an engine adjustment, anything. A deviation nobody can
explain is a stop-and-investigate, possibly a real engine bug — never bless it.

This is the same bar `tri_comparison_ledger.py`'s `has_open_question()` enforces for chart
badges: verified means someone (human, or an agent standing in for one) read the actual
evidence and recorded *why*, not that the numbers looked plausible.

## Ledger entry lifecycle (mirrors the tri-comparison ledger)

One entry per **deviation shape** (signal / cause / which languages exhibit it), not per
occurrence — a shape appearing in 30 languages is one systematic cause, not 30 findings.

1. **Born `unvalidated`** the moment a `--report` run shows a delta the author can't
   immediately tie to an existing validated shape.
2. **Investigated**: read the real source + the relevant engine rule/code path; a micro-repro
   (two minimal files differing only in the suspected cause, scanned for real) is the
   preferred evidence form — see the entries below for two worked examples.
3. **Validated** with a free-text `verdict` and a `disposition`:
   - `engine-semantic` — deliberate GitGalaxy behavior; bake into manifests, document in
     SPEC.md "Engine facts".
   - `keyword-overlap` — two rules legitimately match the same token; bake in, note in
     manifest.
   - `upstream-bug` (or `upstream-question`) — file a gitgalaxy issue, record its number,
     bake the *current* behavior in (the corpus measures what the engine does, not what it
     should do).
4. **When an upstream fix lands**: the affected manifests change in the same PR that flips
   the entry's `still_reproduces` to `false` — never delete the entry, never flip
   `still_reproduces` by hand without a fresh verifying scan. This is the "self-improvement"
   loop: corpus finds → issue filed → engine fixed → corpus re-baselined, with the ledger
   as the audit trail connecting all three.

## What gates on the ledger

- **Per-language PRs** (the fan-out): the generating model must cite, in the manifest
  `notes` and/or decoy `outcome` fields, which ledger entries cover its deviations. A PR
  introducing an unexplained delta is rejected by review even if `verify_language.py`
  passes — passing only proves internal consistency, not that the numbers were understood.
- **Manifest edits**: any diff to an existing `expected_signals.json` must reference the
  ledger entry (new or updated) that justifies it — exactly the golden-master re-bless
  discipline from gitgalaxy's Differential Scan protocol, scaled down.
- **The bias report**: `tools/bias_report.py` output is only meaningful over languages whose
  manifests are fully gated; a language with open `unvalidated` entries is flagged in the
  report rather than silently included.

## Relationship to gitgalaxy's own gates

This corpus is inside gitgalaxy's CI: its `rosetta-audit` check runs `verify_language.py`
across every folder here (at this repo's `main`) against each engine PR's build, and reports
which languages that build moves — modelled on gitgalaxy's tri-comparison audit, and like it
advisory and baseline-gated. An engine PR that changes corpus-observed counts merges first;
the manifests + ledger here are re-blessed against engine main afterwards. See "Cross-repo
flow" below.

## Working a per-language tracking issue

The end-to-end workflow for sweeping one language's deviations (gitgalaxy epic #2560's
per-language children) — classification taxonomy, engine-vs-corpus fix routing, the ledger
and re-baseline steps above, cross-repo PR ordering, and close-out — is packaged as the
`rosetta-language-sweep` skill (`.claude/skills/rosetta-language-sweep/SKILL.md`).
`tools/language_deviations.py <lang>` prints the live vs-median band table it triages from.
The first full sweep (jcl: issue #2581 → gitgalaxy#2610 + this repo's PR #4) is the worked
example, and gitgalaxy's `docs/language_status/jcl.md` §10 is its capstone write-up.

## n/a (incomparable) semantics

A signal whose rule is `None`/absent in the language's `LANGUAGE_DEFINITIONS` entry can never
be reported nonzero by the engine — a measured 0 there means "**not expressible as measured**",
not "the engine found nothing". The bias tooling (`bias_report.py`, the chart,
`findings_report.py`, `language_deviations.py`) renders those cells **n/a**: excluded from
medians, deviation bands, and consistency scores, never counted as −100% divergence. (`api` is
exempt from this inference: the orphan-conversion mechanism synthesizes `api` even where no
rule exists — see ledger `api-contextual-baseline-fix`.)

**Filling a `None` rule flips the cell to comparable — plan the corpus edit with it.** Because
n/a rests on rule *absence*, an engine PR that adds the missing rule ends the exemption whether
or not the corpus has anything for it to match. If the shell plants no instance of the new
idiom, the cell resolves to a measured `0` and is scored against the median like any other
number — turning a documented incomparability into a fresh red cell. Filed engine issues of the
"missing rule" shape (gitgalaxy#2644 yacc `class_start`, #2645 html `high_risk_execution`,
#2646/#2647 yaml `ownership`/`cleanup`) are therefore **paired work**: the rule and the plant
land together, or the rule waits. Before assuming a rule addition is corpus-inert, grep
`data/<lang>/` for the idiom it matches — on 2026-09-02 all four of the above would have
manufactured red cells, because the corpus contains no `%union`, no `srcdoc`, no `author:` and
no teardown verb.

Two hard rules keep n/a from becoming a rug:

1. **n/a is mechanical, correctness is not.** The n/a marker only states what the registry
   says today. Whether the absence is *right* is a bucket-2 question in the
   `rosetta-language-sweep` skill — jcl's `safety` rule was `None` until gitgalaxy#2610 proved
   JCL has real error-handling morphology (`COND=`). An absence is either real morphology
   (→ ledger it) or a missing-rule engine gap (→ file it); it is never simply fine.
2. **Unreviewed absences stay loud.** An n/a cell with no validated ledger entry naming that
   language AND that signal (the entry's `signal` field is a `|`-separated list) is rendered
   with a warning marker (†/⚠) in every report, and `language_deviations.py` exits nonzero on
   it. The worked example of "reviewed": `jcl-2610-rebaseline-residual-morphology` covers
   jcl's `cleanup|doc|test|globals` with the reasoning for each.

### Derived metrics (the `risk_*` columns)

The rule above governs *planted signals*. The `risk_*` columns are one step downstream —
formulas over those same signals — and until now had no n/a mechanism at all, so a language
whose every input was structurally absent was scored as a −100% outlier against languages
that actually measured something. (markdown defines **no** rules whatsoever; it was red on
every risk column for having nothing to measure.)

A derived metric is n/a for a language only when **all four** hold:

1. its formula consumes at least one registry-governed signal;
2. every one of those signals has a `None` rule for that language;
3. it consumes no engine-derived input — `orphaned_logic`, `duplicate_logic`, the `sec_*`
   family — that can be nonzero no matter what the registry says;
4. the scan confirms the observed value really is **0**.

Condition 4 is not decoration. Rule absence alone is *not* sufficient for a derived metric,
because these formulas also read structure the registry does not govern: LOC, doc lines, the
call graph, popularity. Two live cells prove it — `jcl/risk_api_exposure` = 8.67 and
`html/risk_verification` = 0.92 both have every registry input absent and still measure
something. Those are reported as **mismatches** and left comparable, never absorbed: a
mismatch means either the dependency map is incomplete or the engine synthesizes the input
downstream of the registry, the way orphan conversion synthesizes `api` (ledger
`api-contextual-baseline-fix`).

The dependency map is **derived live** from the engine's risk assembly
(`gitgalaxy/metrics/signal_processor.py`), never hand-copied — same doctrine as the registry
loader. If the assembly stops looking the way the parser expects, `risk_dependencies()`
raises rather than returning a stale map that would quietly mark comparable cells n/a.

**Review status is inherited, not invented.** A derived n/a is a mechanical consequence of
its inputs' absences, so it counts as ledgered only when *every* governed input is itself
ledgered for that language; one unreviewed input keeps the derived cell marked `n/a†` too.
That is rule 2 above, composed — and it means `na_check.py` audits the planted 18 plus the
non-planted inputs those formulas read (`concurrency`, `encapsulation`, `sync_locks`,
`dead_code`, `spec_exposure`, `immutability_locks`, `reflection_metaprogramming`), a scope
the #2560 sweep never covered. Inputs to formulas that condition 3 already disqualifies are
excluded on purpose: demanding a ledger entry for `llm_api` in the 40 languages that do not
define it would be review theatre, not review.

The `api` exemption gets one extra turn here. `api` stays out of the *planted signal* n/a
table (rule-absence does not make it unmeasurable — orphan conversion synthesizes it), but it
is a governed input to `risk_api_exposure` and `risk_documentation`, so a derived cell can
rest its n/a on it. Those absences are therefore audited (`markdown/api`, `jcl/api`) even
though they never appear as n/a signals: otherwise the derived cell is marked `n/a†` with
nothing in the baseline to explain the marker, and the reviewer has no row to chase.

## Inert metrics

A metric that records exactly 0 in **every** language is not 100% consistent — it asked no
cross-language question. `risk_churn` (a hardcoded `0.0` in the risk assembly) and
`risk_secrets_risk` (needs `sec_*` signals no corpus shell plants) were both being badged
100% and folded into the headline average, inflating it. They are now reported as **inert**
and excluded from the average, alongside the separate "no comparable median" list.

## Program length is context (gitgalaxy#2669 F.1)

Six columns — `total_loc`, `coding_loc`, `token_mass`, `keyword_hits`, and the two that are
length by definition, `avg_func_loc` (lines per function, over a planted 13) and
`comment_lines` (documentation *lines*, where the SPEC plants markers) — measure how long a
language's 12-probe program came out. The SPEC plants counts, never length: a Dockerfile with
the same 12 probes cannot be as long as the Java version without padding, and padding would
move the planted signals. On 2026-09-04 every procedural language sat within a few percent of
the `coding_loc` median, and the out-of-band tail was exactly the non-procedural shells
(markdown, m4, yacc, jcl, css, html, dockerfile, makefile, yaml, sqlite) plus the two dense
ones (haskell, scheme): 49 cells with no honest fix on either side.

The test for membership: *would a perfect engine give the same value for the same program at
two lengths?* If no by definition, the metric is size and belongs here. If yes but the engine
does not (`control_flow_ratio`, `func_internal_density`, `structural_mass`, `cog_raw`), it
stays gated — its spread is an engine finding (gitgalaxy#2705), and demoting it would hide one.

The bias tooling therefore treats them as **context**: reported and charted, no badge, no share
in the consistency average, no verdict, never counted by `--gate`. Two consequences:

- A context column that is out of band for a language may still explain a `derived` cell there
  (`derived: inherits coding_loc`) — that is a deviation entering through length. A ledger
  entry saying "this program is shorter" is **not** a valid explanation for any cell and must
  not be written; the length itself is already accounted for by being context.
- `coding_loc` is the x-axis of the report's **length-leak check**: for each derived metric,
  across the languages whose measured inputs are all in band (content held equal) *and* that
  share the engine's strictness stratum (gitgalaxy#2653/#2718's Irc/Ot constants — the
  high-gap languages are largely the short shells, so a strictness effect would otherwise read
  as a length effect), the rank correlation against `coding_loc`. A leak (|rho| ≥ 0.6 over ≥ 8
  languages) is one finding on one engine formula — the same program at 46 lengths should
  score the same — filed as an engine design issue in the gitgalaxy#2655 shape. It never
  alters a cell's verdict. The stratum map is read off `analysis_lens.strictness_constants` at
  regen time and stored as `strata` in `docs/bias_data.json`.

## The language-level constant is design; unplanted inputs are not signals (gitgalaxy#2669 F.3)

`analysis_lens.LANGUAGE_STRICTNESS` gives every language four yes/no columns (static types,
enforced errors, memory safety, no implicit globals) and `strictness_constants()` turns the
count of `False` columns into the constants the risk formulas read: `Irc` = gaps, `Ot` =
1 + 0.1 × gaps. Wiki 08-03 documents this as deliberate (gitgalaxy#2653, implemented by
#2718 — which deleted the three hand-listed scoring tiers this section used to describe;
`signal_processor._get_tier` no longer exists). Against a global median it reads as bias:
languages sharing a gap count report identical risk values with inputs identical to the median
language. The report therefore bands each **constant-reading** risk metric against **the median
of its own strictness stratum**, prints the per-stratum medians as the documented offset, and
stores the stratum map (`strata`, keyed `irc0`…`irc4`) and the metric list
(`constant_sensitive`) in `docs/bias_data.json`. Which metrics read a constant is taken off the
engine source at regen time (`_registry.risk_dependencies` records `reads_constant`), never
hand-listed. A ledger entry that says "this language is loosely typed" is not a valid
explanation for any cell; the constant is already accounted for by the reference median.

**Not held equal:** the per-language × per-signal fidelity coefficients
(`gitgalaxy/standards/fidelity_table.py`), which replaced the scalar `Fc` in #2718, are
*generated from this corpus*. Banding against them would be circular — a defence-credit
deviation that survives banding may still be a fidelity cell, and the report says so.

The risk formulas also read registry signals the SPEC never plants (`immutability_locks`,
`concurrency`, `sync_locks`, `reflection_metaprogramming`, `debug_prints`, `spec_exposure`,
`llm_api`, `dead_code`). A shell that idiomatically writes `val`/`let`/`final` carries freeze
hits a `var` shell does not, and `risk_state_flux` then differs with `state_mutation` on plant.
Those signals are cached as an **ungated** group (`unplanted_inputs`; the full reported-but-
never-gated set is `ungated_metrics`): an out-of-band cell there gets no verdict, but a derived
risk cell may inherit from it and say so (`derived: inherits immutability_locks`). That is the
honest reading — the cause is named, and the corpus can decide whether to plant the signal
everywhere or write it out of the shell — and it is not a licence to ignore the group: an
unplanted signal that fires where it should not is still a rule question for the language's
tracking issue. `risk_stability` and `risk_churn` read commit age, not content, and sit in the
same ungated set as temporal context.

## Cross-repo flow (no pins)

Two CI checks hold the corpus and the engine together, symmetrically and without pins
(gitgalaxy#2557, simplified by gitgalaxy#2682):

- **This repo's `verify.yml`** checks out the engine at **`main`** and runs the gates for the
  languages a PR touches (all of them for a tools/SPEC change or a dispatch).
- **gitgalaxy's `rosetta-audit.yml`** checks out THIS repo at **`main`** and runs every gate
  against the engine PR's build, then re-runs anything that failed against engine main. A
  language that fails on both is *pre-existing drift* (this corpus has not caught up yet) and
  is a notice; one that fails only on the PR is a *regression* that PR introduces.

Neither repo requires a status check to merge; both checks are advisory. That is what makes
the flow a straight line:

1. **Engine PR `N` merges first.** Its `rosetta-audit` names the languages it moves. If that is
   intended, the author adds the `rosetta:rebless-owed` label (regressions become warnings)
   and merges. Nothing in this repo is edited beforehand.
2. **Corpus re-bless PR here, against engine main:** manifests + ledger per step 4 of the
   lifecycle above. `verify.yml` is green by construction once the numbers are right.
3. **Merge it.** `bias-history.yml` regenerates the report, chart, cache and findings doc and
   commits them; nothing to pin, nothing to reset.

Between steps 1 and 2, `bias-history.yml` (daily, and on every corpus push) keeps one issue,
*"corpus owes a re-bless against engine main"*, open with the failing languages. Unrelated
engine PRs stay green during that window because their audit classifies the drift as
pre-existing.

**What was retired, and why.** Until 2026-09-03 this repo carried a committed `ENGINE_REF`
file pointing `verify.yml` at an engine ref, and gitgalaxy pinned this repo by a
`KEYWORD_ROSETTA_REF` SHA variable. The two pins pointed at each other: the corpus PR needed
`ENGINE_REF=pull/N/head` to pass, had to be back on `main` before merging, and then failed
against `main` because the engine PR was not in it yet, while the engine PR waited for a
corpus SHA that only existed after that merge. No ordering satisfied all three; in practice
the corpus merged with a knowingly wrong ref and owed a reset nothing enforced
(keyword-rosetta#39 was a PR whose only content was that reset). Both pins were only ever
making an advisory check green before a merge that happened anyway, so both are gone.

**Verifying against an unmerged engine PR** is still possible, as a run parameter rather than
a committed file: `gh workflow run verify.yml -f engine_ref=pull/<N>/head` (or locally, point
`GALAXYSCOPE_BIN` at that branch's build). There is nothing to reset afterwards.

`tools/na_check.py` is the n/a governance gate (see "n/a semantics" above): baseline-gated on
`docs/na_baseline.json`, it fails only on NEW unreviewed rule absences. Shrink the baseline with
`--regenerate` after reviewing cells; never regenerate to absorb a new one unreviewed.
