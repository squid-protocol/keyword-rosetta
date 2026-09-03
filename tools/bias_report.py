"""Cross-language bias report: identical planted intent, divergent measurements.

For every language folder with a locked manifest, runs the same end-to-end scan the
verifier uses, then compares three groups of metrics across languages:

  1. every risk_* score the recorder produces (mean per file),
  2. structure found (functions, classes, imports, keyword hits, comment mass, pagerank),
  3. the SPEC's planted signals (corpus totals).

Because the planted intent is identical everywhere, divergence IS measured language
bias. Output: docs/bias_report.md + docs/bias_variance_chart.svg (strip plot, one
unlabeled dot per language per metric, zone-count stamps; regenerated together).

MUST run against a full-precision engine. In Zero-Dependency Mode (any of networkx /
tiktoken / numpy-ML / pyyaml missing) the recorder nulls every network metric, so
pagerank vanishes from the comparison with no error and no note -- two reports then
differ by a whole column for reasons nothing in them explains. The mode is read from
the scan DB's repo_data.is_zero_dependency_mode, recorded in docs/bias_data.json as
`engine_mode`, stamped in the report header, and aborts the run unless
--allow-zero-dependency is passed:

    GALAXYSCOPE_BIN=<gitgalaxy>/.crucible_venvs/full_precision/bin/galaxyscope \
        python tools/bias_report.py
"""

import collections
import json
import math
import pathlib
import sqlite3
import statistics
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import verify_language as vl
from _registry import (
    load_definitions,
    registry_signals,
    risk_dependencies,
    unmeasurable_signals,
)

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = REPO_ROOT / "docs" / "bias_report.md"
CHART = REPO_ROOT / "docs" / "bias_variance_chart.svg"

# Acceptance thresholds on relative deviation from the cross-language median.
GREEN_DEV = 0.25   # within ±25% of median: acceptable clustering
AMBER_DEV = 0.50   # within ±50%: caution
# beyond ±50%: red zone — any dot here fails the metric's cross-language validation

# Engine measures beyond the planted signals, reported as means per file. These are
# derived descriptions of the SAME program -- topology, shape, size, complexity -- so
# identical planted intent should produce identical values, exactly the argument that
# already justified pagerank. They were being computed on every scan and thrown away.
#
# Deliberately NOT included: the other ~77 signal columns (pointers, macros, generics,
# decorators, the sec_* family, ...). The SPEC probe table does not plant those, so a
# C-vs-Python divergence in `pointers` is language expression, not measurement bias --
# scoring it would fill the report with divergence that means nothing. If a signal
# should be comparable, the fix is to plant it in SPEC.md and add it to PLANTED, not
# to score it unplanted.
MEASURE_COLS = [
    # network topology (NULL in Zero-Dependency Mode -- hence the mode guard)
    "pagerank_score",
    "normalized_blast_radius",
    "betweenness_score",
    "closeness_score",
    "producer_ratio",
    # size and shape
    "total_loc",
    "coding_loc",
    "structural_mass",
    "token_mass",
    "control_flow_ratio",
    # function-level morphology
    "avg_func_loc",
    "avg_func_complexity",
    "max_func_complexity",
    "avg_func_args",
    "func_complexity_gini",
    "func_internal_density",
    # graph and encapsulation shape
    "dependency_density",
    "encapsulation_ratio",
    "popularity",
    "cog_raw",
    # Inputs the risk_* formulas read that this report previously scored the
    # OUTPUT of without ever measuring. `risk_documentation` and
    # `risk_api_exposure` depend on api/encapsulation, and `risk_tech_debt` on
    # orphaned/duplicate logic -- so 46 out-of-band risk cells could not be
    # attributed to an upstream deviation even in principle, the same structural
    # gap `control_flow_ratio` has with its unplanted denominator.
    #
    # The RAW (pre-adjustment) columns are deliberate: galaxyscope's Contextual
    # Baseline Fix rewrites api and orphaned_logic in place for any file with
    # popularity > 0, so the adjusted values carry the DAG's bias into a column
    # meant to measure extraction. #2536 added these snapshots for exactly this
    # consumer.
    "raw_arch_api",
    "raw_state_slop_orphans",
    "def_encapsulation",
    "state_slop_duplicates",
]

# SPEC.md probe table: what every language plants, before any engine semantics.
PLANTED = {
    "branch": 3, "io": 3, "high_risk_execution": 2, "globals": 2, "test": 2,
    "safety": 2, "safety_bypasses": 2, "telemetry": 2, "state_mutation": 2,
    "cleanup": 2, "fragile_debt": 1, "planned_debt": 1, "import": 3,
    "func_start": 13, "args": 13, "class_start": 0, "doc": 1, "ownership": 1,
}


