"""Cross-language bias report: identical planted intent, divergent measurements.

For every language folder with a locked manifest, runs the same end-to-end scan the
verifier uses, then compares three groups of metrics across languages:

  1. every risk_* score the recorder produces (mean per file),
  2. structure found (functions, classes, imports, keyword hits, comment mass, pagerank),
  3. the SPEC's planted signals (corpus totals).

Because the planted intent is identical everywhere, divergence IS measured language
bias. Output: docs/bias_report.md + docs/bias_variance_chart.svg (strip plot, one
unlabeled dot per language per metric, zone-count stamps; regenerated together).
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


def gather(language, colmap):
    """Scan one language folder; return (signal_totals, risk_means, struct_totals)."""
    language_dir = REPO_ROOT / "data" / language
    with tempfile.TemporaryDirectory(prefix=f"rosetta_bias_{language}_") as tmp:
        db_path = vl.scan(language_dir, pathlib.Path(tmp))
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        have = {r[1] for r in conn.execute("PRAGMA table_info(file_data)")}
        sig_cols = [c for c in colmap if c in have]
        risk_cols = sorted(c for c in have if c.startswith("risk_"))
        struct_cols = [c for c in ("function_count", "class_count", "import_count",
                                   "total_loc", "coding_loc", "pagerank_score") if c in have]
        rows = conn.execute(
            f"SELECT {', '.join(sig_cols + risk_cols + struct_cols)} FROM file_data"
        ).fetchall()

    totals = {colmap[c]: 0 for c in sig_cols}
    risks = {c: [] for c in risk_cols}
    struct = {"functions_found": 0, "classes_found": 0, "dependency_links": 0,
              "keyword_hits": 0, "comment_lines": 0, "pagerank": []}
    for row in rows:
        for c in sig_cols:
            totals[colmap[c]] += row[c] or 0
            struct["keyword_hits"] += row[c] or 0
        for c in risk_cols:
            if row[c] is not None:
                risks[c].append(row[c])
        struct["functions_found"] += row["function_count"] or 0
        struct["classes_found"] += row["class_count"] or 0
        struct["dependency_links"] += row["import_count"] or 0
        struct["comment_lines"] += max(0, (row["total_loc"] or 0) - (row["coding_loc"] or 0))
        if "pagerank_score" in row.keys() and row["pagerank_score"] is not None:
            struct["pagerank"].append(row["pagerank_score"])
    risk_means = {c: (statistics.mean(v) if v else None) for c, v in risks.items()}
    struct["pagerank"] = statistics.mean(struct["pagerank"]) if struct["pagerank"] else None
    return totals, risk_means, struct


def _row_stats(values):
    """(devs, green_share, median) for one metric across languages; None if unusable.

    green_share = fraction of languages whose deviation sits inside the green band —
    the metric's cross-language consistency score (one outlier no longer flips a
    binary verdict; it just costs its share)."""
    vals = [v for v in values if v is not None]
    if not vals:
        return None
    med = statistics.median(vals)
    if med <= 0:
        if all(v == 0 for v in vals):
            return ([0.0] * len(vals), 1.0, 0.0) if len(set(vals)) == 1 else None
        return None
    devs = [(v - med) / med for v in vals]
    green_share = sum(1 for d in devs if abs(d) <= GREEN_DEV) / len(devs)
    return devs, green_share, med


def _share_color(share):
    """Rainbow LUT for the consistency badge: anything <=50% is flat red; the
    50-100% range sweeps the hue wheel red -> orange -> yellow -> green, so the
    badge color carries the score even at a squint."""
    import colorsys

    if share <= 0.5:
        hue = 0.0
    else:
        hue = (share - 0.5) / 0.5 * (120 / 360)  # 0deg red -> 120deg green
    r, g, b = colorsys.hls_to_rgb(hue, 0.42, 0.75)
    return f"#{int(r * 255):02x}{int(g * 255):02x}{int(b * 255):02x}"


def write_variance_chart(groups, n_langs):
    """Strip-plot SVG. groups = [(title, {metric: [values-per-language]})].

    One unlabeled dot per language; translucent so overlap darkens; each colored
    zone carries a small count of the dots inside it, so a tight 11-dot (or 40-dot)
    stack reads as a number in the green zone rather than a smudge. Any dot in the
    red zone fails the metric.
    """
    label_w, strip_w, row_h, pad, badge_w = 200, 420, 30, 10, 64
    width = label_w + strip_w + badge_w + pad * 3
    half = strip_w / 2
    px_per_dev = half / 1.1

    def x_of(dev):
        return label_w + pad + half + max(-1.1, min(1.1, dev)) * px_per_dev

    prepared, shares, n_rows, skipped = [], {}, 0, []
    for title, metrics in groups:
        rows = []
        for name, values in metrics.items():
            st = _row_stats(values)
            if st is None:
                skipped.append(name)
                continue
            rows.append((name, *st))
            shares[name] = st[1]
        if rows:
            prepared.append((title, rows))
            n_rows += len(rows)

    height = 60 + sum(24 for _ in prepared) + n_rows * row_h + 14
    s = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'font-family="system-ui, sans-serif" font-size="12">',
        f'<rect width="{width}" height="{height}" fill="#ffffff"/>',
        f'<text x="{pad}" y="20" font-size="14" font-weight="bold" fill="#1a1a1a">'
        f"One program, {n_langs} languages — does GitGalaxy measure it the same everywhere?</text>",
        f'<text x="{pad}" y="36" fill="#666">identical planted code per language · each dot = one '
        f"language's deviation from the cross-language median</text>",
        f'<text x="{pad}" y="50" fill="#666">badge = share of languages inside the green band '
        f"(the metric's consistency score) · red dots mark outliers · small numbers = dots per zone</text>",
    ]
    y = 60
    zone_edges = [(-1.1, -AMBER_DEV, "#f8d7da"), (-AMBER_DEV, -GREEN_DEV, "#fff3cd"),
                  (-GREEN_DEV, GREEN_DEV, "#d4edda"), (GREEN_DEV, AMBER_DEV, "#fff3cd"),
                  (AMBER_DEV, 1.1, "#f8d7da")]
    for title, rows in prepared:
        y += 24
        s.append(f'<text x="{pad}" y="{y - 8}" font-size="12" font-weight="bold" '
                 f'fill="#444" letter-spacing="1">{title.upper()}</text>')
        for name, devs, green_share, med in rows:
            cy = y + row_h / 2
            for lo, hi, color in zone_edges:
                bx, bw = x_of(lo), x_of(hi) - x_of(lo)
                s.append(f'<rect x="{bx:.1f}" y="{y + 4}" width="{bw:.1f}" '
                         f'height="{row_h - 8}" fill="{color}"/>')
            s.append(f'<line x1="{x_of(0):.1f}" y1="{y + 4}" x2="{x_of(0):.1f}" '
                     f'y2="{y + row_h - 4}" stroke="#999" stroke-dasharray="2,2"/>')
            s.append(f'<text x="{pad}" y="{cy + 4}" fill="#1a1a1a">{name}</text>')
            # zone-count stamps, upper corner of each zone
            for lo, hi, _ in zone_edges:
                n = sum(1 for d in devs
                        if (max(-1.1, min(1.1, d)) >= lo if lo != -1.1 else True)
                        and (max(-1.1, min(1.1, d)) < hi if hi != 1.1 else True))
                if n:
                    s.append(f'<text x="{x_of(lo) + 3:.1f}" y="{y + 13}" font-size="9" '
                             f'fill="#555">{n}</text>')
            for d in devs:
                s.append(f'<circle cx="{x_of(d):.1f}" cy="{cy:.1f}" r="4.5" '
                         f'fill="#1f3a5f" fill-opacity="0.3"/>')
            badge_fill = _share_color(green_share)
            bx = label_w + strip_w + pad * 2
            s.append(f'<rect x="{bx}" y="{cy - 10}" width="{badge_w}" height="20" rx="4" fill="{badge_fill}"/>')
            s.append(f'<text x="{bx + badge_w / 2}" y="{cy + 4}" text-anchor="middle" '
                     f'fill="#fff" font-weight="bold" font-size="11">{green_share:.0%}</text>')
            y += row_h
    s.append("</svg>")
    CHART.write_text("\n".join(s) + "\n")
    return shares, skipped


def main():
    languages = sorted(
        p.parent.name for p in (REPO_ROOT / "data").glob("*/expected_signals.json")
    )
    if not languages:
        print("no locked manifests found")
        return 1

    ledger = json.loads((REPO_ROOT / "deviation_ledger.json").read_text())
    open_entries = [e["id"] for e in ledger["entries"] if e["status"] != "validated"]

    colmap = vl._signal_columns()
    all_totals, all_risks, all_struct = {}, {}, {}
    for lang in languages:
        print(f"scanning {lang}...")
        all_totals[lang], all_risks[lang], all_struct[lang] = gather(lang, colmap)

    risk_names = sorted({c for r in all_risks.values() for c in r})
    struct_names = ["functions_found", "classes_found", "dependency_links",
                    "keyword_hits", "comment_lines", "pagerank"]
    groups = [
        ("risk exposure (mean per file)",
         {c: [all_risks[lang].get(c) for lang in languages] for c in risk_names}),
        ("structure found (corpus totals)",
         {c: [all_struct[lang].get(c) for lang in languages] for c in struct_names}),
        ("planted signals (corpus totals)",
         {c: [all_totals[lang].get(c, 0) for lang in languages] for c in PLANTED}),
    ]
    # scan cache: lets findings_report.py (and ad hoc queries) reuse this run
    cache = {"languages": languages, "metrics": {}}
    for _, metrics in groups:
        for name, values in metrics.items():
            cache["metrics"][name] = dict(zip(languages, values))
    (REPO_ROOT / "docs" / "bias_data.json").write_text(
        json.dumps(cache, indent=1) + "\n"
    )

    shares, skipped = write_variance_chart(groups, len(languages))
    avg_share = statistics.mean(shares.values()) if shares else 0
    n_strong = sum(1 for v in shares.values() if v >= 0.8)
    weakest = sorted(shares.items(), key=lambda kv: kv[1])[:5]

    lines = [
        "# Cross-Language Bias Report",
        "",
        f"Generated by `tools/bias_report.py` over {len(languages)} locked language(s): "
        + ", ".join(languages) + ".",
        "",
        "Planted intent is identical in every language (SPEC.md probe table), so any "
        "column-to-column divergence below is measured language bias — an extraction "
        "inequality or a scoring inequality. Every known deviation is validated in "
        "`deviation_ledger.json`; see per-language `expected_signals.json` notes for "
        "the shape-by-shape accounting.",
        "",
    ]
    if open_entries:
        lines += [f"**WARNING: unvalidated ledger entries present: {open_entries} — "
                  "treat this report as provisional (docs/GATING.md).**", ""]

    lines += ["## Cross-language variance chart", "",
              "![variance chart](bias_variance_chart.svg)", "",
              f"Each metric's badge is its **consistency score**: the share of languages "
              f"inside the green band (±{GREEN_DEV:.0%} of the cross-language median). "
              f"**Average across {len(shares)} metrics: {avg_share:.0%}**; "
              f"{n_strong} metrics hold ≥80% of languages in the green band. "
              f"Weakest metrics: "
              + ", ".join(f"{k} {v:.0%}" for k, v in weakest) + ". "
              + (f"Skipped (no comparable data): {', '.join(skipped)}." if skipped else ""),
              ""]

    lines += ["## Signal totals vs. planted intent", "",
              "| signal | planted | " + " | ".join(languages) + " |",
              "|---|---|" + "---|" * len(languages)]
    for sig, want in PLANTED.items():
        vals = [all_totals[lang].get(sig, 0) for lang in languages]
        mark = " ⚠" if (len(set(vals)) > 1 or any(v != want for v in vals)) else ""
        lines.append(f"| {sig}{mark} | {want} | " + " | ".join(str(v) for v in vals) + " |")

    lines += ["", "## Structure found (corpus totals)", "",
              "| metric | " + " | ".join(languages) + " |",
              "|---|" + "---|" * len(languages)]
    for name in struct_names:
        vals = []
        for lang in languages:
            v = all_struct[lang].get(name)
            vals.append("—" if v is None else (f"{v:.4f}" if isinstance(v, float) else str(v)))
        lines.append(f"| {name} | " + " | ".join(vals) + " |")

    lines += ["", "## Mean per-file risk scores", "",
              "| risk | " + " | ".join(languages) + " |",
              "|---|" + "---|" * len(languages)]
    for col in risk_names:
        vals = []
        for lang in languages:
            v = all_risks[lang].get(col)
            vals.append("—" if v is None else f"{v:.3f}")
        lines.append(f"| {col} | " + " | ".join(vals) + " |")

    lines += ["", "A risk-score spread on identical intent is the bottom-line bias number: "
              "same program, different measured risk, purely from language expression "
              "plus the ledgered engine behaviors.", ""]

    OUT.write_text("\n".join(lines))
    print(f"wrote {OUT.relative_to(REPO_ROOT)} and {CHART.relative_to(REPO_ROOT)}")
    print(f"consistency: avg {avg_share:.0%} across {len(shares)} metrics; "
          f"{n_strong} at >=80% green-band share")

    import findings_report
    findings_report.generate()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
