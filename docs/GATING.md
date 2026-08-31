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