def gather(language, colmap):
    """Scan one language: (signals, risk_means, struct, measure_means, zero_dep)."""
    language_dir = REPO_ROOT / "data" / language
    # rosetta#25: the scan sweeps the whole folder, so expected_signals.json
    # itself lands in file_data and its generically-parsed hits used to inflate
    # every aggregate (28% of haskell's keyword_hits came from its own
    # manifest). Restrict the census to exactly the shell files the manifest
    # defines — that also drops any future stray non-source file, and keeps
    # the aggregates aligned with what verify_language.py actually gates.
    shell_files = set(
        json.loads((language_dir / "expected_signals.json").read_text()).get("files", {})
    )
    with tempfile.TemporaryDirectory(prefix=f"rosetta_bias_{language}_") as tmp:
        db_path = vl.scan(language_dir, pathlib.Path(tmp))
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        have = {r[1] for r in conn.execute("PRAGMA table_info(file_data)")}
        sig_cols = [c for c in colmap if c in have]
        risk_cols = sorted(c for c in have if c.startswith("risk_"))
        struct_cols = [c for c in ("function_count", "class_count", "import_count",
                                   "total_loc", "coding_loc", "doc_loc", "pagerank_score") if c in have]
        measure_cols = [c for c in MEASURE_COLS if c in have and c not in struct_cols]
        rows = conn.execute(
            "SELECT file_name, "
            + ", ".join(sig_cols + risk_cols + struct_cols + measure_cols)
            + " FROM file_data"
        ).fetchall()
        rows = [r for r in rows if r["file_name"] in shell_files]
        # Which mode the engine actually ran in, straight from the recorder rather
        # than inferred. Zero-Dependency Mode (any of networkx/tiktoken/numpy-ML/
        # pyyaml missing) nulls every network metric, so pagerank silently drops
        # out of the comparison -- a whole column vanishing with no error and no
        # note in the report. verify.yml installs all six for exactly this reason.
        zero_dep = bool(
            (conn.execute("SELECT is_zero_dependency_mode FROM repo_data").fetchone() or [0])[0]
        )

    totals = {colmap[c]: 0 for c in sig_cols}
    risks = {c: [] for c in risk_cols}
    measures = {c: [] for c in MEASURE_COLS}
    struct = {"functions_found": 0, "classes_found": 0, "dependency_links": 0,
              "keyword_hits": 0, "comment_lines": 0, "pagerank": []}
    for row in rows:
        for c in sig_cols:
            totals[colmap[c]] += row[c] or 0
            struct["keyword_hits"] += row[c] or 0
        for c in risk_cols:
            if row[c] is not None:
                risks[c].append(row[c])
        for c in measures:
            if c in row.keys() and row[c] is not None:
                measures[c].append(row[c])
        struct["functions_found"] += row["function_count"] or 0
        struct["classes_found"] += row["class_count"] or 0
        struct["dependency_links"] += row["import_count"] or 0
        # gitgalaxy#2625: prefer prism's real doc_loc (non-blank, non-code
        # lines), persisted since gitgalaxy PR #2632. The old proxy
        # total_loc - coding_loc silently counted every BLANK line as
        # documentation (total_loc is blank-inclusive, coding_loc is not),
        # biasing comment_lines toward languages whose shells simply use
        # more blank-line spacing. Fallback kept only for pre-#2632 engines.
        if "doc_loc" in row.keys():
            struct["comment_lines"] += row["doc_loc"] or 0
        else:
            struct["comment_lines"] += max(0, (row["total_loc"] or 0) - (row["coding_loc"] or 0))
        if "pagerank_score" in row.keys() and row["pagerank_score"] is not None:
            struct["pagerank"].append(row["pagerank_score"])
    risk_means = {c: (statistics.mean(v) if v else None) for c, v in risks.items()}
    measure_means = {c: (statistics.mean(v) if v else None) for c, v in measures.items()}
    struct["pagerank"] = statistics.mean(struct["pagerank"]) if struct["pagerank"] else None
    return totals, risk_means, struct, measure_means, zero_dep


def _row_stats(values):
    """(devs, share, median, basis) for one metric across languages; None if unusable.

    `share` is the metric's cross-language consistency score (one outlier no longer
    flips a binary verdict; it just costs its share). `basis` says what it measures:
    "band" = fraction inside ±GREEN_DEV of a positive median; "agreement" = fraction
    exactly ON a zero median, the only meaningful reading when a relative deviation
    would divide by zero. Returns None only when the row is unusable: no values at
    all, or inert (every language records 0, so nothing was asked)."""
    vals = [v for v in values if v is not None]
    if not vals:
        return None
    med = statistics.median(vals)
    if med <= 0:
        # All-zero used to score a free 1.0 ("every language agrees"). It does not:
        # a metric that records nothing anywhere asked no cross-language question,
        # and badging it 100% inflated the headline average. Dropped as inert.
        if all(v == 0 for v in vals):
            return None
        # Zero median with disagreement is the interesting case, and it used to be
        # dropped entirely -- hiding real bias. Relative deviation is undefined
        # against a 0 median, but exact agreement is not: score the share of
        # languages sitting ON the median and push every disagreeing language
        # off-scale, where the chart reads it as red. class_start is the worked
        # example: planted 0 everywhere, yet 6 languages report 1-7.
        devs = [0.0 if v == med else math.copysign(1.0, v - med) for v in vals]
        return devs, sum(1 for v in vals if v == med) / len(vals), med, "agreement"
    devs = [(v - med) / med for v in vals]
    green_share = sum(1 for d in devs if abs(d) <= GREEN_DEV) / len(devs)
    return devs, green_share, med, "band"


