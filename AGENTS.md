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
`GITGALAXY_PATH` for the registry loader (defaults to the sibling checkout).
