"""Baseline-gated audit of ORPHAN ledger tokens (validated signal tokens that
excuse no out-of-band cell any more).

A collective deviation-ledger entry lists a `signal` union of N metric tokens
across M languages; the reports read it as the N x M cross-product of excused
cells (docs/GATING.md "ledgered" verdict; bias_report.explain_out_of_band). The
shapes an entry documents retire one at a time -- a decoy gets planted, an engine
rule is narrowed, a metric re-baselines -- and nothing notices when the LAST
out-of-band cell a token still explained goes green. The token then sits in the
union excusing nothing, and the cross-product silently claims M dead cells. This
is structural, not sloppiness: keyword-rosetta#75 found four of
`batch5-tier2-morphology-shapes`' eight tokens decayed to this, the third such
narrowing of that one entry.

The ledger `_doc` already states the rule this enforces:

    a token must hold for EVERY language listed -- scope a collective entry down
    rather than let it excuse a cell nobody looked at.

WHAT COUNTS AS AN ORPHAN. A token T in a validated entry E is `E.id/T` orphan
when, across E's `languages_seen`, T has at least one COMPARABLE cell (a language
that measures T with a real number, not an n/a rule-absence) and NONE of those
comparable cells is out of band. Two deliberate exclusions keep the signal clean:

  * a token whose cells are ALL n/a is not an orphan -- it records an
    incomparability, not a retired deviation, and that is `tools/na_check.py`'s
    job (docs/GATING.md "n/a semantics"). An entry like `markdown-lit-plane-
    morphology`, whose language plants nothing measurable, is doing its job, not
    decaying.
  * a token that names an ungated column (vocabulary/context/unplanted input) or
    a pseudo-signal with no measured column at all (`api_orphan_credit`,
    `structural_boundaries`) is never banded, so it cannot be "out of band" and
    is reported as unbandable rather than flagged.

Retired entries (`still_reproduces: false`) are skipped entirely, matching the
gate since keyword-rosetta#81: they excuse nothing, so their tokens are already
inert and flagging them would just make every retirement look like decay.

The token is resolved to the column it is actually measured under before banding,
using the engine's own `RISK_INPUT_COLUMNS` map (so `api` reads `raw_arch_api`,
`encapsulation` reads `def_encapsulation`) -- otherwise `api` would read the inert
all-None `api` column and flag as orphan in every entry that names it.

REPORT, NOT GATE (keyword-rosetta#75). Whether an orphan is a defect (scope the
entry down) or a documented shape kept on purpose that simply is not pushing a
cell out of band today is a judgement call. So this is baseline-gated like
`tools/na_check.py`, not an absolute gate: `docs/orphan_token_baseline.json` holds
the reviewed set and `--ci` fails only on tokens that decayed AFTER it -- a PR
that plants away the last cell a token explained, or adds a dead token, is caught
at the source, while the standing backlog does not block unrelated work.

Scan-free: it reuses the bands already cached in `docs/bias_data.json` and the
same `out_of_band_cells()` that `bias_report.py --gate` uses, so the two can never
disagree about which cells are out of band. Run `tools/bias_report.py` first if the
cache predates the engine/corpus state you are auditing. The push/daily
`bias-history.yml` regenerates the cache AND this baseline together against engine
main, so on main the two are always in lockstep and a PR's `--ci` only ever sees
orphans the PR itself introduced -- engine drift re-baselines on its own.

Usage:
    python tools/ledger_orphan_check.py              # report every orphan token
    python tools/ledger_orphan_check.py --ci         # exit 1 on NEW orphans
    python tools/ledger_orphan_check.py --regenerate # rewrite the baseline
"""

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from bias_report import (  # noqa: E402  (sys.path shim above; see AGENTS.md testing note)
    CONTEXT_METRICS,
    RISK_INPUT_COLUMNS,
    declaration_strata,
    out_of_band_cells,
    reference_medians,
)

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
BIAS_DATA = REPO_ROOT / "docs" / "bias_data.json"
LEDGER = REPO_ROOT / "deviation_ledger.json"
BASELINE = REPO_ROOT / "docs" / "orphan_token_baseline.json"


def _load_cache():
    if not BIAS_DATA.exists():
        sys.exit(
            f"{BIAS_DATA.relative_to(REPO_ROOT)} missing -- run tools/bias_report.py first "
            "(it rescans all languages and writes the cache this audit reads)."
        )
    return json.loads(BIAS_DATA.read_text())