def is_inert(values):
    """True when every comparable language records exactly 0 for this metric.

    Not a consistency result -- an inert metric asked no cross-language question
    (risk_churn is a hardcoded 0.0 in the risk assembly; risk_secrets_risk needs
    sec_* signals no corpus shell plants). Reported separately from rows that are
    merely median-less.
    """
    vals = [v for v in values if v is not None]
    return bool(vals) and all(v == 0 for v in vals)


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


def classify_na(ledger_entries, na_map):
    """{signal: {lang: "ledgered"|"unreviewed"}} for every unmeasurable cell.

    "ledgered" = a validated deviation-ledger entry names this language AND this
    signal (its `signal` field is a |-separated list), recording WHY the language
    lacks the concept. "unreviewed" = rule absent but nobody has recorded why --
    possibly correct morphology, possibly the next jcl-safety-style gap
    (gitgalaxy#2610); flagged loudly rather than quietly excused.
    """
    validated = [e for e in ledger_entries if e.get("status") == "validated"]
    out = {}
    for lang, sigs in na_map.items():
        for sig in sigs:
            covered = any(
                lang in e.get("languages_seen", [])
                and sig in (e.get("signal") or "").split("|")
                for e in validated
            )
            out.setdefault(sig, {})[lang] = "ledgered" if covered else "unreviewed"
    return out


# ==============================================================================
# E.1 (gitgalaxy#2669): WHEN IS AN OUT-OF-BAND CELL "EXPLAINED"?
# ==============================================================================
# An out-of-band cell is not automatically a defect. gitgalaxy#2689's measurement
# of the shape-descriptor family found three mechanisms that make a red or amber
# cell already-accounted-for, and only what survives all three is a real finding.
# The epic's close criterion is "no UNEXPLAINED out-of-band cells", not "no
# out-of-band cells", so this is what the gate has to count.

# Descriptors that divide by the function count. When a language has no functions
# at all the quotient is undefined, not deviant -- markdown and html record
# functions_found = 0 and every one of these lands red against a median built from
# languages that do have functions. docs/GATING.md already draws this line one
# layer over: a cell is n/a BECAUSE the rule is None.
PER_FUNCTION_METRICS = frozenset({
    "avg_func_complexity",
    "avg_func_loc",
    "avg_func_args",
    "max_func_complexity",
    "func_complexity_gini",
    "func_internal_density",
})

# Composite metrics and the measured inputs they are built from, so a deviation
# that entered through an input is not counted a second time as its own finding.
# Sources, so this stays checkable against the engine rather than drifting:
#   control_flow_ratio  detector.py  ~L1288  branch / (branch + structural_boundaries)
#   cog_raw             signal_processor.py ~L800  ((branch+1) * sqrt(args+1)
#                                                   + 0.05 * min(loc, (signals+1)*10)) * 10
#   the avg_/max_/gini/density family  per-function aggregates of the same inputs
# NOTE (gitgalaxy#2689 bucket B): control_flow_ratio's other input,
# structural_boundaries, is not in this table because the corpus never plants,
# gates or reports it -- which is exactly why that metric cannot be validated
# here yet. It is listed with the one input the corpus does control.
DERIVED_INPUTS = {
    "control_flow_ratio": ("branch",),
    # `_calc_cog_load` (signal_processor.py ~L1357) reads branch, state_mutation
    # (as flux_density), concurrency, reflection_metaprogramming (as
    # heat_density), LOC and func_gini. The first cut of this table listed only
    # branch/args/LOC and so left matlab's cog_raw unexplained once the
    # synthetic-bucket entry retired -- matlab's state_mutation is +1150% (the
    # gitgalaxy#2654 return-convention shape), which is precisely an input
    # deviation this table exists to attribute.
    "cog_raw": (
        "branch", "state_mutation", "concurrency", "reflection_metaprogramming",
        "total_loc", "coding_loc", "func_complexity_gini",
    ),
    # `file_mass` (~L820), recorded as `file_impact` and read here as
    # structural_mass: sum(per-function impacts) + api + concurrency +
    # state_mutation + loc/50.
    "structural_mass": (
        "branch", "args", "api", "concurrency", "state_mutation",
        "total_loc", "coding_loc", "func_start",
    ),
    "avg_func_complexity": ("branch", "func_start"),
    "max_func_complexity": ("branch", "func_start"),
    "func_complexity_gini": ("branch", "func_start"),
    "avg_func_loc": ("total_loc", "coding_loc", "func_start"),
    "avg_func_args": ("args", "func_start"),
    "func_internal_density": ("branch", "args", "func_start"),
}


# The risk formulas name their inputs with registry signal names; the recorder
# stores several of them under different column names, and for two the RAW
# pre-adjustment snapshot is the honest one to compare (see MEASURE_COLS).
# Without this map the derivation edges below silently never match.
RISK_INPUT_COLUMNS = {
    "api": "raw_arch_api",
    "encapsulation": "def_encapsulation",
    "orphaned_logic": "raw_state_slop_orphans",
    "duplicate_logic": "state_slop_duplicates",
}


