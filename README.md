# Keyword Rosetta

A multi-language **control corpus** for [GitGalaxy](https://github.com/squid-protocol/gitgalaxy)
(squid-protocol/gitgalaxy#1096): the same minimal program shell expressed in every language
GitGalaxy's `language_standards.py` registry supports, with a known, exact number of planted
signal keywords per file — so structural extraction can be validated for **cross-language
equivalence**, and downstream risk scores can be compared for **language bias**.

The code here is not meant to run. GitGalaxy scans broken code; what matters is that every
planted keyword occurrence is deliberate, counted, and recorded in each language folder's
`expected_signals.json`.

## Layout

```
SPEC.md                     # canonical program shell + authoring rules (the generation prompt)
tools/keyword_menu.py       # mines per-language keyword menus from language_standards.py
tools/verify_language.py    # galaxyscope one folder, diff detected vs expected — the PR gate
tools/bias_report.py        # full-corpus run: cross-language count + risk-score outlier report
data/<language>/            # one folder per language: main + a/b/c + manifest + expected_signals.json
docs/menus/<language>.json  # generated keyword menus (regenerate, don't hand-edit)
```

## Tiers

- **Tier 1** (39 languages): the full 20-signal core shell.
- **Tier 2** (markdown, jcl, css, html, yaml, yacc, solidity): reduced shell — each folder's
  `expected_signals.json` declares which signals that language's registry entry actually defines.

Source of truth is always the live `LANGUAGE_DEFINITIONS` in the GitGalaxy checkout named by
`GITGALAXY_PATH` (default: a sibling `gitgalaxy/v6` checkout). Nothing here hand-copies keyword
lists.

## License

PolyForm Noncommercial 1.0.0, matching GitGalaxy.
