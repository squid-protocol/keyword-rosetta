"""Generate (and optionally post) the per-language status comment for a rosetta tracking issue.

gitgalaxy epic #2560 opened one issue per language (#2561-#2607); gitgalaxy#2669's
Batch E.2 is the rule that every batch regen leaves each of them a status comment
written from data rather than from memory. gitgalaxy#2581's jcl close-out is the
template: headline movement, then what is fixed / ledgered / still owned by someone.

The comment is generated from docs/bias_data.json plus deviation_ledger.json, using
the SAME verdict machinery bias_report.py gates on (gitgalaxy#2669 E.1), so an issue
can never disagree with the gate about what is left to do.

Usage:
    python tools/issue_status.py <language>            # print one comment
    python tools/issue_status.py --all                 # print all 46
    python tools/issue_status.py <language> --post     # post it via gh
    python tools/issue_status.py --all --post          # post all (asks nothing -- be sure)

--post resolves the issue by searching gitgalaxy for a `rosetta[<language>]:` title, so
the mapping is never stored and cannot go stale. Requires `gh` authenticated against
the engine repo.

Exit status mirrors language_deviations.py: 0 when the language has nothing
unexplained and no unreviewed n/a cell -- i.e. it meets Batch E.4's close criterion.
"""

import json
import pathlib
import statistics
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from bias_report import CONTEXT_METRICS, GREEN_DEV, explain_out_of_band  # noqa: E402
from language_deviations import STRUCTURE_METRICS, classify, group_of  # noqa: E402

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
ENGINE_REPO = "squid-protocol/gitgalaxy"

# How each verdict reads in prose, and whether it counts against the close criterion.
VERDICT_PROSE = {
    "ledgered": "a validated ledger entry names this language and this metric",
    "derived": "the deviation entered through an input that is itself out of band -- "
               "the same finding counted twice",
    "undefined": "a per-function descriptor for a language with no functions: the "
                 "quotient has no value, so this is not a deviation",
}