def out_of_band_cells(metrics, languages):
    """{(metric, lang)} for every comparable cell outside the green band.

    Mirrors _row_stats' banding: a zero median is scored on exact agreement, so a
    nonzero value there is out of band and everything else is in.
    """
    out = set()
    for metric, values in metrics.items():
        nums = [v for v in (values.get(lang) for lang in languages) if isinstance(v, (int, float))]
        if not nums:
            continue
        med = statistics.median(nums)
        for lang in languages:
            v = values.get(lang)
            if not isinstance(v, (int, float)):
                continue
            if med == 0:
                if v != 0:
                    out.add((metric, lang))
            elif abs((v - med) / med) > GREEN_DEV:
                out.add((metric, lang))
    return out


def explain_out_of_band(metrics, languages, ledger_entries, structure, risk_inputs=None):
    """{(metric, lang): (status, detail)} for every out-of-band cell.

    status is one of:
      "undefined"   -- a per-function descriptor for a language with no functions
      "ledgered"    -- a validated ledger entry names this language AND this metric
      "derived"     -- a composite whose deviation entered through an input that is
                       itself out of band for this language. For the risk_*
                       family the edges come from `risk_inputs`, read off the
                       engine's own risk assembly by `_registry.risk_dependencies`
                       rather than hand-listed -- the epic has always treated
                       these as downstream shadows in prose ("re-baselines as
                       upstream fixes land"); this is that statement made
                       machine-checkable. A hand-written table went stale within
                       a day (see DERIVED_INPUTS' own history), which is the
                       argument for deriving these from the engine.
      "unexplained" -- survived all three; the only kind the gate fails on
    """
    validated = [e for e in ledger_entries if e.get("status") == "validated"]
    oob = out_of_band_cells(metrics, languages)
    verdicts = {}
    for metric, lang in sorted(oob):
        funcs = (structure.get("functions_found") or {}).get(lang)
        if metric in PER_FUNCTION_METRICS and funcs == 0:
            verdicts[(metric, lang)] = ("undefined", "language records no functions")
            continue
        named = [
            e["id"] for e in validated
            if lang in e.get("languages_seen", [])
            and metric in (e.get("signal") or "").split("|")
        ]
        if named:
            verdicts[(metric, lang)] = ("ledgered", ", ".join(named))
            continue
        edges = DERIVED_INPUTS.get(metric)
        if edges is None and risk_inputs:
            spec = risk_inputs.get(metric, {})
            # `engine` inputs (orphaned_logic, duplicate_logic, the sec_* family)
            # are synthesized downstream of the registry, so a None rule cannot
            # pin them -- but they are still real inputs, and two of them are now
            # measured columns, so they belong in the derivation edges.
            edges = tuple(
                RISK_INPUT_COLUMNS.get(i, i)
                for i in (*spec.get("governed", ()), *spec.get("engine", ()))
            )
        inherited = [i for i in (edges or ()) if (i, lang) in oob]
        if inherited:
            verdicts[(metric, lang)] = ("derived", "inherits " + ", ".join(inherited))
            continue
        verdicts[(metric, lang)] = ("unexplained", "")
    return verdicts


def unmeasurable_risk_cells(deps, definitions, observed):
    """n/a cells among the DERIVED risk_* metrics, plus the mismatches found.

    The planted signals get n/a straight off the registry: no rule, no nonzero,
    incomparable (docs/GATING.md). The risk_* columns are one step downstream --
    formulas over those same signals -- and had no n/a mechanism at all, so a
    language whose inputs are structurally absent was scored as a -100% outlier
    against languages that actually measured something.

    A risk metric is n/a for a language only when ALL FOUR hold:

      1. its formula consumes at least one registry-governed signal;
      2. every one of those signals has a None rule for that language;
      3. it consumes no engine-derived input (orphaned_logic, duplicate_logic,
         the sec_* family) that can be nonzero regardless of the registry;
      4. the observed value really is 0 -- the scan confirming that 1-3 pinned it.

    (4) is what keeps this from becoming a rug in the other direction. Rule
    absence alone is NOT sufficient for a derived metric, because these formulas
    also read structure the registry does not govern (loc, doc_lines, the call
    graph, popularity). A cell that passes 1-3 but measures nonzero anyway is
    returned as a *mismatch* and left comparable: it means this dependency map
    is incomplete, or the engine synthesizes the input downstream of the registry
    the way orphan conversion synthesizes `api` (ledger:
    api-contextual-baseline-fix). Mismatches are printed loudly, never absorbed.

    Returns ({language: sorted [risk metric]}, [(language, metric, observed)]).
    """
    rules = {lang: d.get("rules") or {} for lang, d in definitions.items()}
    na, mismatches = {}, []
    for metric, dep in sorted(deps.items()):
        governed, engine = dep["governed"], dep["engine"]
        if not governed or engine:
            continue
        for lang, values in sorted(observed.items()):
            if lang not in rules or metric not in values:
                continue
            if any(rules[lang].get(sig) is not None for sig in governed):
                continue
            value = values[metric]
            if value:
                mismatches.append((lang, metric, value))
            else:
                na.setdefault(lang, []).append(metric)
    return {k: sorted(v) for k, v in na.items()}, mismatches


