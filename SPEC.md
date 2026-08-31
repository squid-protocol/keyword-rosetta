# Keyword Rosetta — Canonical Shell Specification

This is the authoring contract for every `data/<language>/` folder. It is written to be
handed verbatim to a model (or human) generating one language's version. The verifier
(`tools/verify_language.py`) is the reviewer: a folder that passes is correct by
construction; one that fails is either a bad generation or a real GitGalaxy engine bug —
both outcomes are the point of this corpus.

## Ground rules

1. **The code never needs to run.** GitGalaxy scans broken code. Do not add scaffolding,
   error handling, or realism beyond what this spec asks for. Every line must serve a
   planted signal, a decoy, or the minimal syntax the language requires.
2. **Functions only — no classes, no methods, no types-with-bodies.** `class_start`
   expected = 0 is a deliberate false-positive tripwire in every language. If the
   language cannot express a free function (e.g. COBOL uses paragraphs, SQL uses
   statements), use its closest function-shaped construct — the same convention
   GitGalaxy's tri-comparison ledger already applies.
3. **Every keyword occurrence is deliberate.** Take token-signal keywords from this
   language's generated menu (`docs/menus/<language>.json`) — never from memory. If a
   menu keyword can't be written syntactically in this language without dragging in
   other signals, pick the next menu keyword.
4. **Exact counts.** Each planted signal appears the exact number of times listed below.
   Incidental extra matches (e.g. a `for` needed as glue syntax) must be counted into
   the manifest, not left unrecorded — prefer restructuring to avoid them.

## File layout (per language folder)

```
data/<language>/
  <manifest>              # the language's idiomatic minimal project file, if it has one
                          # (package.json, Cargo.toml, go.mod, Makefile, *.gemspec, ...)
  main.<ext>              # entry: imports/includes a; calls probe functions
  a.<ext>                 # imports b
  b.<ext>                 # imports c
  c.<ext>                 # leaf, no imports
  expected_signals.json   # ground truth (schema below)
```

The import chain **main → a → b → c** must be real, resolvable import/include/require
statements in that language's syntax — it is the known-shape dependency DAG that
cross-checks `network_risk_sensor.py`. These import statements ARE the planted
`import` signal occurrences (1 per file for main/a/b, 0 for c).

## The probe functions

Twelve probe functions, distributed: `main.<ext>` holds probes 1–3 plus the entry
function, `a.<ext>` holds 4–6, `b.<ext>` holds 7–9, `c.<ext>` holds 10–12. Names are
`probe_<signal>` adapted to the language's naming convention (`PROBE-BRANCH` in COBOL,
`probeBranch` where snake_case is unidiomatic — keep the two words recognizable).

| # | Function | Signal planted | Count | Class |
|---|---------------------|----------------------|-------|------------|
| 1 | probe_branch | `branch` | 3 | token |
| 2 | probe_io | `io` | 3 | token |
| 3 | probe_risk | `high_risk_execution`| 2 | token |
| 4 | probe_globals | `globals` | 2 | token |
| 5 | probe_test | `test` | 2 | token |
| 6 | probe_safety | `safety` | 2 | token |
| 7 | probe_bypass | `safety_bypasses` | 2 | token |
| 8 | probe_telemetry | `telemetry` | 2 | token |
| 9 | probe_state | `state_mutation` | 2 | token |
| 10 | probe_cleanup | `cleanup` | 2 | token |
| 11 | probe_debt | `fragile_debt` | 1 | comment |
| 12 | probe_todo | `planned_debt` | 1 | comment |

Structural signals are planted by the shell itself rather than by a dedicated probe:

- `func_start` / `args`: 13 function definitions total (12 probes + entry), each probe
  taking exactly **one** argument where the language expresses arguments.
- `import`: the main→a→b→c chain (3 occurrences corpus-wide).
- `doc`: one doc-comment on the entry function, in the language's doc idiom.
- `api` / `encapsulation` / `ownership` / `dead_code`: plant **only if** this language's
  menu lists a plantable keyword or the language has a one-line idiomatic construct;
  otherwise record expected 0. These four vary too much to force uniformly.