def analyse():
    """Return (orphans, details, by_entry).

    orphans: sorted list of "entry_id/token".
    details[entry_id/token] = {"column", "comparable", "languages_seen"} so the
    report can show WHY a token is dead (every comparable cell, all in band).
    by_entry[entry_id] = {"orphan": [...], "live": [...], "unbandable": [...]} --
    every validated entry's tokens split three ways. "live" is load-bearing
    (banded and out of band somewhere); "unbandable" names an ungated column or a
    pseudo-signal that is never banded (so it is neither dead nor alive); "orphan"
    is banded, comparable, and in band everywhere it names.
    """
    data = _load_cache()
    metrics = data["metrics"]
    languages = data["languages"]
    strata = data.get("strata") or {}
    constant_sensitive = data.get("constant_sensitive") or []
    na = data.get("na", {})  # {metric: {lang: "ledgered"|"unreviewed"}}
    # F.1/F.3: ungated columns (length/vocabulary/unplanted/temporal) are reported,
    # never gated -- a token naming one is never banded, so it can't be an orphan.
    ungated = set(data.get("ungated_metrics") or CONTEXT_METRICS)

    refs = reference_medians(metrics, languages, strata, constant_sensitive)
    # gitgalaxy#2796: classes_found bands on the declaration-requirement PRESENCE axis,
    # the same one bias_report.py --gate uses, so the orphan check and the gate never
    # disagree on which cells are out of band.
    presence = {"classes_found": declaration_strata(languages)}
    oob = out_of_band_cells(metrics, languages, refs, presence=presence)

    def resolve(token):
        # The signal names a SPEC signal; the recorder stores a few under other
        # column names (api -> raw_arch_api, encapsulation -> def_encapsulation).
        # Same map bias_report.py's derivation edges use, so nothing drifts.
        return RISK_INPUT_COLUMNS.get(token, token)

    def comparable(col, lang):
        value = metrics.get(col, {}).get(lang)
        return isinstance(value, (int, float)) and lang not in na.get(col, {})

    ledger = json.loads(LEDGER.read_text())["entries"]
    orphans = []
    details = {}
    by_entry = {}
    for entry in ledger:
        # Same predicate `explain_out_of_band` gates on since keyword-rosetta#81: a
        # RETIRED entry (still_reproduces: false) no longer excuses any cell, so its
        # tokens cannot be orphans -- there is nothing left for them to fail to
        # excuse. Auditing them would report 33 dead tokens that the gate already
        # ignores, and every retirement would land as a wave of false findings.
        if entry.get("status") != "validated" or entry.get("still_reproduces") is False:
            continue
        seen = entry.get("languages_seen", [])
        buckets = by_entry.setdefault(
            entry["id"], {"orphan": [], "live": [], "unbandable": []}
        )
        for token in (entry.get("signal") or "").split("|"):
            if not token:
                continue
            col = resolve(token)
            if col not in metrics or col in ungated:
                buckets["unbandable"].append(token)  # ungated / pseudo-signal
                continue
            comp = [lang for lang in seen if comparable(col, lang)]
            if not comp:
                buckets["unbandable"].append(token)  # all n/a -- na_check's domain
                continue
            if any((col, lang) in oob for lang in comp):
                buckets["live"].append(token)  # load-bearing on a comparable cell
                continue
            key = f"{entry['id']}/{token}"
            buckets["orphan"].append(token)
            orphans.append(key)
            details[key] = {"column": col, "comparable": comp, "languages_seen": seen}
    return sorted(set(orphans)), details, by_entry


def _partial_decay(by_entry):
    """Entries with SOME dead tokens while others still hold -- the actionable
    "scope it down" case (batch5's shape). An entry whose only banded token is now
    dead is fully dormant, a different disposition; this surfaces the mixed ones,
    where the live tokens prove the entry is still needed but the dead ones are
    dragging cells nobody looks at."""
    partial = {}
    for eid, b in by_entry.items():
        if b["orphan"] and b["live"]:
            partial[eid] = (sorted(b["orphan"]), sorted(b["live"]))
    return partial


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    orphans, details, by_entry = analyse()

    if mode == "--regenerate":
        BASELINE.write_text(json.dumps({"orphan_tokens": orphans}, indent=1) + "\n")
        print(f"wrote {BASELINE.relative_to(REPO_ROOT)} ({len(orphans)} orphan tokens)")
        return 0

    baseline = set(
        json.loads(BASELINE.read_text()).get("orphan_tokens", []) if BASELINE.exists() else []
    )
    new = [k for k in orphans if k not in baseline]
    resolved = sorted(baseline - set(orphans))

    print(f"orphan ledger tokens: {len(orphans)} ({len(baseline)} baselined)")

    partial = _partial_decay(by_entry)
    if partial:
        print(
            f"\npartial-decay entries ({len(partial)}) -- some tokens dead while others still "
            "hold; candidates to scope down (docs/GATING.md, _doc rule):"
        )
        for eid, (dead, live) in sorted(partial.items()):
            print(f"  {eid}")
            print(f"      dead: {', '.join(dead)}")
            print(f"      live: {', '.join(live) or '(none)'}")

    if resolved:
        print(
            f"\nresolved since baseline (run --regenerate to shrink it): "
            f"{', '.join(resolved)}"
        )

    if new:
        print(f"\nNEW orphan tokens (not in {BASELINE.name}):")
        for key in new:
            d = details[key]
            print(
                f"  - {key}: every comparable cell in band "
                f"({', '.join(d['comparable'])} on {d['column']})"
            )
        print(
            "\nEach is a token that no longer excuses any out-of-band cell for its entry. "
            "Either scope the entry down (drop the token, record why in the verdict), or -- "
            "if it is a documented shape kept on purpose that simply is not deviating today -- "
            "run --regenerate to accept it into the baseline."
        )
        return 1 if mode == "--ci" else 0

    print("\nno new orphan tokens")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