def na_audit_signals(deps):
    """Every signal whose absence the n/a governance has to have an opinion about.

    The planted 18, plus the extra inputs read by the risk formulas that can
    actually qualify for a derived n/a. Formulas blocked by an engine-synthesized
    input (risk_tech_debt, risk_secrets_risk) are excluded on purpose: their
    absences can never make a cell incomparable, so demanding a ledger entry for
    `llm_api` in the 40 languages that do not define it would be review theatre.
    """
    extra = {
        sig
        for dep in deps.values()
        if dep["governed"] and not dep["engine"]
        for sig in dep["governed"]
    }
    return sorted(set(PLANTED) | extra)


def classify_risk_na(risk_na, deps, signal_na_state):
    """{metric: {lang: "ledgered"|"unreviewed"}} for derived n/a cells.

    A derived n/a is a mechanical consequence of its input signals' absences, so
    it inherits their review status rather than opening a parallel backlog: the
    cell is "ledgered" only when EVERY governed input is itself ledgered for that
    language. An input nobody has reviewed keeps the derived cell loud too --
    GATING.md rule 2, composed. `signal_na_state` is classify_na()'s output.
    """
    out = {}
    for lang, metrics in risk_na.items():
        for metric in metrics:
            covered = all(
                signal_na_state.get(sig, {}).get(lang) == "ledgered"
                for sig in deps[metric]["governed"]
            )
            out.setdefault(metric, {})[lang] = "ledgered" if covered else "unreviewed"
    return out


def write_variance_chart(groups, n_langs, na_by_metric=None):
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

    prepared, shares, n_rows, skipped, inert, agreement = [], {}, 0, [], [], []
    for title, metrics in groups:
        rows = []
        for name, values in metrics.items():
            st = _row_stats(values)
            if st is None:
                (inert if is_inert(values) else skipped).append(name)
                continue
            rows.append((name, *st))
            shares[name] = st[1]
            if st[3] == "agreement":
                agreement.append(name)
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
        f"(the metric's consistency score) · red dots mark outliers · small numbers = dots per zone"
        f" · n/a = languages whose registry defines no rule for the signal (incomparable, excluded)</text>",
    ]
    na_by_metric = na_by_metric or {}
    y = 60
    zone_edges = [(-1.1, -AMBER_DEV, "#f8d7da"), (-AMBER_DEV, -GREEN_DEV, "#fff3cd"),
                  (-GREEN_DEV, GREEN_DEV, "#d4edda"), (GREEN_DEV, AMBER_DEV, "#fff3cd"),
                  (AMBER_DEV, 1.1, "#f8d7da")]
    for title, rows in prepared:
        y += 24
        s.append(f'<text x="{pad}" y="{y - 8}" font-size="12" font-weight="bold" '
                 f'fill="#444" letter-spacing="1">{title.upper()}</text>')
        for name, devs, green_share, med, basis in rows:
            cy = y + row_h / 2
            for lo, hi, color in zone_edges:
                bx, bw = x_of(lo), x_of(hi) - x_of(lo)
                s.append(f'<rect x="{bx:.1f}" y="{y + 4}" width="{bw:.1f}" '
                         f'height="{row_h - 8}" fill="{color}"/>')
            s.append(f'<line x1="{x_of(0):.1f}" y1="{y + 4}" x2="{x_of(0):.1f}" '
                     f'y2="{y + row_h - 4}" stroke="#999" stroke-dasharray="2,2"/>')
            label = name if basis == "band" else f"{name} ‖"
            s.append(f'<text x="{pad}" y="{cy + 4}" fill="#1a1a1a">{label}</text>')
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
            n_na = len(na_by_metric.get(name, {}))
            if n_na:
                s.append(f'<text x="{label_w + strip_w + pad - 3:.1f}" y="{y + 13}" '
                         f'font-size="9" fill="#888" text-anchor="end">n/a {n_na}</text>')
            badge_fill = _share_color(green_share)
            bx = label_w + strip_w + pad * 2
            s.append(f'<rect x="{bx}" y="{cy - 10}" width="{badge_w}" height="20" rx="4" fill="{badge_fill}"/>')
            s.append(f'<text x="{bx + badge_w / 2}" y="{cy + 4}" text-anchor="middle" '
                     f'fill="#fff" font-weight="bold" font-size="11">{green_share:.0%}</text>')
            y += row_h
    s.append("</svg>")
    CHART.write_text("\n".join(s) + "\n")
    return shares, skipped, inert, agreement