If a signal in the table has no plantable menu keyword for this language (Tier-2
languages, or a structural-only rule), record expected 0 in the manifest and move on —
never invent an occurrence the rule can't match.

## Decoys (all recorded, all expected 0 extra)

Decoys cross the two detection surfaces in both directions:

1. **Comment decoy** — every file carries one comment containing 2+ code-stream
   keywords in prose, e.g. `# this probe never calls eval and has no while loop`.
   Must contribute nothing: tests `prism.py` comment stripping.
2. **String decoy** — one string literal per language containing code-stream keywords,
   e.g. `msg = "if eval fails, try open"`. Must contribute nothing: tests literal
   shielding. Skip only if the language has no string literals.
3. **Reverse decoy** — one code identifier built from a comment-surface keyword, e.g.
   a variable named `HACK_LEVEL` (fragile_debt's `HACK` must only count in comments in
   languages whose rule is comment-anchored; where the rule matches anywhere, record
   it as a planted occurrence instead — the menu + a verifier run settles which).
4. **The `#hack` tag** — probe_debt's comment is written as the tech-debt tag itself
   (`# HACK: shortcut, see rosetta spec`), the corpus's one deliberate tech-debt marker
   per language.

## expected_signals.json schema

```json
{
  "language": "python",
  "tier": 1,
  "generator": "claude-sonnet-5 | human | <model-id>",
  "files": {
    "main.py": {"branch": 3, "io": 3, "high_risk_execution": 2, "func_start": 4, "...": 0},
    "a.py":    {"...": 0}
  },
  "decoys": [
    {"file": "main.py", "line_hint": "never calls eval", "surface": "comment", "signals": ["high_risk_execution", "branch"]},
    {"file": "a.py", "line_hint": "HACK_LEVEL", "surface": "code", "signals": ["fragile_debt"]}
  ],
  "notes": "anything non-obvious about how this language expresses the shell"
}
```

Only list keys with nonzero expectations plus every key the verifier should assert as
zero (`class_start` always among them). The verifier treats unlisted keys as
"don't-care" — but `class_start`, and every signal named in a decoy, must be listed.

## Engine facts learned from the python reference (2026-08-31)

Verified empirically; every generator must account for them:

1. **Files must be git-committed before verification.** GalaxyScope's census walks
   git-tracked files — an untracked folder scans as "0 files mapped".
2. **`api` inflates on imported files** (the Contextual Baseline Fix,
   `galaxyscope.py` ~2145): a file imported by others has its `orphaned_logic`
   (uncalled functions) converted into `api`. With the spec's main→a→b→c chain and
   uncalled probes, expect `api = defs × 2` in a/b/c and `api = defs` in main.
3. **String literals count for most code-stream signals** — the string decoy's
   keywords land in branch/safety/io and must be baked into that file's expected
   counts. Shielding is *selective*: the high-risk family (`eval` etc.) does NOT
   count from inside a literal (it feeds `sec_tainted_injection` instead). Record
   what the verifier reports and describe it in the decoy's `outcome` field.
4. **Known keyword overlaps** (record, don't avoid): `assert` hits both `safety`
   and `test`; `os.`/`sys.` prefixes needed for `globals` also hit python-family
   `io`. Every language will have its own — the report run reveals them.

## Authoring workflow

1. `python tools/keyword_menu.py <language>` — regenerate and read the menu.
2. Write the four files + manifest stub per this spec, **git add + commit them**.
3. `python tools/verify_language.py <language> --report` — read every observed
   count; explain each delta from your planted intent (overlap? decoy surface?
   engine semantic?) before accepting it. An unexplainable delta is a stop-and-
   investigate, possibly a real engine bug — never bless a number you can't
   account for.
4. Lock the manifest, then `python tools/verify_language.py <language>` must PASS.
5. Record any spec deviation the language forced in the manifest `notes` field.
