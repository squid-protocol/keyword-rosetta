# Keyword Rosetta

A multi-language **control corpus** for [GitGalaxy](https://github.com/squid-protocol/gitgalaxy)
([gitgalaxy#1096](https://github.com/squid-protocol/gitgalaxy/issues/1096)): the same minimal
12-probe program expressed in every language GitGalaxy's `language_standards.py` registry
supports, with a known, exact number of planted signal keywords per file — so structural
extraction can be validated for **cross-language equivalence**, and downstream risk scores can
be compared for **language bias**. One program, every language: does the engine measure it the
same everywhere?

The code here is not meant to run. GitGalaxy scans broken code; what matters is that every
planted keyword occurrence is deliberate, counted, and locked in each language folder's
`expected_signals.json` — and that every deviation from planted intent has a validated entry
in the deviation ledger before it may be baked into a manifest.

**Status: all 46 registry languages locked** (every signature-bearing language in
`LANGUAGE_DEFINITIONS`, Tier-1 and Tier-2), 35 validated deviation shapes, 15 upstream engine
issues filed and tracked (gitgalaxy
[#2535](https://github.com/squid-protocol/gitgalaxy/issues/2535)–[#2549](https://github.com/squid-protocol/gitgalaxy/issues/2549),
[#2610](https://github.com/squid-protocol/gitgalaxy/issues/2610)), with per-language deviation
tracking under gitgalaxy epic [#2560](https://github.com/squid-protocol/gitgalaxy/issues/2560).

## Layout

```
SPEC.md                        # canonical program shell + authoring rules (the generation prompt)
deviation_ledger.json          # one validated entry per deviation shape (the audit trail)
docs/GATING.md                 # the self-improvement gate: how a number earns its place
docs/bias_report.md            # full cross-language tables (signals, structure, risk scores)
docs/bias_variance_chart.svg   # the variance gate: dot strips, zone counts, PASS/WARN/FAIL
docs/findings_by_language.md   # actionable per-language report: defect → issue → evidence file
tools/keyword_menu.py          # mines per-language keyword menus from language_standards.py
tools/verify_language.py       # galaxyscope one folder, diff detected vs expected — the PR gate
tools/bias_report.py           # full-corpus scan → report + chart + cache (+ findings refresh)
tools/findings_report.py       # joins ledger + manifests + scan cache into the findings doc
data/<language>/               # main + a/b/c (known import chain) + expected_signals.json
docs/menus/<language>.json     # generated keyword menus (regenerate, don't hand-edit)
```

## The workflow

1. `python tools/keyword_menu.py <language>` — regenerate and read the menu.
2. Author the four files per `SPEC.md`, **git add + commit** (the census only scans tracked files).
3. `python tools/verify_language.py <language> --report` — explain every observed delta
   (keyword overlap? decoy surface? engine semantic?) before accepting it; an unexplainable
   delta is a stop-and-investigate, possibly a real engine bug.
4. Record each deviation in `deviation_ledger.json` per `docs/GATING.md`, lock the manifest,
   and the plain `verify_language.py <language>` gate must PASS.
5. `python tools/bias_report.py` — rebuilds the report, the variance chart, and the
   per-language findings doc together.

Tools need a GitGalaxy checkout (`GITGALAXY_PATH`, default sibling `gitgalaxy/v6`) and a
`galaxyscope` binary (`GALAXYSCOPE_BIN`).

For *improving* an already-authored language (working one of gitgalaxy epic
[#2560](https://github.com/squid-protocol/gitgalaxy/issues/2560)'s per-language tracking
issues), use the `rosetta-language-sweep` skill
(`.claude/skills/rosetta-language-sweep/SKILL.md`) — it routes each measured deviation to the
right fix (engine bug, missing rule, corpus authoring gap, ledgered morphology, or median
inflation) instead of treating the red/amber list as a single work queue.
`python tools/language_deviations.py <lang>` prints the live vs-median band table.

## Tiers

- **Tier 1** (39 languages): the full 20-signal core shell.
- **Tier 2** (markdown, jcl, css, html, yaml, yacc, solidity): reduced shell — each folder's
  `expected_signals.json` declares which signals that language's registry entry defines.

Source of truth is always the live `LANGUAGE_DEFINITIONS` in the GitGalaxy checkout. Nothing
here hand-copies keyword lists.

## License

PolyForm Noncommercial 1.0.0, matching GitGalaxy — see `LICENSE`.

## The GitGalaxy constellation

This repo is one strand of the web of repos that build, prove, and showcase
[GitGalaxy](https://github.com/squid-protocol/gitgalaxy). This is the **consistency leg** —
identical planted intent in every language; the **accuracy leg** (is extraction right on real
code?) is the crucible + tri-comparison system:

- [gitgalaxy](https://github.com/squid-protocol/gitgalaxy) — the engine under measurement
- **keyword-rosetta** — *you are here*: the 46-language planted control corpus
- [language-crucible](https://github.com/squid-protocol/language-crucible) — real-world adversarial corpus behind the engine's golden-master gate and tri-comparison accuracy program
- [gitgalaxy-raw-output](https://github.com/squid-protocol/gitgalaxy-raw-output) — unedited scans of real repos + speed telemetry
- [gitgalaxy-population-analyses](https://github.com/squid-protocol/gitgalaxy-population-analyses) — statistics over the scan population (cross-language comparisons there inherit whatever bias this corpus measures)
- [cobol_to_java_examples](https://github.com/squid-protocol/cobol_to_java_examples) — 10 COBOL repos auto-translated to compiling Spring Boot architectures
- [squid-telemetry](https://github.com/squid-protocol/squid-telemetry) — public distribution/adoption metrics
- Docs: [architecture & methodology site](https://squid-protocol.github.io/gitgalaxy/) · [risk-equation methodology](https://squid-protocol.github.io/gitgalaxy/08-01-methodology) (the formulas this corpus stress-tests) · [Museum of Code](https://squid-protocol.github.io/gitgalaxy/museum-of-code/) · [gitgalaxy.io](https://gitgalaxy.io/)