def main():
    # The report is only comparable to itself if every run measures the same engine.
    # Full precision is the contract (AGENTS.md, and verify.yml installs all six deps);
    # the escape hatch exists so a degraded engine can still be investigated on purpose.
    allow_zero_dependency = "--allow-zero-dependency" in sys.argv
    # E.1: the epic close criterion. Off by default so a routine regen still
    # writes its artifacts and exits 0; CI and the epic gate pass --gate.
    gate = "--gate" in sys.argv
    languages = sorted(
        p.parent.name for p in (REPO_ROOT / "data").glob("*/expected_signals.json")
    )
    if not languages:
        print("no locked manifests found")
        return 1

    ledger = json.loads((REPO_ROOT / "deviation_ledger.json").read_text())
    open_entries = [e["id"] for e in ledger["entries"] if e["status"] != "validated"]

    # n/a (incomparable) cells: the language's registry defines no rule for the
    # signal, so a 0 there means "not expressible as measured", not "missed".
    definitions = load_definitions()
    na_map = {
        lang: sigs
        for lang, sigs in unmeasurable_signals(definitions, list(PLANTED)).items()
        if lang in languages
    }
    na_by_metric = classify_na(ledger["entries"], na_map)

    # ...and the same question one step downstream, for the derived risk_*
    # columns. Their inputs are read off the live engine's risk assembly rather
    # than hand-listed, so an engine refactor fails loudly here instead of
    # leaving a stale map quietly marking comparable cells n/a.
    deps = risk_dependencies(registry_signals(definitions))
    audit_signals = na_audit_signals(deps)
    dep_na_state = classify_na(
        ledger["entries"],
        {
            lang: sigs
            for lang, sigs in unmeasurable_signals(
                definitions, audit_signals, include_exempt=True
            ).items()
            if lang in languages
        },
    )
    # Absences of inputs the risk formulas read but the probe table never planted.
    # The #2560 review sweep only ever covered the planted 18, so these have had
    # no bucket-2 pass at all -- they are why some derived cells below are n/a†.
    dep_unreviewed = sorted(
        f"{lang}/{sig}"
        for sig, per_lang in dep_na_state.items()
        if sig not in PLANTED
        for lang, state in per_lang.items()
        if state == "unreviewed"
    )

    colmap = vl._signal_columns()
    all_totals, all_risks, all_struct, all_measures, zero_dep = {}, {}, {}, {}, {}
    for lang in languages:
        print(f"scanning {lang}...")
        (
            all_totals[lang],
            all_risks[lang],
            all_struct[lang],
            all_measures[lang],
            zero_dep[lang],
        ) = gather(lang, colmap)
        # Fail on the FIRST degraded scan rather than after all 46: the mode is a
        # property of the binary, so language 1 already settles it.
        if zero_dep[lang] and not allow_zero_dependency:
            print(
                f"ABORT: {lang} scanned in Zero-Dependency Mode. Network metrics are "
                "NULL there, so pagerank silently drops out of the comparison and the "
                "published report is not cell-for-cell comparable with a full-precision "
                "one. Point GALAXYSCOPE_BIN at the full-precision venv (AGENTS.md):\n"
                "  GALAXYSCOPE_BIN=<gitgalaxy>/.crucible_venvs/full_precision/bin/galaxyscope\n"
                "Deliberately reporting on a degraded engine? Re-run with "
                "--allow-zero-dependency; the report will say so in its header."
            )
            return 1
    degraded = sorted(lang for lang, z in zero_dep.items() if z)

    risk_na, risk_mismatches = unmeasurable_risk_cells(deps, definitions, all_risks)
    risk_na_by_metric = classify_risk_na(risk_na, deps, dep_na_state)
    na_by_metric.update(risk_na_by_metric)
    for lang, metrics in risk_na.items():
        for metric in metrics:
            all_risks[lang][metric] = None
    if risk_mismatches:
        print(
            f"MISMATCH: {len(risk_mismatches)} derived cell(s) whose every registry "
            "input is absent still measured nonzero (left comparable):"
        )
        for lang, metric, value in risk_mismatches:
            print(f"  {lang}/{metric} = {value:.4f} (inputs: {deps[metric]['governed']})")

    # Planted signals only. A derived risk cell is never its own audit row: its †
    # comes from an unreviewed *input*, already listed in dep_unreviewed above.
    # Listing it here too would give one backlog two incompatible counts -- derived
    # cells in this report vs. the input cells na_check.py actually gates on.
    unreviewed = sorted(
        f"{lang}/{sig}"
        for sig, per_lang in na_by_metric.items()
        if sig in PLANTED
        for lang, state in per_lang.items()
        if state == "unreviewed"
    )

    risk_names = sorted({c for r in all_risks.values() for c in r})
    struct_names = ["functions_found", "classes_found", "dependency_links",
                    "keyword_hits", "comment_lines", "pagerank"]
    measure_names = [c for c in MEASURE_COLS
                     if any(all_measures[lang].get(c) is not None for lang in languages)]
    groups = [
        ("risk exposure (mean per file)",
         {c: [all_risks[lang].get(c) for lang in languages] for c in risk_names}),
        ("engine measures (mean per file)",
         {c: [all_measures[lang].get(c) for lang in languages] for c in measure_names}),
        ("structure found (corpus totals)",
         {c: [all_struct[lang].get(c) for lang in languages] for c in struct_names}),
        ("planted signals (corpus totals)",
         {c: [None if c in na_map.get(lang, ()) else all_totals[lang].get(c, 0)
              for lang in languages] for c in PLANTED}),
    ]
    # scan cache: lets findings_report.py (and ad hoc queries) reuse this run.
    # n/a cells are stored as null (never 0 -- the engine cannot produce a nonzero
    # there), with the classification carried separately under "na".
    cache = {
        "languages": languages,
        "metrics": {},
        "na": na_by_metric,
        # E.1 follow-on: the risk_* derivation edges, read off the engine's own
        # risk assembly at regen time so every consumer of this cache attributes
        # downstream shadows the same way without importing the engine.
        "risk_inputs": deps,
        # Which engine mode produced these numbers. Zero-Dependency Mode nulls the
        # network metrics, so a cache generated there is not comparable cell-for-cell
        # with one generated at full precision (rosetta: the pre-#30 report had
        # pagerank NULL in all 46 columns and nothing said why).
        "engine_mode": "zero-dependency" if degraded else "full-precision",
    }
    for _, metrics in groups:
        for name, values in metrics.items():
            cache["metrics"][name] = dict(zip(languages, values))
    (REPO_ROOT / "docs" / "bias_data.json").write_text(
        json.dumps(cache, indent=1) + "\n"
    )

    # E.1 (gitgalaxy#2669): which out-of-band cells are already accounted for.
    verdicts = explain_out_of_band(
        cache["metrics"], languages, ledger["entries"],
        {c: dict(zip(languages, [all_struct[lang].get(c) for lang in languages]))
         for c in struct_names},
        risk_inputs=deps,
    )
    unexplained = sorted(k for k, (st, _) in verdicts.items() if st == "unexplained")
    by_status = collections.Counter(st for st, _ in verdicts.values())

    shares, skipped, inert, agreement = write_variance_chart(
        groups, len(languages), na_by_metric
    )
    avg_share = statistics.mean(shares.values()) if shares else 0
    n_strong = sum(1 for v in shares.values() if v >= 0.8)
    weakest = sorted(shares.items(), key=lambda kv: kv[1])[:5]

    lines = [
        "# Cross-Language Bias Report",
        "",
        f"Generated by `tools/bias_report.py` over {len(languages)} locked language(s): "
        + ", ".join(languages) + ".",
        "",
        ("**Engine mode: full precision** — all six optional dependencies present, so "
         "the network metrics (pagerank) are live."
         if not degraded else
         f"**WARNING — engine mode: Zero-Dependency Mode** for {len(degraded)} language(s) "
         f"({', '.join(degraded)}). Network metrics are NULL there, so pagerank silently "
         "drops out of the comparison. `verify.yml` installs all six dependencies for "
         "exactly this reason; point `GALAXYSCOPE_BIN` at the full-precision venv "
         "(AGENTS.md) and regenerate before trusting these numbers."),
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

    n_na_signal = sum(len(v) for k, v in na_by_metric.items() if k in PLANTED)
    n_na_risk = sum(len(v) for v in risk_na_by_metric.values())
    if n_na_signal:
        lines += [
            f"**n/a semantics:** {n_na_signal} language/signal cells are marked n/a — the "
            "language's registry entry defines no rule for that signal, so the engine "
            "cannot ever report a nonzero there. Those cells are *incomparable*, not "
            "zero: they are excluded from medians, deviation bands, and consistency "
            "scores rather than counted as −100% divergence. An n/a does **not** "
            "certify the absence is correct — that takes a validated ledger entry "
            "(docs/GATING.md).",
            "",
        ]
    if n_na_risk:
        lines += [
            f"**Derived metrics:** a further {n_na_risk} cells are n/a in the "
            "`risk_*` columns. Those are formulas over the same signals, so a language "
            "whose every governed input is absent has a structurally pinned score, not "
            "a low one — it used to be scored as a −100% outlier against languages that "
            "actually measured something. The inputs are read live off the engine's risk "
            "assembly, and a derived cell qualifies only when its formula reads no "
            "engine-synthesized input **and** the scan confirms the observed value is 0 "
            "(rule absence alone is not enough: these formulas also read structure the "
            "registry does not govern — LOC, doc lines, the call graph, popularity). Its "
            "review status is inherited, not invented: it counts as ledgered only when "
            "every governed input is itself ledgered for that language.",
            "",
        ]
    if risk_mismatches:
        lines += [
            "**Registry/engine mismatches** (left comparable, never absorbed): every "
            "registry input to these cells is absent, yet the engine still measured a "
            "value — so either the derived dependency map is incomplete, or the input is "
            "synthesized downstream of the registry the way orphan conversion synthesizes "
            "`api` (ledger `api-contextual-baseline-fix`): "
            + ", ".join(f"`{lang}/{metric}` = {value:.3f}" for lang, metric, value in risk_mismatches)
            + ".",
            "",
        ]
    if dep_unreviewed:
        lines += [
            "**WARNING: unreviewed absences among the risk formulas' non-planted inputs** "
            "(these are not in the probe table, so the #2560 sweep never reviewed them; "
            "each is either real morphology to ledger or a missing-rule engine gap, and "
            "each keeps every derived cell built on it marked n/a†): "
            + ", ".join(f"`{x}`" for x in dep_unreviewed) + ".",
            "",
        ]
    if unreviewed:
        lines += [
            "**WARNING: unreviewed rule absences** (no validated ledger entry records "
            "why the language lacks the concept — each is either real morphology to "
            "ledger, or a missing-rule engine gap like jcl's pre-#2610 `safety`): "
            + ", ".join(f"`{x}`" for x in unreviewed) + ".",
            "",
        ]

    lines += ["## Out-of-band cells: explained vs. unexplained", "",
              "An out-of-band cell is not automatically a defect. Three mechanisms account for one "
              "without anything being wrong with the engine, and the epic's close criterion is that "
              "nothing survives all three (`--gate` exits nonzero while anything does).", "",
              "| verdict | cells | meaning |",
              "|---|---|---|",
              f"| undefined | {by_status.get('undefined', 0)} | a per-function descriptor for a "
              "language with no functions -- the quotient has no value, it is not a deviation |",
              f"| ledgered | {by_status.get('ledgered', 0)} | a validated deviation-ledger entry "
              "names this language and this metric |",
              f"| derived | {by_status.get('derived', 0)} | a composite whose deviation entered "
              "through an input that is itself out of band, so it is the same finding counted twice |",
              f"| **unexplained** | **{len(unexplained)}** | **survived all three -- the real work "
              "remaining** |",
              ""]
    if unexplained:
        shown = collections.defaultdict(list)
        for metric, lang in unexplained:
            shown[metric].append(lang)
        lines += ["Unexplained cells, by metric:", ""]
        lines += [f"- `{m}` — {', '.join(sorted(langs))}" for m, langs in sorted(shown.items())]
        lines += [""]

    lines += ["## Cross-language variance chart", "",
              "![variance chart](bias_variance_chart.svg)", "",
              f"Each metric's badge is its **consistency score**: the share of languages "
              f"inside the green band (±{GREEN_DEV:.0%} of the cross-language median). "
              f"**Average across {len(shares)} metrics: {avg_share:.0%}**; "
              f"{n_strong} metrics hold ≥80% of languages in the green band. "
              f"Weakest metrics: "
              + ", ".join(f"{k} {v:.0%}" for k, v in weakest) + ". "
              + (f"‖ marks a metric scored on **exact agreement** with a zero median "
                 f"(relative deviation is undefined there, so the score is the share of "
                 f"languages sitting exactly on it): {', '.join(agreement)}. "
                 if agreement else "")
              + (f"Skipped (no values recorded): {', '.join(skipped)}. " if skipped else "")
              + (f"**Inert** (every language records exactly 0, so the column asks no "
                 f"cross-language question — scored as no result rather than as unanimous "
                 f"agreement): {', '.join(inert)}." if inert else ""),
              ""]

    lines += ["## Signal totals vs. planted intent", "",
              "| signal | planted | " + " | ".join(languages) + " |",
              "|---|---|" + "---|" * len(languages)]
    for sig, want in PLANTED.items():
        cells, comparable = [], []
        for lang in languages:
            if sig in na_map.get(lang, ()):
                cells.append("n/a" if na_by_metric[sig][lang] == "ledgered" else "n/a†")
            else:
                v = all_totals[lang].get(sig, 0)
                cells.append(str(v))
                comparable.append(v)
        mark = " ⚠" if (len(set(comparable)) > 1 or any(v != want for v in comparable)) else ""
        lines.append(f"| {sig}{mark} | {want} | " + " | ".join(cells) + " |")
    if n_na_signal:
        lines += ["", "n/a = no rule defined for this language (incomparable, excluded "
                  "from bands and medians); † = absence not yet backed by a validated "
                  "ledger entry."]

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
            if col in risk_na.get(lang, ()):
                vals.append("n/a" if risk_na_by_metric[col][lang] == "ledgered" else "n/a†")
                continue
            v = all_risks[lang].get(col)
            vals.append("—" if v is None else f"{v:.3f}")
        lines.append(f"| {col} | " + " | ".join(vals) + " |")
    if n_na_risk:
        lines += ["", "n/a = every registry-governed input to this formula is absent for "
                  "the language and the scan confirms the score is pinned at 0 "
                  "(incomparable, excluded from bands and medians); † = at least one of "
                  "those input absences is not yet backed by a validated ledger entry."]

    lines += ["", "## Engine measures (mean per file)", "",
              "Derived descriptions of the same program — topology, size, shape, "
              "complexity. Identical planted intent should produce identical values "
              "here for the same reason it should for pagerank; a spread is the engine "
              "describing one program differently depending on the language it is "
              "written in.", "",
              "| measure | " + " | ".join(languages) + " |",
              "|---|" + "---|" * len(languages)]
    for col in measure_names:
        vals = []
        for lang in languages:
            v = all_measures[lang].get(col)
            vals.append("—" if v is None else f"{v:.4g}")
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
    print(
        f"out-of-band cells: {len(unexplained)} unexplained "
        f"({by_status.get('undefined', 0)} undefined, {by_status.get('ledgered', 0)} ledgered, "
        f"{by_status.get('derived', 0)} derived)"
    )
    if gate and unexplained:
        print("--gate: unexplained out-of-band cells remain; epic close criterion not met")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
