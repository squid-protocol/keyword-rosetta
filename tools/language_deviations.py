"""Print one language's metrics vs the cross-language median, band-classified.

The single-language triage view for a rosetta sweep (see
.claude/skills/rosetta-language-sweep/SKILL.md): where bias_report.py scans all 46
languages and regenerates the corpus-wide artifacts, this reads the already-cached
docs/bias_data.json and answers "where does THIS language stand right now, and by
how much?" -- the exact table a per-language tracking issue (gitgalaxy epic #2560's
children) is written from. Run bias_report.py first if the cache predates the engine
or corpus state you are triaging.

Usage:
    python tools/language_deviations.py <language> [--all-metrics]

By default only out-of-band metrics (beyond GREEN_DEV of the median) print, grouped
by the epic's triage order: structure first, then planted signals, then downstream
risk. --all-metrics includes the in-band rows too.

n/a rows (the language's registry defines no rule for the signal -- incomparable,
not zero) are excluded from the red/amber tally; an n/a with no validated ledger
entry recording WHY prints as an unreviewed warning instead.

Out-of-band cells carry a verdict (gitgalaxy#2669 E.1): a red or amber cell is
"explained" when a validated ledger entry names it, when it is a per-function
descriptor for a language with no functions (the quotient is undefined, not
deviant), or when it is a composite whose deviation entered through an input that
is itself out of band. Explained cells still print -- with the reason -- but do
not fail the gate, because the epic's close criterion is "nothing UNEXPLAINED
remains", not "nothing deviates".

Exit status: 0 if every out-of-band metric is explained AND no n/a cell is
unreviewed, 1 otherwise -- so a sweep can be gate-checked
(`python tools/language_deviations.py jcl && echo clean`).
"""

import json
import pathlib
import statistics
import sys

from bias_report import AMBER_DEV, GREEN_DEV, PLANTED, explain_out_of_band

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
BIAS_DATA = REPO_ROOT / "docs" / "bias_data.json"

# Mirrors bias_report.py's chart grouping: structure metrics are fixed upstream of
# signal rules, which sit upstream of the risk-score consequences.
STRUCTURE_METRICS = (
    "functions_found", "classes_found", "dependency_links",
    "keyword_hits", "comment_lines", "pagerank",
)


def classify(value, median):
    """Return (band, deviation); band is 'green'/'amber'/'red'/'zero-median'."""
    if median == 0:
        # Relative deviation is undefined. A nonzero value here is usually a
        # documented per-language morphology exception (jcl/cobol/css
        # class_start = program-unit cards, dockerfile FROM, ...), already
        # accounted in the manifest notes/ledger -- surfaced for eyeballing
        # but kept out of the red/amber tally so this script's counts match
        # the tracking issues', which exclude zero-median shapes too.
        return ("green" if value == 0 else "zero-median"), None
    dev = (value - median) / median
    if abs(dev) <= GREEN_DEV:
        return "green", dev
    if abs(dev) <= AMBER_DEV:
        return "amber", dev
    return "red", dev


def group_of(metric):
    if metric.startswith("risk_"):
        return 3, "risk (downstream -- re-baselines as upstream fixes land)"
    if metric in STRUCTURE_METRICS:
        return 1, "structure (fix first)"
    return 2, "signals"


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    show_all = "--all-metrics" in sys.argv
    if len(args) != 1:
        sys.exit(__doc__)
    lang = args[0]

    data = json.loads(BIAS_DATA.read_text())
    if lang not in data["languages"]:
        sys.exit(f"unknown language {lang!r} -- not in {BIAS_DATA}")
    na = data.get("na", {})  # {metric: {lang: "ledgered"|"unreviewed"}}

    # E.1: the same verdicts bias_report.py gates on, so per-language triage and
    # the corpus-wide gate can never disagree about what is left to do.
    ledger = json.loads((REPO_ROOT / "deviation_ledger.json").read_text())
    verdicts = explain_out_of_band(
        data["metrics"], data["languages"], ledger["entries"],
        {m: data["metrics"].get(m, {}) for m in ("functions_found",)},
    )

    rows = []
    for metric, values in sorted(data["metrics"].items()):
        if not isinstance(values, dict) or lang not in values:
            continue
        if lang in na.get(metric, {}) or values[lang] is None:
            rows.append((group_of(metric), metric, None, None,
                         "na-" + na.get(metric, {}).get(lang, "ledgered"), None))
            continue
        nums = [v for v in values.values() if isinstance(v, (int, float))]
        median = statistics.median(nums)
        band, dev = classify(values[lang], median)
        rows.append((group_of(metric), metric, values[lang], median, band, dev))

    rows.sort(key=lambda r: (r[0][0], r[1]))
    dot = {"green": "\U0001f7e2", "amber": "\U0001f7e1", "red": "\U0001f534",
           "zero-median": "◦", "na-ledgered": "—", "na-unreviewed": "⚠"}
    reds = ambers = comparable = unreviewed = explained = 0
    current_group = None
    for (gnum, gname), metric, value, median, band, dev in rows:
        if band not in ("zero-median", "na-ledgered", "na-unreviewed"):
            comparable += 1
        verdict = verdicts.get((metric, lang), (None, ""))[0]
        if band in ("red", "amber") and verdict and verdict != "unexplained":
            explained += 1
        elif band == "red":
            reds += 1
        elif band == "amber":
            ambers += 1
        elif band == "na-unreviewed":
            unreviewed += 1
        if band == "green" and not show_all:
            continue
        if (gnum, gname) != current_group:
            current_group = (gnum, gname)
            print(f"\n== {gnum}. {gname} ==")
        if band.startswith("na-"):
            # Derived risk_* cells are n/a for a composed reason (every registry
            # input to the formula is absent AND the scan confirms a pinned 0), and
            # inherit their review status from those inputs -- so they get their own
            # wording rather than the planted signal's "no rule in registry".
            derived = metric.startswith("risk_")
            if band == "na-ledgered":
                note = ("every registry input to this formula is absent (score pinned "
                        "at 0); each of those absences is recorded in the ledger"
                        if derived
                        else "no rule in registry; absence recorded in the deviation ledger")
            else:
                note = ("every registry input to this formula is absent (score pinned "
                        "at 0), but at least one of those inputs has NO ledger entry "
                        "saying why -- see docs/na_baseline.json"
                        if derived
                        else "no rule in registry and NO ledger entry says why -- real "
                             "morphology to ledger, or a missing-rule engine gap")
            print(f"{dot[band]} {metric:24s} {'n/a':>10s}  {note}")
            continue
        dev_txt = f"{dev:+.0%}" if dev is not None else "(median 0 -- morphology, check manifest notes)"
        planted = f"  planted={PLANTED[metric]}" if metric in PLANTED else ""
        status, detail = verdicts.get((metric, lang), (None, ""))
        mark = ""
        if status and status != "unexplained":
            # Explained: shown, reasoned, and excluded from the gate's tally.
            mark = f"  [{status}" + (f": {detail}" if detail else "") + "]"
        print(f"{dot[band]} {metric:24s} {value:>10.4g}  median {median:<10.4g} {dev_txt}{planted}{mark}")

    tail = (f"\n{lang}: {reds} red / {ambers} amber UNEXPLAINED across {comparable} "
            f"comparable metrics")
    if explained:
        tail += f"; {explained} further out-of-band cell(s) explained (see [tags] above)"
    if unreviewed:
        tail += f"; WARNING {unreviewed} unreviewed n/a cell(s)"
    print(tail)
    sys.exit(0 if reds + ambers + unreviewed == 0 else 1)


if __name__ == "__main__":
    main()
