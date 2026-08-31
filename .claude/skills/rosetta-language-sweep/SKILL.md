---
name: rosetta-language-sweep
description: Work one language's rosetta cross-language-consistency tracking issue (gitgalaxy epic #2560's children #2561-#2607) end to end -- classify every out-of-band metric by cause, fix what is fixable (engine and/or corpus), ledger what is intended, re-baseline, regenerate the bias artifacts, and close out with the issue update and the gitgalaxy language-status capstone section. Use when the user says "work on <rosetta issue number>", "sweep <language>'s rosetta deviations", or a #2560 child issue is the task. Not for adding a NEW language to the corpus (that's SPEC.md's authoring workflow) or for tri-comparison accuracy work (gitgalaxy's tri-comparison-ledger-sweep).
---

A rosetta tracking issue lists a language's metrics that sit outside ±25%/±50% of the
46-language median on identical planted intent. The first full sweep (jcl, issue #2581 →
gitgalaxy#2610/PR#2611 + this repo's PR#4, 2026-08-31) proved the load-bearing insight: **the
red/amber list is not a work list — it is an unclassified mixture of five different causes, and
each cause has a different correct action.** Classifying first is the whole game; every hour of
that sweep's fixing was preceded by minutes of cheap classification, and the one real engine bug
it found (#2610: jcl `//*` comments never reached the comment surface, engine-wide) fell out of
asking "is this zero because the language lacks the concept, or because the engine can't see
it?" rather than pattern-matching "Tier-2 morphology" onto every zero.

## Prerequisites

- A gitgalaxy checkout (default sibling layout: `GITGALAXY_PATH`, see `tools/_registry.py`) and
  a working engine venv: `GALAXYSCOPE_BIN=<gitgalaxy>/.crucible_venvs/full_precision/bin/galaxyscope`.
- Know which engine build you are measuring. The verifier/bias tools run whatever
  `GALAXYSCOPE_BIN` points at (an editable install → that checkout's current branch), but this
  repo's CI checks out gitgalaxy **main** — see "Cross-repo choreography" before opening PRs.

## Phase 0 — read before triaging (all primary sources, no memory)

1. The tracking issue itself, and its section grouping: §1 structure → §2 signals → §3 risk.
   §3 is *downstream*; the epic forbids tuning risk formulas against biased inputs. Never
   start in §3.
2. `python tools/language_deviations.py <lang>` — the live vs-median band table (reads the
   cached `docs/bias_data.json`; run `tools/bias_report.py` first if the cache predates the
   engine/corpus state you're triaging). Its red/amber totals should match the issue title;
   if they don't, the issue is stale — proceed from the live numbers and say so in the update.
3. `data/<lang>/` shell files + `expected_signals.json` (especially `notes`), and every
   `deviation_ledger.json` entry whose `languages_seen` includes this language.
4. The language's `rules` dict in gitgalaxy's
   `gitgalaxy/standards/language_standards/languages/<lang>.py` — which keys are wired,
   which are `None` and *why* (read the inline comments), and this language's entry (or
   deliberate absence) in `gitgalaxy_config.py`'s lexical-family delimiter maps.

## Phase 1 — classify every deviation (the five-cause taxonomy)

For each out-of-band metric, decide which bucket it belongs to. The test for each bucket, and
the action it dictates:

1. **Real engine bug.** The language HAS the construct, the engine claims to handle it, but the
   measurement is wrong. Test: trace the pipeline for this language specifically — does the
   rule's input stream actually contain what the rule expects? (jcl's `comment_lines` looked
   like "authoring chose few comments" until prism showed ALL of them sitting in the code
   stream.) → File a gitgalaxy issue + fix there (Phase 2).
2. **Missing rule with genuine morphology.** The rule key is `None`/absent, but the language
   really does express the concept, idiomatically and risk-relevantly (jcl error handling =
   `COND=`; error-ignoring = `COND=EVEN/ONLY`; log verbosity = `MSGLEVEL=/MSGCLASS=`). Test:
   can you name the language's own idiom for the concept and defend it to a practitioner of
   that language? Also check the overlap cost: a candidate whose keyword already feeds another
   rule may be net-negative (jcl `cleanup` = `DISP=(...,DELETE)` would double-count `io`'s
   `DISP=` — deliberately rejected and ledgered instead). → Propose the rule set in the
   strategy; add in gitgalaxy (Phase 2).
3. **Corpus authoring gap, not morphology.** The spec's construct IS expressible but the shell
   under-planted it. Test: re-read SPEC.md's requirement and ask whether the language *could*
   plant it (jcl `args` sat at 1 for months labeled "morphology" when `PARM=` per EXEC step was
   always legal and the engine rule already handled it). **Run this test before ever ledgering
   a §1 structure deviation as morphology.** → Re-author the shell (Phase 3).
4. **Intended morphology.** The language genuinely lacks the concept (jcl has no test
   framework, no doc idiom, no scoped-vs-global variables), or the deviation is deliberate
   engine design (jcl `dependency_links` +1 = the DD `DSN=` capture; datasets ARE
   dependencies). → Validated ledger entry per GATING.md; no code change.
5. **Median inflation — this language is the honest one.** The value matches planted intent
   exactly; the *median* is wrong because other languages over-count (return-in-branch family
   #2545, ×3 flux weighting #2546). Test: compare the observed value to SPEC.md's planted
   count, not to the median. → No action on this language; cross-reference the cross-cutting
   issue in the ledger/issue update and move on. Fixing it here would be tuning the honest
   language to match a bug.

§3 risk metrics are downstream shadows of §1/§2 — classify them "re-baselines after upstream"
and do not chase them individually.

## Phase 2 — engine work (in the gitgalaxy repo, its rules apply)

- gitgalaxy has a **strategy-first rule**: present the classification + proposed fix and get
  explicit approval before editing engine code. Scope questions worth asking explicitly: which
  bucket-2 rules to add, and any overlap trade-offs (the jcl `cleanup` decision was put to the
  user as its own question).
- File the issue first (`bug, core-engine, metrics` + component labels; **COBOL/JCL issues are
  always `priority: high`**). `gh pr edit --add-label` is broken there — use
  `gh api -X POST repos/squid-protocol/gitgalaxy/issues/<n>/labels -f 'labels[]=<label>'`.
- Engine changes that touch parsing = golden-master re-bless:
  `python tests/tools/crucible_check.py --update --yes` (both venvs, non-interactive), then a
  plain `crucible_check.py` must PASS. `audit_check.py` needs ruff/mypy on PATH — they live in
  `.crucible_venvs/full_precision/bin`, prepend it.
- Sanity-check the re-bless diff is the *expected shape* before blessing (the jcl one: every
  corpus `.jcl`'s coding/doc LOC split + new signals + global topology reflow — and nothing
  in unrelated languages beyond coordinate reflow).
- New rules need strict tests (positive/negative pairs + a dedicated semantics test + ReDoS
  detonation for any new quantified regex) in `tests/extraction/languages/test_<lang>_strict.py`.

## Phase 3 — corpus work (this repo)

1. Edit the shell files. **`git add` + commit BEFORE verifying** — the census only walks
   git-tracked files (engine fact #1; an uncommitted edit silently verifies the old content).
2. `GALAXYSCOPE_BIN=... python tools/verify_language.py <lang> --report` — account for EVERY
   observed count against planted intent. An unexplainable delta is a stop-and-investigate
   (possibly a new bucket-1 finding), never a number to bless.
3. Update `expected_signals.json` (counts + a `notes` field that explains every non-obvious
   placement — e.g. which steps carry which plants and why) and add/update the ledger entry
   per GATING.md's lifecycle. One entry per deviation *shape*; cite finditer/report evidence
   in the verdict.
4. The strict gate must PASS: `python tools/verify_language.py <lang>`.
5. Watch for plant-vs-keyword collisions: debt comment text must not contain OTHER menu
   keywords (a `//* TODO implement X` comment plants planned_debt **2** — `IMPLEMENT` is also
   a planned keyword).

## Phase 4 — regenerate and confirm

- `GALAXYSCOPE_BIN=... python tools/bias_report.py` — rescans all 46 languages, rewrites
  `docs/bias_report.md`, `docs/bias_variance_chart.svg`, `docs/bias_data.json`,
  `docs/findings_by_language.md`. Expect only the swept language's dots plus small median
  shifts to move; anything else moving is a red flag.
- `python tools/language_deviations.py <lang>` — the before/after for the issue update.

## Phase 5 — cross-repo PR choreography (ENGINE_REF + the pinned gate)

Two gates hold the repos together (gitgalaxy#2557; full protocol in docs/GATING.md
"Cross-repo choreography"): this repo's `verify.yml` checks out the engine at the committed
**`ENGINE_REF`** file's ref, and gitgalaxy's `rosetta-audit.yml` runs this corpus (pinned via
the `KEYWORD_ROSETTA_REF` Actions variable) against every engine PR that touches parsing code.

For a sweep that changes engine behavior:

1. Open the gitgalaxy PR `N`; its `rosetta-audit` check **fails — that is expected and
   correct** (the drift caught at the source). Never bless around it.
2. Open this repo's corpus PR with `ENGINE_REF` set to `pull/N/head` → its gates run against
   the engine PR's build and go green immediately. No draft, no waiting, no rerun.
3. When the engine PR is approved: restore `ENGINE_REF` to `main` in the corpus PR, merge the
   corpus PR, then the engine PR bumps `KEYWORD_ROSETTA_REF` to the new corpus commit and
   merges green. (The brief window where corpus main is ahead of engine main is covered by
   gitgalaxy's pinned gate.)
4. `tools/na_check.py --ci` runs in both gates — a sweep that removes/nulls a rule must ship
   the validated ledger entry in the same corpus PR, or shrink `docs/na_baseline.json` via
   `--regenerate` only for cells actually reviewed.

Also still true: verify locally against the engine branch anytime via `GALAXYSCOPE_BIN` —
CI choreography never blocks local iteration. **A PR touching only `tools/` runs ALL 46
gates** (no data diff → full sweep), which is by design: it is how stale baselines from
already-merged engine changes get caught (the cobol #2552/#2538 case).

## Phase 6 — close out

1. **Issue update comment** on the tracking issue: before/after red/amber counts, the
   deviations grouped by the five buckets with links (engine issue/PRs, ledger entry id), and
   a "remaining" list stating what each residual is blocked on (#2545/#2546, scoring-side
   morphology work, §3 downstream). The jcl comment on #2581 is the template.
2. **Capstone**: add/refresh the "Rosetta cross-language consistency" section (§10) in
   gitgalaxy's `docs/language_status/<lang>.md` via that repo's `language-status` skill —
   jcl.md §10 is the finished example. Also refresh §1/§3/§4 there if rules were added.
3. Close criteria (from the epic): every comparable metric in ±25%, OR every remaining
   deviation ledgered as intended morphology / blocked on a named cross-cutting issue. State
   plainly which criterion applies; closing is the user's call.

## Checklist

- [ ] Phase 0 sources read; `language_deviations.py` matches (or supersedes) the issue title
- [ ] Every red/amber classified into buckets 1-5 (§3 = "downstream", not chased)
- [ ] Bucket 3 test applied before ledgering ANY structure deviation as morphology
- [ ] Strategy approved before engine edits (gitgalaxy rule); scope questions asked explicitly
- [ ] Engine: issue filed + labeled (COBOL/JCL ⇒ priority: high); strict tests; golden masters
      re-blessed with an expected-shape diff; crucible_check + audit_check clean
- [ ] Corpus: shells committed BEFORE `--report`; every delta accounted; manifest notes updated;
      ledger entry validated with evidence; gate PASS
- [ ] `bias_report.py` regenerated; only the swept language (+ medians) moved
- [ ] PRs sequenced: engine PR green → user merges → rerun corpus CI → un-draft
- [ ] Issue comment posted; epic checkbox state checked; language_status §10 capstone written
- [ ] Memory/notes updated with any new engine facts discovered
