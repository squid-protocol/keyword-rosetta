"""Cross-language bias report: identical planted intent, divergent measurements.

For every language folder with a locked manifest, runs the same end-to-end scan the
verifier uses, then compares (a) per-signal corpus totals against the SPEC's planted
intent and (b) downstream per-file risk scores across languages. Because the planted
intent is identical everywhere, divergence IS measured language bias — either an
extraction inequality or a scoring inequality.

Usage:
    python tools/bias_report.py            # writes docs/bias_report.md
"""

import json
import pathlib
import sqlite3
import statistics
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import verify_language as vl

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = REPO_ROOT / "docs" / "bias_report.md"
CHART = REPO_ROOT / "docs" / "bias_variance_chart.svg"

# Acceptance thresholds on relative deviation from the cross-language median.
GREEN_DEV = 0.25   # within ±25% of median: acceptable clustering
AMBER_DEV = 0.50   # within ±50%: caution
# beyond ±50%: red zone — any dot here fails the metric's cross-language validation

# SPEC.md probe table: what every language plants, before any engine semantics.
PLANTED = {
    "branch": 3, "io": 3, "high_risk_execution": 2, "globals": 2, "test": 2,
    "safety": 2, "safety_bypasses": 2, "telemetry": 2, "state_mutation": 2,
    "cleanup": 2, "fragile_debt": 1, "planned_debt": 1, "import": 3,
    "func_start": 13, "args": 13, "class_start": 0, "doc": 1, "ownership": 1,
}

RISK_COLS = [
    "risk_cognitive_load", "risk_safety_score", "risk_tech_debt",
    "risk_api_exposure", "risk_dead_code",
]


def gather(language):
    language_dir = REPO_ROOT / "data" / language
    colmap = vl._signal_columns()
    with tempfile.TemporaryDirectory(prefix=f"rosetta_bias_{language}_") as tmp:
        db_path = vl.scan(language_dir, pathlib.Path(tmp))
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        have = {r[1] for r in conn.execute("PRAGMA table_info(file_data)")}
        sig_cols = [c for c in colmap if c in have]
        risk_cols = [c for c in RISK_COLS if c in have]
        rows = conn.execute(
            f"SELECT file_name, {', '.join(sig_cols + risk_cols)} FROM file_data"
        ).fetchall()
    totals = {colmap[c]: 0 for c in sig_cols}
    risks = {c: [] for c in risk_cols}
    for row in rows:
        for c in sig_cols:
            totals[colmap[c]] += row[c] or 0
        for c in risk_cols:
            if row[c] is not None:
                risks[c].append(row[c])
    return totals, {c: (statistics.mean(v) if v else None) for c, v in risks.items()}


def write_variance_chart(all_risks, languages):
    """Compact strip-plot SVG: one row per risk metric, one unlabeled dot per language.

    Dots are positioned by relative deviation from the cross-language median.
    Tight clustering in the green band = the metric measures languages equivalently;
    any dot in the red zone (>±50% deviation) fails that metric's cross-language
    validation. Regenerated on every bias_report run, like the tri-comparison chart.
    """
    rows = []
    for col in RISK_COLS:
        vals = [all_risks[lang].get(col) for lang in languages]
        vals = [v for v in vals if v is not None]
        med = statistics.median(vals) if vals else 0
        if not vals or med <= 0:
            rows.append((col, med, [], "NO DATA"))
            continue
        devs = [(v - med) / med for v in vals]
        worst = max(abs(d) for d in devs)
        verdict = "PASS" if worst <= GREEN_DEV else ("WARN" if worst <= AMBER_DEV else "FAIL")
        rows.append((col, med, devs, verdict))

    label_w, strip_w, row_h, pad = 200, 420, 34, 10
    badge_w = 64
    width = label_w + strip_w + badge_w + pad * 3
    height = row_h * len(rows) + 58
    half = strip_w / 2
    px_per_dev = half / 1.1  # x-scale: ±110% deviation spans the strip; beyond clamps

    def x_of(dev):
        return label_w + pad + half + max(-1.1, min(1.1, dev)) * px_per_dev

    s = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'font-family="system-ui, sans-serif" font-size="12">',
        f'<rect width="{width}" height="{height}" fill="#ffffff"/>',
        f'<text x="{pad}" y="20" font-size="14" font-weight="bold" fill="#1a1a1a">'
        "Cross-language variance — identical planted intent</text>",
        f'<text x="{pad}" y="36" fill="#666">each dot = one language · deviation from the '
        f"cross-language median · green ±{GREEN_DEV:.0%} · red beyond ±{AMBER_DEV:.0%}</text>",
    ]
    y0 = 48
    for i, (col, med, devs, verdict) in enumerate(rows):
        y = y0 + i * row_h
        cy = y + row_h / 2
        sx = label_w + pad
        # zone bands: red base, amber, green center
        s.append(f'<rect x="{sx}" y="{y + 6}" width="{strip_w}" height="{row_h - 12}" fill="#f8d7da"/>')
        for lo, hi, color in ((-AMBER_DEV, AMBER_DEV, "#fff3cd"), (-GREEN_DEV, GREEN_DEV, "#d4edda")):
            bx, bw = x_of(lo), x_of(hi) - x_of(lo)
            s.append(f'<rect x="{bx:.1f}" y="{y + 6}" width="{bw:.1f}" height="{row_h - 12}" fill="{color}"/>')
        s.append(f'<line x1="{x_of(0):.1f}" y1="{y + 6}" x2="{x_of(0):.1f}" y2="{y + row_h - 6}" stroke="#999" stroke-dasharray="2,2"/>')
        s.append(f'<text x="{pad}" y="{cy + 4}" fill="#1a1a1a">{col}</text>')
        for d in devs:
            s.append(f'<circle cx="{x_of(d):.1f}" cy="{cy:.1f}" r="5" fill="#1f3a5f" fill-opacity="0.55"/>')
        badge_fill = {"PASS": "#28a745", "WARN": "#d39e00", "FAIL": "#dc3545", "NO DATA": "#6c757d"}[verdict]
        bx = label_w + strip_w + pad * 2
        s.append(f'<rect x="{bx}" y="{cy - 10}" width="{badge_w}" height="20" rx="4" fill="{badge_fill}"/>')
        s.append(f'<text x="{bx + badge_w / 2}" y="{cy + 4}" text-anchor="middle" fill="#fff" font-weight="bold" font-size="11">{verdict}</text>')
    s.append("</svg>")
    CHART.write_text("\n".join(s) + "\n")
    return {col: verdict for col, _, _, verdict in rows}


