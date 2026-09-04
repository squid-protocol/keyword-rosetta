"""Cross-language bias report: identical planted intent, divergent measurements.

For every language folder with a locked manifest, runs the same end-to-end scan the
verifier uses, then compares four gated groups of metrics across languages, in
pipeline order:

  1. planted keyword signals (corpus totals -- the extraction layer),
  2. structure counts (functions, classes, dependency edges, pagerank),
  3. shape descriptors (per-function and graph measures derived from the signals),
  4. risk scores (mean per file -- what the product reports),

plus four context groups that are reported but never gated: program length,
vocabulary (token tallies), unplanted risk inputs, commit age.

Because the planted intent is identical everywhere, divergence IS measured language
bias. Output: docs/bias_report.md + docs/bias_variance_chart.svg (strip plot, one
dot per language per metric coloured by zone, rows best -> worst per group, red-zone
outliers named, consistency badge per gated row; regenerated together).

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
    scoring_strata,
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

# ==============================================================================
# F.1 (gitgalaxy#2669): PROGRAM LENGTH IS CONTEXT, NOT A CONSISTENCY CLAIM
# ==============================================================================
# Four columns measure how LONG each language's 12-probe program came out, not
# whether the engine read it the same way: total_loc (blank-inclusive lines),
# coding_loc (lines after prism strips comments and blanks), token_mass (tokens
# in those lines) and keyword_hits (every rule match in the file summed over
# every signal -- the planted counts plus whatever glue syntax matched). The SPEC
# plants counts, never length: a 12-probe Dockerfile cannot be as long as the
# Java one without padding, and padding would move the signals that ARE planted.
# On the 2026-09-04 cache every procedural language sat within a few percent of
# the coding_loc median (go 18.5, perl 18.75, ada 18.5 vs 17.1); the out-of-band
# tail was exactly the non-procedural shells (markdown 0, m4 4, yacc 5, jcl 6,
# css/html/dockerfile/makefile/yaml/sqlite) and the two dense ones (haskell,
# scheme) -- 49 cells that no engine fix and no honest corpus edit could close.
#
# So these four are CONTEXT: charted without a badge, excluded from the
# consistency average, never given a verdict of their own, never counted by
# --gate. Two things they still do, deliberately:
#   * a context metric that is out of band for a language can still EXPLAIN a
#     derived cell there ("derived: inherits coding_loc") -- that is a deviation
#     entering through length, which is what length_leaks() measures one level
#     up, on the formula instead of the cell;
#   * coding_loc is the x-axis of length_leaks(): the same program at 46
#     lengths is the ideal fixture for asking which engine formulas read length
#     when they should be reading content.
#
# Two more joined on the same test ("would a perfect engine give the same value for
# the same program at two lengths?" -- no, by definition): avg_func_loc is lines
# per function, i.e. length divided by a planted 13; comment_lines is a count of
# documentation LINES where the SPEC plants one doc marker and one ownership
# marker per file, never a line count. Metrics that SHOULD be invariant and are
# not (func_internal_density, cog_raw) stay gated: their spread is an engine
# finding (gitgalaxy#2705), not size.
CONTEXT_METRICS = (
    "total_loc", "coding_loc", "token_mass", "keyword_hits",
    "avg_func_loc", "comment_lines",
)

# ==============================================================================
# VOCABULARY IS CONTEXT TOO (gitgalaxy#2669, after #2705 / #2716)
# ==============================================================================
# Two columns measure how a language SPELLS the program, not what the program
# does. `structural_boundaries` is a per-language keyword tally (solidity matches
# every `uint|address|bool|string|mapping`, perl every `my`, java every
# `var|new|return`); the same 12-probe program spans 16x across languages on it
# while coding_loc spans 4.7x (#2705). `control_flow_ratio` is
# branch / (branch + structural_boundaries) and `structural_mass` is the tally
# itself, so both inherit that spread by construction. #2705 decided NOT to
# redefine control_flow_ratio (it is a pre-trained ML feature in two scoring
# paths); the finding is ledgered (`control-flow-ratio-denominator-is-a-
# vocabulary-tally`), and a ledgered finding that can never turn green is not a
# gate, it is a fixture. So both leave the consistency average and the gate and
# are charted as context, exactly like length. cog_raw stays gated: it is
# branch/flux/heat density over mass_loc, not the tally.
VOCABULARY_METRICS = ("control_flow_ratio", "structural_mass")

# ==============================================================================
# F.3 (gitgalaxy#2669): TIER CONSTANTS ARE DESIGN; UNPLANTED INPUTS ARE NOT SIGNALS
# ==============================================================================
# Two more things a cell can be that are not "the engine read the same program
# differently":
#   * LANGUAGE-LEVEL CONSTANT. analysis_lens.LANGUAGE_STRICTNESS assigns each
#     language four yes/no strictness columns, and strictness_constants() turns
#     the count of False columns into Irc (= gaps) and Ot (= 1 + 0.1 x gaps),
#     which the risk formulas read -- wiki 08-03 documents it as deliberate.
#     Against a global median that reads as bias: languages sharing a gap count
#     report identical risk values with inputs identical to the median language,
#     which is the constant, not a defect (gitgalaxy#2653, #2718). So a
#     constant-reading metric is banded against the median of its OWN stratum
#     (reference_medians), and the per-stratum medians are printed as the
#     documented offset rather than hidden. Which metrics read one comes off the
#     engine source (_registry.risk_dependencies()[...]["reads_constant"]), never a hand
#     list. The per-signal fidelity table is deliberately NOT held equal: it is
#     generated from this corpus, so holding it equal would be circular.
#   * UNPLANTED INPUTS. The risk formulas also read registry signals the SPEC
#     never plants (immutability_locks, concurrency, sync_locks, ...). A shell
#     that idiomatically writes `val`/`let`/`final` carries freeze hits a `var`
#     shell does not, so risk_state_flux differs with state_mutation on plant.
#     Those signals are cached as an ungated group so a derived verdict can NAME
#     the input ("inherits immutability_locks") instead of leaving the cell
#     unexplained -- and so the corpus can see what it plants unintentionally.
#     The list is derived from the risk assembly at regen time.
#   * TEMPORAL. risk_stability and risk_churn read commit age, not content.
TEMPORAL_METRICS = ("risk_stability", "risk_churn")


def ungated_metrics(unplanted_inputs=()):
    """Everything reported but never gated: length, vocabulary, unplanted inputs, temporal."""
    return (set(CONTEXT_METRICS) | set(VOCABULARY_METRICS) | set(unplanted_inputs)
            | set(TEMPORAL_METRICS))


def reference_medians(metrics, languages, strata=None, constant_sensitive=()):
    """{metric: {lang: median}} -- what each cell is banded against.

    The global median for everything except the risk metrics that read a
    language-level constant, which use the median of the language's own strictness
    stratum when `strata` is given (gitgalaxy#2718: Irc = strictness gaps). The
    same program N times is still a median.
    """
    refs = {}
    for metric, values in metrics.items():
        if not isinstance(values, dict):
            continue
        nums = {
            lang: values.get(lang) for lang in languages
            if isinstance(values.get(lang), (int, float))
        }
        if not nums:
            continue
        if strata and metric in constant_sensitive:
            by_stratum = {}
            for lang, v in nums.items():
                by_stratum.setdefault(strata.get(lang, "irc0"), []).append(v)
            stratum_med = {t: statistics.median(vs) for t, vs in by_stratum.items()}
            refs[metric] = {lang: stratum_med[strata.get(lang, "irc0")] for lang in nums}
        else:
            global_med = statistics.median(nums.values())
            refs[metric] = {lang: global_med for lang in nums}
    return refs


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


def _row_stats(values, medians=None):
    """(devs, share, median, basis) for one metric across languages; None if unusable.

    `share` is the metric's cross-language consistency score (one outlier no longer
    flips a binary verdict; it just costs its share). `basis` says what it measures:
    "band" = fraction inside ±GREEN_DEV of a positive median; "agreement" = fraction
    exactly ON a zero median, the only meaningful reading when a relative deviation
    would divide by zero. Returns None only when the row is unusable: no values at
    all, or inert (every language records 0, so nothing was asked).

    `medians`, when given, is the per-language reference aligned with `values`
    (F.3: a constant-reading risk metric is banded against its own stratum's median);
    the returned median is still the global one, for the label."""
    vals = [v for v in values if v is not None]
    if not vals:
        return None
    med = statistics.median(vals)
    if medians is not None:
        pairs = [(v, m) for v, m in zip(values, medians) if v is not None and m is not None]
        if pairs and all(m > 0 for _, m in pairs):
            devs = [(v - m) / m for v, m in pairs]
            green_share = sum(1 for d in devs if abs(d) <= GREEN_DEV) / len(devs)
            return devs, green_share, med, "band"
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
    # record_keeper.py ~L487: avg_comp / avg_loc -- it divides by avg_func_loc
    # (context), so a short-shell language inherits its deviation from length.
    "func_internal_density": ("branch", "args", "func_start", "avg_func_loc"),
    # F.2 (gitgalaxy#2669): the graph family. record_keeper.py ~L489:
    #   dependency_density = import_count / max(int(coding_loc * control_flow_ratio), 1)
    # so a language whose only deviation is a short file or an off-median
    # control_flow_ratio reads as import-dense with the same three imports.
    "dependency_density": ("import", "coding_loc", "control_flow_ratio"),
    # record_keeper.py: import_count = len(raw_imports) -- the capture output the
    # corpus plants as `import` (3 per shell).
    "dependency_links": ("import",),
    # network_risk_sensor.py ~L371: nx.betweenness_centrality over the import DAG,
    # whose edges are exactly the captured imports.
    "betweenness_score": ("dependency_links",),
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


def out_of_band_cells(metrics, languages, refs=None):
    """{(metric, lang)} for every comparable cell outside the green band.

    Mirrors _row_stats' banding: a zero median is scored on exact agreement, so a
    nonzero value there is out of band and everything else is in. `refs` is
    reference_medians()' output; without it every cell is banded against the
    global median.
    """
    out = set()
    refs = refs or {}
    for metric, values in metrics.items():
        nums = [v for v in (values.get(lang) for lang in languages) if isinstance(v, (int, float))]
        if not nums:
            continue
        global_med = statistics.median(nums)
        for lang in languages:
            v = values.get(lang)
            if not isinstance(v, (int, float)):
                continue
            med = refs.get(metric, {}).get(lang, global_med)
            if med == 0:
                if v != 0:
                    out.add((metric, lang))
            elif abs((v - med) / med) > GREEN_DEV:
                out.add((metric, lang))
    return out


def explain_out_of_band(metrics, languages, ledger_entries, structure, risk_inputs=None,
                        strata=None, constant_sensitive=(), ungated=None):
    """{(metric, lang): (status, detail)} for every out-of-band cell.

    `strata` + `constant_sensitive` band the constant-reading risk metrics against
    their own stratum's median (F.3); `ungated` is the set of reported-but-never-gated
    metrics (defaults to the length context; the cache carries the full set as
    `ungated_metrics`). An ungated cell gets no verdict but stays in the
    out-of-band set so a derived metric can inherit from it.

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
    ungated = set(ungated) if ungated is not None else set(CONTEXT_METRICS)
    refs = reference_medians(metrics, languages, strata, constant_sensitive)
    oob = out_of_band_cells(metrics, languages, refs)
    verdicts = {}
    for metric, lang in sorted(oob):
        if metric in ungated:
            # F.1/F.3: length, unplanted inputs and temporal columns are reported,
            # never gated. The cell stays in `oob` so a derived metric can still
            # inherit from it below.
            continue
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
        edges = derivation_inputs(metric, risk_inputs, include_context=True)
        inherited = [i for i in edges if (i, lang) in oob]
        if inherited:
            verdicts[(metric, lang)] = ("derived", "inherits " + ", ".join(inherited))
            continue
        verdicts[(metric, lang)] = ("unexplained", "")
    return verdicts


def derivation_inputs(metric, risk_inputs=None, include_context=False):
    """The measured inputs a derived metric is built from, as cache column names.

    DERIVED_INPUTS for the structural composites; the engine's own risk assembly
    (`risk_inputs`, read off `_registry.risk_dependencies` at regen time) for the
    risk_* family; () for a metric with no known edges. `engine` inputs
    (orphaned_logic, duplicate_logic, the sec_* family) are synthesized downstream
    of the registry, so a None rule cannot pin them -- but they are still real
    inputs, and two of them are measured columns, so they belong in the edges.
    Context metrics (length) are dropped unless `include_context`: the verdict
    machinery may inherit from them, the leak check must not hold them equal.
    """
    edges = DERIVED_INPUTS.get(metric)
    if edges is None and risk_inputs and metric in risk_inputs:
        spec = risk_inputs[metric]
        edges = tuple(
            RISK_INPUT_COLUMNS.get(i, i)
            for i in (*spec.get("governed", ()), *spec.get("engine", ()))
        )
    edges = tuple(edges or ())
    if include_context:
        return edges
    return tuple(i for i in edges if i not in CONTEXT_METRICS)


# ------------------------------------------------------------------------------
# F.1 (gitgalaxy#2669): THE LENGTH-LEAK CHECK
# ------------------------------------------------------------------------------
# The rosetta corpus is one program written at 46 lengths. For a derived metric,
# take the languages whose planted inputs for it are all in band -- content held
# equal, so length is the only thing left to vary -- and rank-correlate the metric
# against coding_loc across them. A strong correlation is ONE finding on that
# formula (it reads length where it should read content), not N language cells:
# it is reported once, cited to the line where length enters, and filed as an
# engine design question in the gitgalaxy#2655 shape. It never changes a cell's
# verdict -- the cells of a leaking formula keep whatever verdict they had; the
# leak is the formula-level reason they were out of band to begin with.
LEAK_MIN_LANGUAGES = 8   # fewer than this and a rank correlation is noise
LEAK_RHO = 0.6           # |Spearman rho| at or above: leak
LEAK_WEAK_RHO = 0.4      # in [0.4, 0.6): reported as weak, not asserted

# Where length enters the formula, for the metrics whose LOC term is already
# located. A metric that leaks WITHOUT an entry here is the more interesting
# finding: its length term has not been found yet. Line numbers are approximate
# and dated 2026-09-04 (engine a334839) -- re-verify when the formula moves.
LENGTH_TERMS = {
    "func_internal_density": "avg_func_complexity / avg_func_loc (record_keeper.py ~L487)",
    "cog_raw": "_calc_cog_load: every density divides by _mass_loc(loc), floored at 50 by "
               "#2655 (signal_processor.py ~L1360-1390) -- every rosetta shell is below the "
               "floor, so no length term should survive; a residual correlation is an unheld "
               "input (concurrency, reflection_metaprogramming are not cached) or aggregation",
    "risk_cognitive_load": "the same _calc_cog_load densities, post-sigmoid",
    "control_flow_ratio": "branch / (branch + structural_boundaries); structural_boundaries "
                          "is a per-language token tally that grows with the file "
                          "(detector.py ~L1288)",
    "structural_mass": "file_mass adds loc / 50 (signal_processor.py ~L820)",
    "dependency_density": "import_count / max(int(coding_loc * control_flow_ratio), 1) "
                          "(record_keeper.py ~L489)",
    "risk_tech_debt": "_calc_tech_debt: stress / _mass_loc(loc) (signal_processor.py ~L1478)",
    # gitgalaxy#2669 F.4: located while re-banding onto the strictness strata. The
    # numerator of each of these grows with the program (opaque_execution adds
    # 5 + log1p(impact) per load-bearing undocumented function; api x 2.0 grows
    # with the surface; verification counts per-function coverage), while the
    # denominator is _mass_loc / max(total_loc, 50) -- floored at the #2655
    # evidence mass. EVERY file in this corpus is under that floor, so the
    # denominator is a constant here and the numerator's growth is unopposed.
    # That is the floor behaving as designed (below it, score on counts), not a
    # new length term: the same formulas divide correctly on real files.
    "risk_documentation": "_calc_documentation: (opaque_execution + api x 2 + dynamism) / "
                          "(_mass_loc(loc) + 20) (signal_processor.py ~L1561-1568) -- the "
                          "denominator is the #2655 floor, constant for every file in this "
                          "corpus, so the numerator's growth with program length is unopposed",
    "risk_api_exposure": "_calc_api_exposure: log1p(api) / log1p(max(total_loc, 50)) "
                         "(signal_processor.py ~L1738) -- same floor, same constant denominator",
    "risk_verification": "_calc_verification: untested impact / _mass_loc(loc) "
                         "(signal_processor.py ~L1664) -- same floor, same constant denominator",
}


def _spearman(xs, ys):
    """Spearman rank correlation, average ranks on ties; 0.0 when degenerate."""
    def ranks(a):
        order = sorted(range(len(a)), key=lambda i: a[i])
        r = [0.0] * len(a)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and a[order[j + 1]] == a[order[i]]:
                j += 1
            for k in range(i, j + 1):
                r[order[k]] = (i + j) / 2 + 1
            i = j + 1
        return r

    rx, ry = ranks(xs), ranks(ys)
    n = len(xs)
    mx, my = sum(rx) / n, sum(ry) / n
    cov = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    sx = math.sqrt(sum((a - mx) ** 2 for a in rx))
    sy = math.sqrt(sum((b - my) ** 2 for b in ry))
    return cov / (sx * sy) if sx and sy else 0.0


# A metric whose denominator is a registry keyword tally is not leaking LENGTH:
# the tally differs in vocabulary breadth per language (solidity matches every
# type token, makefile only assignments -- 16x on the identical program while
# coding_loc spans 4.7x) and merely tracks length within a language. #2705's
# design pass measured it; the ledger entry
# `control-flow-ratio-denominator-is-a-vocabulary-tally` owns the cells. The row
# is kept in the table, labelled for what it is, so it stops reappearing as a
# length finding at every regen.
# The vocabulary-denominator label this check used to attach to control_flow_ratio
# is gone: control_flow_ratio and structural_mass are VOCABULARY_METRICS now,
# reported as context and never in this table (the ledger entry
# `control-flow-ratio-denominator-is-a-vocabulary-tally` owns the finding).


def length_leaks(metrics, languages, risk_inputs=None, strata=None, x_axis="coding_loc",
                 constant_sensitive=(), ungated=None):
    """[{metric, n, rho, verdict, held, stratum, where}], strongest |rho| first.

    verdict is "leak" (|rho| >= LEAK_RHO) or "weak"; vocabulary metrics are context
    and never appear here.

    One row per derived metric that rank-correlates with `x_axis` at |rho| >=
    LEAK_WEAK_RHO across at least LEAK_MIN_LANGUAGES languages whose measured
    inputs for that metric (`held`) are all inside the green band. Planted
    signals and the context metrics themselves are never candidates. A metric
    with no known edges is correlated over every language that records it --
    there is nothing to hold equal, so the result is weaker evidence and says so
    through an empty `held`.

    `strata` ({language: strictness stratum}) is held equal too when given: the
    risk formulas add a flat `Irc / mass_loc` term and scale verification by `Ot`
    (gitgalaxy#2653, #2718), and the high-gap languages are, by and large, the
    short shells -- so without this a strictness effect reads as a length effect.
    The correlation runs inside the largest stratum among the qualifying languages
    and the row says which.
    """
    ungated = set(ungated) if ungated is not None else set(CONTEXT_METRICS)
    oob = out_of_band_cells(
        metrics, languages, reference_medians(metrics, languages, strata, constant_sensitive)
    )
    xs_all = metrics.get(x_axis, {})
    out = []
    for metric, values in metrics.items():
        if metric in PLANTED or metric in ungated or not isinstance(values, dict):
            continue
        held = tuple(i for i in derivation_inputs(metric, risk_inputs) if i in metrics)
        langs = [
            lang for lang in languages
            if isinstance(values.get(lang), (int, float))
            and isinstance(xs_all.get(lang), (int, float)) and xs_all[lang] > 0
            and all(
                (i, lang) not in oob and isinstance(metrics[i].get(lang), (int, float))
                for i in held
            )
        ]
        stratum = None
        if strata:
            by_stratum = collections.Counter(strata.get(lang, "irc0") for lang in langs)
            stratum = max(by_stratum, key=by_stratum.get) if by_stratum else None
            langs = [lang for lang in langs if strata.get(lang, "irc0") == stratum]
        if len(langs) < LEAK_MIN_LANGUAGES or len({values[lang] for lang in langs}) < 2:
            continue
        rho = _spearman([xs_all[lang] for lang in langs], [values[lang] for lang in langs])
        if abs(rho) < LEAK_WEAK_RHO:
            continue
        verdict = "leak" if abs(rho) >= LEAK_RHO else "weak"
        out.append({
            "metric": metric,
            "n": len(langs),
            "rho": round(rho, 3),
            "verdict": verdict,
            "held": list(held),
            "stratum": stratum,
            "where": LENGTH_TERMS.get(metric),
        })
    out.sort(key=lambda r: -abs(r["rho"]))
    return out


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


# Plain-English row labels for the chart; anything not listed falls back to the
# key with underscores as spaces. The key itself is always printed alongside,
# small and monospaced, so nothing is renamed away from the report tables.
PRETTY_METRIC = {
    "risk_api_exposure": "API exposure", "risk_cognitive_load": "Cognitive load",
    "risk_concurrency": "Concurrency", "risk_dead_code": "Dead code",
    "risk_documentation": "Documentation", "risk_safety_score": "Safety",
    "risk_spec_match": "Spec alignment", "risk_state_flux": "State flux",
    "risk_tech_debt": "Tech debt", "risk_verification": "Verification",
    "risk_secrets_risk": "Secrets", "risk_stability": "Stability", "risk_churn": "Churn",
    "pagerank_score": "PageRank", "pagerank": "PageRank (total)",
    "normalized_blast_radius": "Blast radius", "betweenness_score": "Betweenness",
    "closeness_score": "Closeness", "producer_ratio": "Producer ratio",
    "avg_func_complexity": "Avg function complexity", "max_func_complexity": "Max function complexity",
    "avg_func_args": "Avg function args", "func_complexity_gini": "Complexity Gini",
    "func_internal_density": "Function internal density", "dependency_density": "Dependency density",
    "encapsulation_ratio": "Encapsulation ratio", "popularity": "Popularity",
    "cog_raw": "Cognitive density (raw)", "raw_arch_api": "API surface (raw)",
    "raw_state_slop_orphans": "Orphaned functions", "def_encapsulation": "Encapsulation (raw)",
    "state_slop_duplicates": "Duplicate logic", "functions_found": "Functions found",
    "classes_found": "Classes found", "dependency_links": "Dependency links",
    "control_flow_ratio": "Control-flow ratio", "structural_mass": "Structural mass",
    "total_loc": "Total lines", "coding_loc": "Coding lines", "token_mass": "Token mass",
    "keyword_hits": "Keyword hits", "avg_func_loc": "Lines per function",
    "comment_lines": "Comment lines", "high_risk_execution": "High-risk execution",
    "safety_bypasses": "Safety bypasses", "state_mutation": "State mutation",
    "planned_debt": "Planned debt", "fragile_debt": "Fragile debt", "func_start": "Functions",
    "class_start": "Classes", "io": "I/O", "api": "API", "doc": "Documentation",
    "reflection_metaprogramming": "Reflection",
    "immutability_locks": "Immutability locks", "sync_locks": "Sync locks",
    "debug_prints": "Debug prints", "dead_code": "Dead code", "concurrency": "Concurrency",
    "spec_exposure": "Spec exposure", "llm_api": "LLM API",
}

# Group titles carry a one-line definition on the chart; keyed by the title
# string main() builds the groups with.
GROUP_BLURBS = {
    "planted keyword signals": "the extraction layer: does each rule find the constructs the SPEC planted?",
    "structure counts": "functions, classes and dependency edges the slicer and graph found",
    "shape descriptors": "per-function and graph measures derived from the signals",
    "risk scores": "what the product reports, per file (banded within the strictness stratum where a constant is read)",
    "program length": "how long the same program came out -- context, never gated",
    "vocabulary": "how the language spells it -- token tallies, context, never gated",
    "unplanted inputs": "signals the risk formulas read that the SPEC never plants -- context",
    "commit age": "temporal, not content -- context",
}


def _pretty(name):
    return PRETTY_METRIC.get(name, name.replace("_", " ").capitalize())


def _kept_languages(languages, values, medians):
    """The languages _row_stats kept for this row, in the order its devs come back."""
    if languages is None:
        return None
    if medians is not None:
        pairs = [(l, v, m) for l, v, m in zip(languages, values, medians) if v is not None and m is not None]
        if pairs and all(m > 0 for _, _, m in pairs):
            return [l for l, _, _ in pairs]
    return [l for l, v in zip(languages, values) if v is not None]


def write_variance_chart(groups, n_langs, na_by_metric=None, medians=None,
                         languages=None, unexplained=()):
    """Strip-plot SVG. groups = [(title, {metric: [values-per-language]}, gated)].

    `medians` = {metric: [per-language reference median]} for the rows that are
    banded against something other than the global median (F.3 stratum rows).
    `languages` (aligned with each metric's value list) lets the chart name the
    red-zone outliers; `unexplained` = {(metric, lang)} cells that survived every
    verdict, drawn as a red ring so the gate state is visible on the picture.

    Rows are ordered best -> worst inside each group; each group prints its
    average. Dots are coloured by zone (green / amber / red) and translucent so a
    stack darkens; the count of dots inside the green band sits at its edge. A
    context row is drawn but carries no badge and no share -- a length or
    vocabulary spread is not a consistency result.
    """
    label_w, strip_w, row_h, pad, badge_w = 300, 430, 26, 16, 118
    width = label_w + strip_w + badge_w + pad * 4
    half = strip_w / 2
    px_per_dev = half / 1.1
    unexplained = set(unexplained)

    def x_of(dev):
        return label_w + pad * 2 + half + max(-1.1, min(1.1, dev)) * px_per_dev

    prepared, shares, n_rows, skipped, inert, agreement = [], {}, 0, [], [], []
    for title, metrics, gated in groups:
        rows = []
        for name, values in metrics.items():
            row_meds = (medians or {}).get(name)
            st = _row_stats(values, row_meds)
            if st is None:
                (inert if is_inert(values) else skipped).append(name)
                continue
            rows.append((name, *st, _kept_languages(languages, values, row_meds)))
            if gated:
                shares[name] = st[1]
            if st[3] == "agreement":
                agreement.append(name)
        rows.sort(key=lambda r: -r[2])
        if rows:
            prepared.append((title, rows, gated))
            n_rows += len(rows)

    avg_share = statistics.mean(shares.values()) if shares else 0.0
    n_strong = sum(1 for v in shares.values() if v >= 0.8)
    height = 128 + sum(48 for _ in prepared) + n_rows * row_h + 28
    ink, muted, faint = "#14213d", "#5f6670", "#9aa3ad"
    s = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'font-family="Inter, system-ui, sans-serif" font-size="12">',
        f'<rect width="{width}" height="{height}" fill="#ffffff"/>',
        f'<text x="{pad}" y="30" font-size="19" font-weight="700" fill="{ink}">'
        f"One program, {n_langs} languages — does GitGalaxy read it the same everywhere?</text>",
        f'<text x="{pad}" y="52" fill="{muted}">Identical planted code in every language. Each dot is one '
        f"language's deviation from the cross-language median: green ±{GREEN_DEV:.0%}, amber ±{AMBER_DEV:.0%}, "
        f"red beyond.</text>",
        f'<text x="{pad}" y="68" fill="{muted}">Rows run best → worst inside each group. Every dot outside '
        f"the green band has a verdict in the deviation ledger; an unexplained one is drawn as a red ring.</text>",
    ]
    tiles = [
        (f"{avg_share:.0%}", "average consistency, gated metrics"),
        (f"{n_strong} / {len(shares)}", "gated metrics at ≥ 80% green"),
        (f"{len(unexplained)}", "unexplained out-of-band cells"),
        (f"{n_langs}", "languages"),
    ]
    tile_w = (width - pad * 2) / len(tiles)
    for i, (big, cap) in enumerate(tiles):
        tx = pad + i * tile_w
        s.append(f'<text x="{tx:.0f}" y="102" font-size="22" font-weight="700" fill="{ink}">{big}</text>')
        s.append(f'<text x="{tx:.0f}" y="118" font-size="10.5" fill="{muted}">{cap}</text>')
    na_by_metric = na_by_metric or {}
    y = 128
    for title, rows, gated in prepared:
        y += 24
        s.append(f'<line x1="{pad}" y1="{y - 14}" x2="{width - pad}" y2="{y - 14}" stroke="#e3e6ea"/>')
        s.append(f'<text x="{pad}" y="{y + 4}" font-size="13" font-weight="700" fill="{ink}" '
                 f'letter-spacing=".6">{title.upper()}</text>')
        blurb = GROUP_BLURBS.get(title, "")
        if blurb:
            s.append(f'<text x="{pad + 8.2 * len(title) + 36:.0f}" y="{y + 4}" font-size="11.5" fill="{muted}">{blurb}</text>')
        if gated and rows:
            gavg = statistics.mean(r[2] for r in rows)
            s.append(f'<text x="{width - pad}" y="{y + 4}" font-size="11.5" fill="{muted}" '
                     f'text-anchor="end">group average {gavg:.0%}</text>')
        y += 24
        for name, devs, green_share, med, basis, kept in rows:
            cy = y + row_h / 2
            s.append(f'<rect x="{x_of(-1.1):.1f}" y="{y + 5}" width="{strip_w}" height="{row_h - 10}" fill="#f4f5f7" rx="3"/>')
            s.append(f'<rect x="{x_of(-GREEN_DEV):.1f}" y="{y + 5}" width="{x_of(GREEN_DEV) - x_of(-GREEN_DEV):.1f}" '
                     f'height="{row_h - 10}" fill="#dcefe0"/>')
            for e in (-AMBER_DEV, AMBER_DEV):
                s.append(f'<line x1="{x_of(e):.1f}" y1="{y + 5}" x2="{x_of(e):.1f}" y2="{y + row_h - 5}" '
                         f'stroke="#e8c98a" stroke-dasharray="2,2"/>')
            s.append(f'<line x1="{x_of(0):.1f}" y1="{y + 5}" x2="{x_of(0):.1f}" y2="{y + row_h - 5}" stroke="{faint}"/>')
            s.append(f'<text x="{pad}" y="{cy + 4}" fill="#1a1a1a" font-size="12.5">{_pretty(name)}</text>')
            n_na = len(na_by_metric.get(name, {}))
            key = name if basis == "band" else f"{name} · exact"
            if n_na:
                key += f" · n/a {n_na}"
            s.append(f'<text x="{label_w - 4}" y="{cy + 4}" fill="{faint}" font-size="9.5" '
                     f'font-family="ui-monospace, Menlo, monospace" text-anchor="end">{key}</text>')
            outl = []
            for i, d in enumerate(devs):
                lang = kept[i] if kept and i < len(kept) else None
                col = "#2f855a" if abs(d) <= GREEN_DEV else ("#c98a1a" if abs(d) <= AMBER_DEV else "#c0392b")
                s.append(f'<circle cx="{x_of(d):.1f}" cy="{cy:.1f}" r="4.2" fill="{col}" fill-opacity=".55"/>')
                if lang and (name, lang) in unexplained:
                    s.append(f'<circle cx="{x_of(d):.1f}" cy="{cy:.1f}" r="7" fill="none" stroke="#c0392b" stroke-width="1.8"/>')
                if abs(d) > AMBER_DEV and lang:
                    outl.append((d, lang))
            n_green = sum(1 for d in devs if abs(d) <= GREEN_DEV)
            s.append(f'<text x="{x_of(GREEN_DEV) + 4:.1f}" y="{y + 13}" font-size="9" fill="#2f855a">{n_green}</text>')
            left = [l for d, l in sorted(outl) if d < 0][:3]
            right = [l for d, l in sorted(outl, reverse=True) if d > 0][:3]
            if left:
                s.append(f'<text x="{x_of(-1.1) + 3:.1f}" y="{y + row_h - 1}" font-size="8" fill="#a33">{", ".join(left)}</text>')
            if right:
                s.append(f'<text x="{x_of(1.1) - 3:.1f}" y="{y + row_h - 1}" font-size="8" fill="#a33" '
                         f'text-anchor="end">{", ".join(right)}</text>')
            bx = label_w + strip_w + pad * 3
            if gated:
                col = "#2f855a" if green_share >= 0.8 else ("#c98a1a" if green_share >= 0.6 else "#c0392b")
                bar_w = badge_w - 42
                s.append(f'<rect x="{bx}" y="{cy - 6}" width="{bar_w}" height="12" fill="#eceff2" rx="2"/>')
                s.append(f'<rect x="{bx}" y="{cy - 6}" width="{bar_w * green_share:.1f}" height="12" fill="{col}" rx="2"/>')
                s.append(f'<text x="{bx + badge_w - 2}" y="{cy + 4}" font-size="12" font-weight="700" fill="{col}" '
                         f'text-anchor="end">{green_share:.0%}</text>')
            else:
                s.append(f'<text x="{bx + badge_w - 2}" y="{cy + 4}" font-size="10.5" fill="{faint}" text-anchor="end">context</text>')
            y += row_h
    s.append(f'<text x="{pad}" y="{height - 10}" font-size="10" fill="{faint}">keyword-rosetta · tools/bias_report.py · '
             f'band ±{GREEN_DEV:.0%} of the cross-language median (exact agreement where the median is 0) · '
             f"n/a = the language's registry defines no rule for the signal</text>")
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
    # F.1: the length columns leave their groups for a context group of their own
    # (the tables below still print them where they always were).
    context_values = {}
    for c in CONTEXT_METRICS:
        if c in measure_names:
            context_values[c] = [all_measures[lang].get(c) for lang in languages]
        elif c in struct_names:
            context_values[c] = [all_struct[lang].get(c) for lang in languages]
    # F.3: which risk formulas read a language-level constant, and which registry signals
    # they read that the SPEC never plants -- both off the engine's risk assembly.
    constant_sensitive = sorted(m for m, d in deps.items() if d.get("reads_constant"))
    # (api and encapsulation are governed-but-unplanted too, but they are already
    # measured columns -- raw_arch_api / def_encapsulation -- so they stay there.)
    unplanted_inputs = sorted(
        {s for d in deps.values() for s in d["governed"]
         if s not in PLANTED and s not in RISK_INPUT_COLUMNS}
    )
    ungated = ungated_metrics(unplanted_inputs)
    strata = scoring_strata(languages)
    # Pipeline order, top to bottom: what was planted -> what the slicer found ->
    # the descriptors derived from it -> the scores the product reports; then the
    # context groups (reported, never gated). Titles are keyed by GROUP_BLURBS.
    groups = [
        ("planted keyword signals",
         {c: [None if c in na_map.get(lang, ()) else all_totals[lang].get(c, 0)
              for lang in languages] for c in PLANTED}, True),
        ("structure counts",
         {c: [all_struct[lang].get(c) for lang in languages]
          for c in struct_names if c not in CONTEXT_METRICS}, True),
        ("shape descriptors",
         {c: [all_measures[lang].get(c) for lang in languages]
          for c in measure_names if c not in CONTEXT_METRICS and c not in VOCABULARY_METRICS}, True),
        ("risk scores",
         {c: [all_risks[lang].get(c) for lang in languages]
          for c in risk_names if c not in TEMPORAL_METRICS}, True),
        ("program length", context_values, False),
        ("vocabulary",
         {c: [all_measures[lang].get(c) for lang in languages]
          for c in VOCABULARY_METRICS if c in measure_names}, False),
        ("unplanted inputs",
         {s: [None if lang in dep_na_state.get(s, {}) else all_totals[lang].get(s, 0)
              for lang in languages] for s in unplanted_inputs}, False),
        ("commit age",
         {c: [all_risks[lang].get(c) for lang in languages]
          for c in risk_names if c in TEMPORAL_METRICS}, False),
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
        # F.1: which columns are length (context, never gated), so every consumer
        # of this cache draws the line in the same place.
        "context_metrics": list(CONTEXT_METRICS),
        # Vocabulary columns (token tallies): context like length, never gated.
        "vocabulary_metrics": list(VOCABULARY_METRICS),
        # The engine's strictness stratum per language (analysis_lens, read
        # off the source): held equal by the leak check, banded within by F.3.
        "strata": strata,
        # F.3: the risk metrics banded against their own stratum's median, the
        # registry signals the formulas read but the SPEC never plants, and the
        # full reported-not-gated set every consumer must skip.
        "constant_sensitive": constant_sensitive,
        "unplanted_inputs": unplanted_inputs,
        "ungated_metrics": sorted(ungated),
    }
    for _, metrics, _gated in groups:
        for name, values in metrics.items():
            cache["metrics"][name] = dict(zip(languages, values))
    # F.1: the length-leak findings ride in the cache too, so issue_status.py and
    # ad hoc readers see the same table the report prints.
    leaks = length_leaks(cache["metrics"], languages, deps, strata=strata,
                         constant_sensitive=constant_sensitive, ungated=ungated)
    cache["length_leaks"] = leaks
    (REPO_ROOT / "docs" / "bias_data.json").write_text(
        json.dumps(cache, indent=1) + "\n"
    )

    # E.1 (gitgalaxy#2669): which out-of-band cells are already accounted for.
    verdicts = explain_out_of_band(
        cache["metrics"], languages, ledger["entries"],
        {c: dict(zip(languages, [all_struct[lang].get(c) for lang in languages]))
         for c in struct_names},
        risk_inputs=deps, strata=strata, constant_sensitive=constant_sensitive, ungated=ungated,
    )
    unexplained = sorted(k for k, (st, _) in verdicts.items() if st == "unexplained")
    by_status = collections.Counter(st for st, _ in verdicts.values())

    refs = reference_medians(cache["metrics"], languages, strata, constant_sensitive)
    shares, skipped, inert, agreement = write_variance_chart(
        groups, len(languages), na_by_metric,
        medians={m: [refs[m].get(lang) for lang in languages] for m in constant_sensitive if m in refs},
        languages=languages, unexplained=set(unexplained),
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

    oob_all = out_of_band_cells(cache["metrics"], languages, refs)
    n_context_oob = sum(1 for metric, _ in oob_all if metric in CONTEXT_METRICS)
    n_unplanted_oob = sum(1 for metric, _ in oob_all if metric in unplanted_inputs)
    lines += ["## Out-of-band cells: explained vs. unexplained", "",
              "An out-of-band cell is not automatically a defect. Three mechanisms account for one "
              "without anything being wrong with the engine, and the epic's close criterion is that "
              "nothing survives all three (`--gate` exits nonzero while anything does). The four "
              "program-length columns are context, not consistency claims, and are not counted here "
              f"at all ({n_context_oob} of their cells are out of band; see the next section).", "",
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

    present = sorted({strata.get(l) for l in languages if strata.get(l)})
    lines += ["## The language-level risk constant is design; the report bands within it", "",
              "`analysis_lens.LANGUAGE_STRICTNESS` gives every language four yes/no columns (static "
              "types, enforced errors, memory safety, no implicit globals) and "
              "`strictness_constants()` turns the count of `False` columns into the constants the "
              "formulas below read: `Irc` = gaps, `Ot` = 1 + 0.1 x gaps (gitgalaxy#2718, which "
              "replaced the three hand-listed scoring tiers this section used to read out of "
              "`signal_processor._get_tier`). Wiki 08-03 documents the term as deliberate. Against a "
              "global median it reads as bias: languages carrying the same gap count report identical "
              "risk values with inputs identical to the median language. So each metric that reads a "
              "language-level constant is banded against **the median of its own stratum** "
              "(gitgalaxy#2669 F.3), and the per-stratum medians are the documented offset, printed "
              "here rather than hidden. Which metrics read one is taken off the engine source at "
              "regen time, never hand-listed. Strata (`ircN` = N strictness gaps): "
              + "; ".join(
                  f"**{t}** = " + ", ".join(sorted(l for l in languages if strata.get(l) == t))
                  for t in present
              ) + ".", "",
              "**Not held equal:** the per-language x per-signal fidelity coefficients "
              "(`gitgalaxy/standards/fidelity_table.py`) that replaced the scalar `fc`. They are "
              "generated FROM this corpus, so banding against them would be circular -- a surviving "
              "defence-credit deviation may still be a fidelity cell.", "",
              "| metric | " + " | ".join(f"{t} median (n)" for t in present) + " | global median |",
              "|---" * (len(present) + 2) + "|"]
    for m in constant_sensitive:
        vals = cache["metrics"].get(m, {})
        cells = []
        for t in present:
            vs = [v for lang, v in vals.items() if strata.get(lang) == t and isinstance(v, (int, float))]
            cells.append(f"{statistics.median(vs):.3f} ({len(vs)})" if vs else "—")
        allv = [v for v in vals.values() if isinstance(v, (int, float))]
        tail = f" | {statistics.median(allv):.3f} |" if allv else " | — |"
        lines.append(f"| `{m}` | " + " | ".join(cells) + tail)
    lines += ["", "## Unplanted risk inputs", "",
              "The risk formulas read registry signals the SPEC does not plant: "
              + ", ".join(f"`{s}`" for s in unplanted_inputs)
              + ". A shell that idiomatically writes `val`/`let`/`final` carries `immutability_locks` "
              "a `var` shell does not, and `risk_state_flux` then differs with `state_mutation` on "
              "plant. These columns are reported (below, and in the chart) but never gated; an "
              "out-of-band cell here gets no verdict, but a derived risk cell may inherit from it "
              f"and say so. {n_unplanted_oob} such cells are out of band now:", ""]
    unplanted_hits = collections.defaultdict(list)
    for metric, lang in sorted(oob_all):
        if metric in unplanted_inputs:
            unplanted_hits[metric].append(f"{lang} {cache['metrics'][metric][lang]:g}")
    lines += [f"- `{m}` — {', '.join(v)}" for m, v in sorted(unplanted_hits.items())] or ["- none"]
    lines += ["", "`risk_stability` and `risk_churn` read commit age, not content, and are reported "
              "as temporal context on the same terms.", ""]

    lines += ["## Program length is context, and the x-axis of the leak check", "",
              "`" + "`, `".join(CONTEXT_METRICS) + "` measure how long each language's 12-probe "
              "program came out, which the SPEC does not plant (gitgalaxy#2669 F.1): a 12-probe "
              "Dockerfile cannot be as long as the Java one without padding, and padding would move "
              "the planted signals. They are charted without a badge, excluded from the consistency "
              "average, and never gated. A context column that is out of band for a language can "
              "still explain a derived cell there (`derived: inherits coding_loc` is a deviation that "
              "entered through length), and `coding_loc` is the x-axis of the check below.", "",
              "**Length leaks.** For each derived metric, over the languages whose measured inputs "
              "for it are all in band (content held equal, so length is the only free variable), the "
              "Spearman rank correlation against `coding_loc`. "
              f"|rho| ≥ {LEAK_RHO} across ≥ {LEAK_MIN_LANGUAGES} languages is a **leak**: the formula "
              "reads length where it should read content. That is one finding per formula, not one "
              "per language — each is an engine design question in the gitgalaxy#2655 shape, filed "
              "against the cited line — and it changes no cell's verdict above. The engine's "
              "language-level constant (gitgalaxy#2653/#2718: a flat `Irc / mass_loc` term and an "
              "`Ot` scale) is held equal as well, inside the largest strictness stratum among the "
              "qualifying languages, because the high-gap languages are largely the short shells and "
              "a strictness effect would otherwise read as a length effect. A metric with no known inputs is correlated over every "
              "language that records it (nothing held), which is weaker evidence and is marked as "
              "such.", ""]
    if leaks:
        lines += ["| metric | languages | stratum | rho | verdict | inputs held in band | where length enters |",
                  "|---|---|---|---|---|---|---|"]
        for r in leaks:
            held = ", ".join(f"`{h}`" for h in r["held"]) if r["held"] else "*(none known)*"
            where = r["where"] or "**not located yet** — the more interesting finding"
            label = {"leak": "**leak**", "weak": "weak"}[r["verdict"]]
            lines.append(f"| `{r['metric']}` | {r['n']} | {r.get('stratum') or '—'} | {r['rho']:+.2f} | "
                         f"{label} | {held} | {where} |")
        lines += [""]
    else:
        lines += ["No derived metric correlates with `coding_loc` at "
                  f"|rho| ≥ {LEAK_WEAK_RHO} over ≥ {LEAK_MIN_LANGUAGES} languages.", ""]

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

    lines += ["## Planted keyword signals (corpus totals vs. planted intent)", "",
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

    lines += ["", "## Structure counts (corpus totals)", "",
              "| metric | " + " | ".join(languages) + " |",
              "|---|" + "---|" * len(languages)]
    for name in struct_names:
        vals = []
        for lang in languages:
            v = all_struct[lang].get(name)
            vals.append("—" if v is None else (f"{v:.4f}" if isinstance(v, float) else str(v)))
        lines.append(f"| {name} | " + " | ".join(vals) + " |")

    lines += ["", "## Risk scores (mean per file)", "",
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

    lines += ["", "## Shape descriptors (mean per file)", "",
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
        f"{by_status.get('derived', 0)} derived; {n_context_oob} context + {n_unplanted_oob} "
        "unplanted-input cells not counted)"
    )
    n_leak = sum(1 for r in leaks if r["verdict"] == "leak")
    print(
        f"length leaks: {n_leak} leak / {len(leaks) - n_leak} weak -- "
        + (", ".join(f"{r['metric']} {r['rho']:+.2f}" for r in leaks if r["verdict"] == "leak")
           or "none")
    )
    if gate and unexplained:
        print("--gate: unexplained out-of-band cells remain; epic close criterion not met")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
