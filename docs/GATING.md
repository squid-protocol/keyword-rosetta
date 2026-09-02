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

This corpus sits *outside* gitgalaxy's CI today. The eventual integration (issue #1096
Phase 5) is a pinned-tag arrangement like the language-crucible's `LANGUAGE_CRUCIBLE_REF`:
gitgalaxy CI runs `verify_language.py` across the corpus at a pinned tag, and an engine PR
that changes corpus-observed counts must update the manifests + ledger here (cross-repo,
same as `RELEASING.md` golden-master steps). Until then, the gate is enforced by review
discipline plus the verifier.

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

## Cross-repo choreography (ENGINE_REF + the gitgalaxy-side pin)

Two CI gates hold the corpus and the engine together (gitgalaxy#2557), asymmetrically pinned:

- **This repo's `verify.yml`** checks out the engine at the ref in the committed **`ENGINE_REF`**
  file — normally `main`. A corpus PR that depends on a not-yet-merged engine PR sets it to that
  PR's persistent ref (`pull/<N>/head`), so the gate runs against the right engine immediately —
  no draft-PR limbo, no post-merge rerun. Reset it to `main` before merging here (the engine PR
  should merge first; the reset is part of the same corpus PR's final state).
- **gitgalaxy's `rosetta-audit.yml`** checks out THIS repo at the pinned `KEYWORD_ROSETTA_REF`
  Actions variable and runs every language gate plus `tools/na_check.py --ci` against the engine
  PR's build — so an engine change that shifts corpus-observed counts, or removes a rule without
  a ledger entry, fails **at the source**, in the PR that caused it, not days later here.

The full flow for an intentional count-changing engine fix:

1. Engine PR `N` opens in gitgalaxy → its `rosetta-audit` fails (expected — that's the gate
   catching the drift at the source).
2. Corpus re-baseline PR here: manifests + ledger per this doc's step 4, `ENGINE_REF` set to
   `pull/N/head` → all gates green → flip `ENGINE_REF` back to `main` → merge (engine PR must
   merge before the reset lands... in practice: merge this PR with `main` restored once the
   engine PR is approved; the brief window where this repo's main floats ahead of engine main
   is covered by gitgalaxy's pinned gate).
3. Engine PR `N` bumps `KEYWORD_ROSETTA_REF` to this repo's new commit → `rosetta-audit` green
   → merge.

`tools/na_check.py` is the n/a governance gate (see "n/a semantics" above): baseline-gated on
`docs/na_baseline.json`, it fails only on NEW unreviewed rule absences. Shrink the baseline with
`--regenerate` after reviewing cells; never regenerate to absorb a new one unreviewed.