def main():
    languages = sorted(
        p.parent.name for p in (REPO_ROOT / "data").glob("*/expected_signals.json")
    )
    if not languages:
        print("no locked manifests found")
        return 1

    ledger = json.loads((REPO_ROOT / "deviation_ledger.json").read_text())
    open_entries = [e["id"] for e in ledger["entries"] if e["status"] != "validated"]

    all_totals, all_risks = {}, {}
    for lang in languages:
        print(f"scanning {lang}...")
        all_totals[lang], all_risks[lang] = gather(lang)

    lines = [
        "# Cross-Language Bias Report",
        "",
        f"Generated by `tools/bias_report.py` over {len(languages)} locked language(s): "
        + ", ".join(languages) + ".",
        "",
        "Planted intent is identical in every language (SPEC.md probe table), so any "
        "column-to-column divergence below is measured language bias — an extraction "
        "inequality (signal table) or a scoring inequality (risk table). Every known "
        "deviation is validated in `deviation_ledger.json`; see per-language "
        "`expected_signals.json` notes for the shape-by-shape accounting.",
        "",
    ]
    if open_entries:
        lines += [f"**WARNING: unvalidated ledger entries present: {open_entries} — "
                  "treat this report as provisional (docs/GATING.md).**", ""]

    lines += ["## Signal totals vs. planted intent", "",
              "| signal | planted | " + " | ".join(languages) + " |",
              "|---|---|" + "---|" * len(languages)]
    divergent = []
    for sig, want in PLANTED.items():
        vals = [all_totals[lang].get(sig, 0) for lang in languages]
        mark = ""
        if len(set(vals)) > 1 or any(v != want for v in vals):
            mark = " ⚠"
            divergent.append(sig)
        lines.append(f"| {sig}{mark} | {want} | " + " | ".join(str(v) for v in vals) + " |")

    verdicts = write_variance_chart(all_risks, languages)
    lines += ["", "## Cross-language variance chart", "",
              "![variance chart](bias_variance_chart.svg)", "",
              "One dot per language, positioned by deviation from the cross-language median. "
              "A metric is cross-language **validated** only when no dot sits in the red zone "
              f"(>±{AMBER_DEV:.0%}): " + ", ".join(f"{c} **{v}**" for c, v in verdicts.items()) + ".", ""]

    lines += ["", "## Mean per-file risk scores", "",
              "| risk | " + " | ".join(languages) + " |",
              "|---|" + "---|" * len(languages)]
    for col in RISK_COLS:
        vals = []
        for lang in languages:
            v = all_risks[lang].get(col)
            vals.append("—" if v is None else f"{v:.3f}")
        lines.append(f"| {col} | " + " | ".join(vals) + " |")

    lines += ["", f"**Signals diverging from uniform planted intent: "
              f"{len(divergent)}/{len(PLANTED)}** — {', '.join(divergent) if divergent else 'none'}.",
              "",
              "A risk-score spread on identical intent is the bottom-line bias number: "
              "same program, different measured risk, purely from language expression "
              "plus the ledgered engine behaviors.", ""]

    OUT.write_text("\n".join(lines))
    print(f"wrote {OUT.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