def build(lang, data, ledger):
    """Returns (markdown, is_clean) for one language."""
    metrics = data["metrics"]
    na = data.get("na", {})
    verdicts = explain_out_of_band(
        metrics, data["languages"], ledger["entries"],
        {"functions_found": metrics.get("functions_found", {})},
        risk_inputs=data.get("risk_inputs"),
    )

    rows, unreviewed, context = [], [], []
    for metric, values in sorted(metrics.items()):
        if not isinstance(values, dict) or lang not in values:
            continue
        if metric in CONTEXT_METRICS:
            # F.1: program length is reported, never gated -- it neither counts
            # against the language nor needs a verdict.
            nums = [v for v in values.values() if isinstance(v, (int, float))]
            if isinstance(values[lang], (int, float)) and nums:
                band, dev = classify(values[lang], statistics.median(nums))
                if band in ("red", "amber"):
                    context.append((metric, values[lang], statistics.median(nums), dev))
            continue
        state = na.get(metric, {}).get(lang)
        if state:
            if state == "unreviewed":
                unreviewed.append(metric)
            continue
        if values[lang] is None:
            continue
        nums = [v for v in values.values() if isinstance(v, (int, float))]
        band, dev = classify(values[lang], statistics.median(nums))
        if band in ("red", "amber"):
            status = verdicts.get((metric, lang), ("unexplained", ""))
            rows.append((metric, values[lang], statistics.median(nums), dev, band, status))

    unexplained = [r for r in rows if r[5][0] == "unexplained"]
    explained = [r for r in rows if r[5][0] != "unexplained"]
    is_clean = not unexplained and not unreviewed

    out = []
    reds = sum(1 for r in unexplained if r[4] == "red")
    ambers = sum(1 for r in unexplained if r[4] == "amber")

    if is_clean:
        out.append(f"## Status: **clean** — every out-of-band metric is accounted for")
    else:
        out.append(f"## Status: **{reds}🔴 / {ambers}🟡 unexplained**, "
                   f"{len(explained)} further out-of-band cell(s) accounted for")
    out.append("")
    out.append(
        "Generated from `docs/bias_data.json` + `deviation_ledger.json` by "
        "`tools/issue_status.py`, using the same verdict machinery "
        "`bias_report.py --gate` runs on (gitgalaxy#2669 E.1), so this comment and the "
        "gate cannot disagree about what is left."
    )
    out.append("")

    if unexplained:
        out.append("### Still unexplained — the work this issue tracks")
        out.append("")
        out.append("| metric | value | median | dev | group |")
        out.append("|---|---|---|---|---|")
        for metric, val, med, dev, band, _ in sorted(unexplained, key=lambda r: group_of(r[0])[0]):
            dot = "🔴" if band == "red" else "🟡"
            dev_txt = f"{dev:+.0%}" if dev is not None else "median 0"
            out.append(f"| {dot} `{metric}` | {val:.4g} | {med:.4g} | {dev_txt} | "
                       f"{group_of(metric)[1].split(' (')[0]} |")
        out.append("")

    if explained:
        out.append("### Out of band, but accounted for")
        out.append("")
        by_verdict = {}
        for metric, val, med, dev, band, (status, detail) in explained:
            by_verdict.setdefault(status, []).append((metric, detail))
        for status, items in sorted(by_verdict.items()):
            out.append(f"**{status}** — {VERDICT_PROSE.get(status, '')}")
            out.append("")
            for metric, detail in sorted(items):
                out.append(f"- `{metric}`" + (f" — {detail}" if detail else ""))
            out.append("")

    if context:
        out.append(
            "**Program length (context, not gated):** "
            + ", ".join(f"`{m}` {v:.4g} vs median {med:.4g} ({dev:+.0%})"
                        for m, v, med, dev in context)
            + " — how long this language's shell came out, which the SPEC does not plant "
            "(gitgalaxy#2669 F.1); shown for orientation only."
        )
        out.append("")

    if unreviewed:
        out.append("### Unreviewed n/a cells")
        out.append("")
        out.append(
            "The registry defines no rule here, and **no validated ledger entry records "
            "why** — each is either real morphology to ledger or a missing-rule engine gap "
            "of the kind gitgalaxy#2610 turned out to be: "
            + ", ".join(f"`{m}`" for m in sorted(unreviewed)) + "."
        )
        out.append("")

    out.append("### Close criterion (gitgalaxy#2669 Batch E.4)")
    out.append("")
    if is_clean:
        out.append(
            "`python tools/language_deviations.py " + lang + "` **exits 0**: nothing is "
            "unexplained and no n/a cell is unreviewed. That is not the same as \"no metric "
            "deviates\" — deviations remain, and each is named above with the reason it is "
            "not a defect. This issue has nothing language-specific left to do."
        )
    else:
        out.append(
            "`python tools/language_deviations.py " + lang + "` **exits 1**: "
            f"{len(unexplained)} unexplained cell(s)"
            + (f" and {len(unreviewed)} unreviewed n/a cell(s)" if unreviewed else "")
            + " remain. Each needs a fix, or a validated ledger entry saying why it is "
            "correct, before this issue can close."
        )
    return "\n".join(out), is_clean


def issue_number(lang):
    """Resolve the tracking issue by title, so no mapping is stored to go stale."""
    res = subprocess.run(
        ["gh", "issue", "list", "--repo", ENGINE_REPO, "--state", "all", "--limit", "100",
         "--search", f"rosetta[{lang}] in:title", "--json", "number,title"],
        capture_output=True, text=True, check=True,
    )
    for item in json.loads(res.stdout):
        if item["title"].startswith(f"rosetta[{lang}]"):
            return item["number"]
    return None


def main():
    argv = [a for a in sys.argv[1:] if not a.startswith("--")]
    do_all = "--all" in sys.argv
    post = "--post" in sys.argv
    if not do_all and len(argv) != 1:
        sys.exit(__doc__)

    data = json.loads((REPO_ROOT / "docs" / "bias_data.json").read_text())
    ledger = json.loads((REPO_ROOT / "deviation_ledger.json").read_text())
    langs = data["languages"] if do_all else argv

    all_clean = True
    for lang in langs:
        if lang not in data["languages"]:
            sys.exit(f"unknown language {lang!r}")
        body, clean = build(lang, data, ledger)
        all_clean &= clean
        if post:
            num = issue_number(lang)
            if num is None:
                print(f"{lang}: no tracking issue found, skipped")
                continue
            subprocess.run(
                ["gh", "issue", "comment", str(num), "--repo", ENGINE_REPO, "--body", body],
                check=True, capture_output=True,
            )
            print(f"{lang}: commented on #{num} ({'clean' if clean else 'open'})")
        else:
            print(f"\n{'=' * 70}\n{lang}  ->  {'CLEAN' if clean else 'open'}\n{'=' * 70}")
            print(body)
    return 0 if all_clean else 1


if __name__ == "__main__":
    sys.exit(main())
