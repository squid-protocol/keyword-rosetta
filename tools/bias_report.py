"""Cross-language bias report: identical planted intent, divergent measurements.

For every language folder with a locked manifest, runs the same end-to-end scan the
verifier uses, then compares four gated groups of metrics across languages, in
pipeline order:

  1. planted keyword signals (corpus totals -- the extraction layer),
  2. structure counts (functions, classes, dependency edges, pagerank),
  3. shape descriptors (per-function and graph measures derived from the signals),
  4. risk scores (mean per file -- what the product reports),

plus two context groups that are reported but never gated: program size &
vocabulary (length and token tallies), and commit age. The non-planted risk inputs
used to be a third; since 2026-09-07 they are scored, because their honest value is
0 in every language and that is a comparable claim.

Because the planted intent is identical everywhere, divergence IS measured language
bias. Output: docs/bias_report.md + docs/bias_variance_chart.svg (strip plot,
languages clustered into count-labelled dots per metric, coloured by cause, rows
best -> worst per group, out-of-band languages named, accounted-share badge per
gated row; regenerated together).

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
import os
import pathlib
import sqlite3
import statistics
import subprocess
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import _registry
import verify_language as vl
from _registry import (
    declaration_strata,
    load_definitions,
    population_less_languages,
    registry_signals,
    risk_dependencies,
    scoring_strata,
    unmeasurable_signals,
)

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = REPO_ROOT / "docs" / "bias_report.md"
CHART = REPO_ROOT / "docs" / "bias_variance_chart.svg"


def engine_provenance():
    """(commit, scanner_package_path, mismatch_reason) for the engine being measured.

    Two DIFFERENT things resolve the engine on every run and nothing used to check
    they agree: `GITGALAXY_PATH` supplies the registry this process imports (rules,
    risk_dependencies, strictness constants) while `GALAXYSCOPE_BIN` is a separate
    binary whose editable install points at whatever checkout it was created from.
    Point them at different trees and the report reads one engine's registry over
    another engine's measurements -- with no error and no visible symptom.

    That is not hypothetical either: on 2026-09-07 a regen run with GITGALAXY_PATH
    on main and GALAXYSCOPE_BIN on the primary checkout (7 merges behind) reported
    32 unexplained cells and a 2.5% open-defect share, against the true 6 and 1.5%.
    Nothing in the output said which engine produced it, because the cache recorded
    only `engine_mode`; the commit lived solely in bias-history.yml's commit message,
    so a local run recorded nothing at all.

    The scanner's own `gitgalaxy.__file__` is asked of the scanner's interpreter, not
    of this one -- the whole point is that the two can differ.
    """
    registry_root = pathlib.Path(_registry.GITGALAXY_PATH).resolve()
    commit = None
    head = subprocess.run(
        ["git", "-C", str(registry_root), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
    )
    if head.returncode == 0:
        commit = head.stdout.strip()

    scanner_root, mismatch = None, None
    binary = pathlib.Path(vl.GALAXYSCOPE_BIN)
    interpreter = binary.parent / "python"
    if interpreter.exists():
        probe = subprocess.run(
            [str(interpreter), "-c", "import gitgalaxy, pathlib; print(gitgalaxy.__file__)"],
            capture_output=True,
            text=True,
            env={**os.environ},
        )
        if probe.returncode == 0 and probe.stdout.strip():
            scanner_root = str(pathlib.Path(probe.stdout.strip()).resolve().parent.parent)
            if pathlib.Path(scanner_root) != registry_root:
                mismatch = (
                    f"GITGALAXY_PATH resolves the registry to {registry_root}, but "
                    f"{vl.GALAXYSCOPE_BIN} scans with the engine at {scanner_root}. "
                    "The report would read one engine's rules over another's measurements. "
                    "Point PYTHONPATH at the same checkout as GITGALAXY_PATH so it shadows "
                    "the binary's editable install:\n"
                    f"  PYTHONPATH={registry_root} GITGALAXY_PATH={registry_root} \\\n"
                    f"      GALAXYSCOPE_BIN={vl.GALAXYSCOPE_BIN} python tools/bias_report.py\n"
                    "Deliberately measuring a different engine? Re-run with --allow-engine-mismatch."
                )
    return commit, scanner_root, mismatch


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
    # Baseline Fix rewrites api and unreferenced_by_name in place for any file with
    # popularity > 0, so the adjusted values carry the DAG's bias into a column
    # meant to measure extraction. #2536 added these snapshots for exactly this
    # consumer.
    "raw_arch_api",
    "raw_state_unreferenced",
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
    """Everything reported but never gated: length, vocabulary, temporal.

    The unplanted risk inputs used to be here too, and are NOT any more. They were
    grouped with length and vocabulary on the "languages vary too much for a band to
    mean anything" argument, but that argument does not apply to them: the corpus
    plants nothing these rules match, so the expected reading is 0 in EVERY language
    and any nonzero cell is a rule firing on something nobody wrote. That is exactly
    the comparable claim the chart exists to make, and it is scored the way every
    other zero-median metric already is -- exact agreement, not a relative band
    (see `basis == "agreement"`). The parameter is kept so callers that pass it stay
    valid; it no longer widens the set.
    """
    return set(CONTEXT_METRICS) | set(VOCABULARY_METRICS) | set(TEMPORAL_METRICS) | set(UNIT_METRICS)


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
    """Scan one language: (signals, risk_means, struct, measure_means, zero_dep, units)."""
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
        # gitgalaxy#2908: the per-unit attribute totals (function_data SUMs over
        # the shell files). Pre-Phase-2 engines have no is_public column; the
        # totals are simply absent then, never fabricated as zero.
        units = {u: None for u in UNIT_METRICS}
        fhave = {r[1] for r in conn.execute("PRAGMA table_info(function_data)")}
        if {"is_public", "is_documented"} <= fhave:
            row = conn.execute(
                "SELECT COALESCE(SUM(fd.is_public), 0), COALESCE(SUM(fd.is_documented), 0),"
                " COALESCE(SUM(fd.is_public * fd.is_documented), 0)"
                " FROM function_data fd JOIN file_data f ON fd.file_id = f.id"
                " WHERE f.file_name IN (%s)" % ",".join("?" * len(shell_files)),
                sorted(shell_files),
            ).fetchone()
            units = {"units_public": row[0], "units_documented": row[1],
                     "units_public_documented": row[2]}
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
    return totals, risk_means, struct, measure_means, zero_dep, units


def _row_stats(values, medians=None, presence=None):
    """(devs, share, median, basis) for one metric across languages; None if unusable.

    `share` is the metric's cross-language consistency score (one outlier no longer
    flips a binary verdict; it just costs its share). `basis` says what it measures:
    "band" = fraction inside ±GREEN_DEV of a positive median; "agreement" = fraction
    exactly ON a zero median, the only meaningful reading when a relative deviation
    would divide by zero; "declaration" = the gitgalaxy#2796 presence rule below.
    Returns None only when the row is unusable: no values at all, or inert (every
    language records 0, so nothing was asked).

    `medians`, when given, is the per-language reference aligned with `values`
    (F.3: a constant-reading risk metric is banded against its own stratum's median);
    the returned median is still the global one, for the label.

    `presence`, when given, is the per-language declaration stratum aligned with
    `values` ("container-required"/"declaration-optional"/None) and takes priority."""
    vals = [v for v in values if v is not None]
    if not vals:
        return None
    if presence is not None:
        # gitgalaxy#2796: the declaration-requirement row (classes_found) bands on
        # container PRESENCE, not a cross-language count. A language whose file IS a
        # container -- cobol PROGRAM-ID, jcl JOB card, dockerfile FROM -- is in band
        # iff it declares >=1; a declaration-optional language iff it declares 0. How
        # MANY containers a file carries is corpus structure (dockerfile's 4 stages vs
        # cobol's 1 program), not engine quality, so an exact-count median would paint
        # correct morphology red. A missing required container, or a spurious class in
        # a language that requires none, still reads off-scale.
        judged = [(v, p) for v, p in zip(values, presence) if v is not None and p is not None]
        if judged:
            devs, greens = [], 0
            for v, p in judged:
                ok = (v >= 1) if p == "container-required" else (v == 0)
                greens += ok
                devs.append(0.0 if ok else math.copysign(1.0, v - (1 if p == "container-required" else 0)))
            return devs, greens / len(judged), statistics.median([v for v, _ in judged]), "declaration"
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

# ==============================================================================
# PER-UNIT ATTRIBUTES (gitgalaxy#2908)
# ==============================================================================
# Phase 2 put `is_public` / `is_documented` on every extracted unit; Phase 3 made
# `risk_documentation` a ratio over exactly those attributes. The cross-language
# TOTALS are cached here so the derivation machinery can do its job -- a
# documentation cell that goes out of band attributes to a unit input
# ("derived: inherits units_public"), and the length-leak check holds the unit
# inputs the way it holds any other measured input. They are reported, NEVER
# gated: the per-file values are already gated by verify_language.py against the
# manifests, and the cross-language spread of `main`'s split is the api-contract
# question the ledger already owns (`units-public-main-outside-api-contract`,
# `units-documented-structural-absences`) -- banding the totals here would count
# the same finding a second time.
UNIT_METRICS = ("units_public", "units_documented", "units_public_documented")

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


# ==============================================================================
# gitgalaxy#2795: THE STRUCTURE COUNTS NEED AN n/a MECHANISM TOO
# ==============================================================================
# `functions_found`, `classes_found` and `dependency_links` do not read a registry
# rule -- they read the engine's own `function_count`/`class_count`/`import_count`
# columns -- so the rule-absence inference that makes a *signal* cell n/a never
# reached them. A language could be simultaneously "has no function concept, do
# not compare" on `func_start` (n/a, excluded from the median) and "records 0
# functions, -100% outlier" on `functions_found` (scored) in the same report: the
# STRUCTURE COUNTS rows were measured over a larger population than the rows they
# summarise. Same defect gitgalaxy#2669 F.3 fixed one family over for `risk_*`.
#
# Each structure count therefore names the registry rule that GOVERNS it -- the
# rule whose matches the engine counts. `dependency_links` is deliberately NOT
# governed by `import`: since gitgalaxy#2638 the DAG is fed by
# `_dependency_capture`, and markdown proves the two diverge -- no `import` rule,
# yet 3 real edges from relative links, a comparable cell that must stay scored.
# No language currently nulls `_dependency_capture`, so that edge produces no
# cell today; it is here so the family is defined consistently rather than
# per-metric, and so na_check gates the absence the day one does.
STRUCTURE_GOVERNORS = {
    "functions_found": "func_start",
    "classes_found": "class_start",
    "dependency_links": "_dependency_capture",
}

# gitgalaxy#2792: a governing rule can be PRESENT and still govern nothing. Five
# languages define a `func_start` whose every match names a slicer bucket rather
# than an identifier anyone wrote -- dockerfile after the `RUN`/`CMD` keyword,
# css after the at-rule, sqlite (mode_e) after the igniter -- so once the engine
# stopped counting those buckets as functions their honest `functions_found` is
# 0, and scoring it would be a BIGGER red deviation than the over-count it
# replaced. The predicate is `_registry.population_less_languages`, read off the
# engine, never hand-listed here. Only `functions_found` has this second way of
# being ungoverned; `class_start` and `_dependency_capture` capture real names in
# every language that defines them.
STRUCTURE_LABEL_ONLY = {"functions_found"}


# ==============================================================================
# gitgalaxy#2866: THE CENSUS NEEDS AN n/a MECHANISM TOO
# ==============================================================================
# `raw_state_unreferenced` is neither a registry rule nor a structure count: it
# is a census computed in the engine's splice over the extracted function list,
# so neither the rule-absence inference nor STRUCTURE_GOVERNORS ever reached
# it. A census over a population that cannot exist and a census whose
# population answered "none" both print 0, and the cell cannot say which --
# jcl sat at 0.00 held in band only by its ledger entry, and the #2549
# undefined family (css, dockerfile, html, markdown, sqlite, yaml) sat at 0.00
# scored red against the 2.50 median. The registry now says which zero is
# which (docs/unreferenced_by_name_contract.md, "The undefined family
# resolved"): the census is UNANSWERABLE for a language when its registry
# declares `invocation_model != by_name` (the units execute in written order --
# jcl #2806; dockerfile/html/sqlite/yaml #2866) or defines no `func_start`
# rule at all (markdown -- no population, the #2795 inference one family
# over). Both predicates read off the engine registry, never hand-listed.
# css deliberately fails both and stays scored: `animation-name` reaches a
# `@keyframes` unit by name, so its census is measured (2.50 on the median).
CENSUS_METRICS = ("raw_state_unreferenced",)


def unmeasurable_census_cells(definitions, observed):
    """n/a cells among the census columns, plus the mismatches found.

    Same shape as `unmeasurable_structure_cells`: a nonzero observation in a
    cell the registry calls unanswerable is a *mismatch*, printed loudly and
    left comparable -- the engine suppresses the census for a positional
    language at the source, so a nonzero here means the declaration is not
    reaching the detector (the gitgalaxy#2806 lens trap's exact symptom).

    Returns ({language: sorted [metric]}, [(language, metric, observed)]).
    """
    na, mismatches = {}, []
    for metric in CENSUS_METRICS:
        for lang, values in sorted(observed.items()):
            defn = definitions.get(lang)
            if defn is None or values.get(metric) is None:
                continue
            unanswerable = defn.get("invocation_model", "by_name") != "by_name" or (
                (defn.get("rules") or {}).get("func_start") is None
            )
            if not unanswerable:
                continue
            value = values[metric]
            if value:
                mismatches.append((lang, metric, value))
            else:
                na.setdefault(lang, []).append(metric)
    return {k: sorted(v) for k, v in na.items()}, mismatches


def classify_census_na(census_na, governor_na_state, ledger_entries=()):
    """{metric: {lang: "ledgered"|"unreviewed"}} for census n/a cells.

    Mirrors `classify_structure_na`'s two doctrines:

      * no `func_start` rule -- the absence is the mechanism, so the cell
        INHERITS the rule's own review status (markdown's lit-plane entry);
      * `invocation_model` declared -- there is no rule absence for na_check
        to have an opinion about, so the declaration is reviewed the ordinary
        way: a validated entry naming the language and the census column
        (`jcl-steps-have-no-invocation-by-name`, the #2866 contract entry).
    """
    validated = [e for e in ledger_entries if e.get("status") == "validated"]
    out = {}
    for lang, metrics in census_na.items():
        for metric in metrics:
            covered = governor_na_state.get("func_start", {}).get(lang) == "ledgered" or any(
                lang in e.get("languages_seen", [])
                and metric in (e.get("signal") or "").split("|")
                for e in validated
            )
            out.setdefault(metric, {})[lang] = "ledgered" if covered else "unreviewed"
    return out


# The risk formulas name their inputs with registry signal names; the recorder
# stores several of them under different column names, and for two the RAW
# pre-adjustment snapshot is the honest one to compare (see MEASURE_COLS).
# Without this map the derivation edges below silently never match.
RISK_INPUT_COLUMNS = {
    "api": "raw_arch_api",
    "encapsulation": "def_encapsulation",
    "unreferenced_by_name": "raw_state_unreferenced",
    "duplicate_logic": "state_slop_duplicates",
}


def out_of_band_cells(metrics, languages, refs=None, presence=None):
    """{(metric, lang)} for every comparable cell outside the green band.

    Mirrors _row_stats' banding: a zero median is scored on exact agreement, so a
    nonzero value there is out of band and everything else is in. `refs` is
    reference_medians()' output; without it every cell is banded against the
    global median. `presence` is {metric: {lang: declaration stratum}}; a metric
    it names is banded on the gitgalaxy#2796 container-PRESENCE rule instead, so the
    gate and the chart agree on what is out of band.
    """
    out = set()
    refs = refs or {}
    presence = presence or {}
    for metric, values in metrics.items():
        pres = presence.get(metric)
        nums = [v for v in (values.get(lang) for lang in languages) if isinstance(v, (int, float))]
        if not nums:
            continue
        global_med = statistics.median(nums)
        for lang in languages:
            v = values.get(lang)
            if not isinstance(v, (int, float)):
                continue
            if pres is not None:
                p = pres.get(lang)
                if p is None:
                    continue
                ok = (v >= 1) if p == "container-required" else (v == 0)
                if not ok:
                    out.add((metric, lang))
                continue
            med = refs.get(metric, {}).get(lang, global_med)
            if med == 0:
                if v != 0:
                    out.add((metric, lang))
            elif abs((v - med) / med) > GREEN_DEV:
                out.add((metric, lang))
    return out


def ledger_incomparable_cells(ledger_entries):
    """{(signal, language)} declared CROSS-PLANT-INCOMPARABLE by a validated entry.

    gitgalaxy#2796: an entry with disposition "cross-plant-incomparable" states that a
    signal's value in a language is dictated by a DIFFERENT plant (kotlin's class count
    IS its `globals` plant), so it is not a comparable reading of that signal and is
    treated as n/a -- distinct from the structure/census n/a passes, which fire on a
    language whose registry has no rule for the signal at all.
    """
    out = set()
    for e in ledger_entries:
        if (e.get("status") == "validated"
                and e.get("still_reproduces") is not False
                and e.get("disposition") == "cross-plant-incomparable"):
            for signal in (e.get("signal") or "").split("|"):
                for lang in e.get("languages_seen", []):
                    if signal:
                        out.add((signal, lang))
    return out


def explain_out_of_band(metrics, languages, ledger_entries, structure, risk_inputs=None,
                        strata=None, constant_sensitive=(), ungated=None, presence=None):
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
    # A retired entry (still_reproduces: false -- the upstream fix landed, verified by
    # a fresh scan) explains nothing any more: a cell it used to name either sits in
    # band now or has a live cause of its own to record. Until 2026-09-06 the gate
    # honoured retired entries, which let three cells (m4/makefile risk_api_exposure,
    # m4 risk_documentation) coast on api-double-count-inflates-scored-api for four
    # days after #2734 fixed it.
    validated = [
        e for e in ledger_entries
        if e.get("status") == "validated" and e.get("still_reproduces") is not False
    ]
    ungated = set(ungated) if ungated is not None else set(CONTEXT_METRICS)
    refs = reference_medians(metrics, languages, strata, constant_sensitive)
    oob = out_of_band_cells(metrics, languages, refs, presence=presence)
    verdicts = {}
    for metric, lang in sorted(oob):
        if metric in ungated:
            # F.1/F.3: length, unplanted inputs and temporal columns are reported,
            # never gated. The cell stays in `oob` so a derived metric can still
            # inherit from it below.
            continue
        # None since gitgalaxy#2795: the language has no function CONCEPT, which
        # is the same "no population to divide by" this verdict exists for -- a
        # stricter `== 0` would have silently dropped markdown's descriptors back
        # into the scored set the moment its count became n/a.
        funcs = (structure.get("functions_found") or {}).get(lang)
        if metric in PER_FUNCTION_METRICS and funcs in (0, None):
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


# ==============================================================================
# CAUSE CATEGORIES (gitgalaxy docs/contract_roadmap.md, Phase 0)
# ==============================================================================
# A verdict says whether a red cell is ACCOUNTED FOR; it does not say what the cell
# IS. The consistency badge paints every out-of-band cell the same red whether the
# ledger validated it as "this language cannot express that" or as an open engine
# defect -- which is why the epic kept reading as an extraction problem. The roll-up
# below folds each ledgered cell's dispositions into one of five causes, most severe
# first when an entry list mixes them, and reports an OPEN-DEFECT SHARE next to the
# consistency score: the share of comparable cells whose only explanation is an
# engine finding somebody still owes. It changes no verdict and nothing about --gate.
CELL_CATEGORIES = ("unexplained", "extraction", "correlation", "scoring", "inherency", "echo")
CATEGORY_MEANING = {
    "unexplained": "survived every mechanism -- the gate fails on these",
    "extraction": "a rule matches the wrong construct, or two rules claim one token "
                  "(upstream-bug, upstream-question, engine-defect, keyword-overlap)",
    "correlation": "a proximity pair in spatial_correlation.py used to edit the recorded count "
                   "(the x3 cascading flux, the silencer dampener); since gitgalaxy#2815 (Phase 2) "
                   "they are tallies applied only in the score layer's weighted view",
    "scoring": "a deliberate engine choice in a formula or a path modifier (engine-semantic)",
    "inherency": "the best the language can do: intended-morphology, or a per-function "
                 "descriptor where the language has no functions",
    "echo": "derived -- an upstream deviation counted again downstream",
}
_DISPOSITION_CATEGORY = {
    "upstream-bug": "extraction", "upstream-question": "extraction",
    "engine-defect": "extraction", "keyword-overlap": "extraction",
    "engine-semantic": "scoring",
    "intended-morphology": "inherency", "language-morphology": "inherency",
}
# engine-semantic entries that record a recorded-count edit by a proximity pair rather
# than a formula choice. The disposition vocabulary has no value for this, so they are
# named; gitgalaxy#2546/#2631 documents the mechanism, gitgalaxy#2815 (roadmap Phase 2)
# moved it out of the recorded counts -- `state-flux-branch-weighting` is retired
# (still_reproduces false); `string-literal-selective-shielding` still explains which
# rules count a keyword inside a literal, a stream fact rather than a correlation one,
# and whether it stays in this set is the Phase 0 owner's call.
# Empty since gitgalaxy#2815 (Phase 2): the recorded count is the raw count, so no
# validated entry describes a proximity edit any more. state-flux-branch-weighting is
# retired; string-literal-selective-shielding never was one (strings count uniformly,
# #2535) and its 2026-09-06 narrowing says so. Kept as the hook for any future entry
# of that shape.
CORRELATION_ENTRIES = frozenset()
# Which categories count as an open defect for the headline: everything the engine
# still owes an answer on. Scoring choices are ledgered design; inherency and echo
# are not findings at all.
OPEN_DEFECT_CATEGORIES = frozenset({"unexplained", "extraction", "correlation"})


def categorize_out_of_band(verdicts, ledger_entries):
    """{(metric, lang): category} for every gated out-of-band cell.

    `verdicts` is explain_out_of_band()'s output. A ledgered cell naming several
    entries takes the most severe category among them (CELL_CATEGORIES order),
    so a cell that is half morphology and half open bug reads as the bug.
    """
    by_id = {e["id"]: e for e in ledger_entries}
    out = {}
    for cell, (status, detail) in verdicts.items():
        if status == "derived":
            out[cell] = "echo"
        elif status == "undefined":
            out[cell] = "inherency"
        elif status == "unexplained":
            out[cell] = "unexplained"
        else:
            cats = []
            for eid in detail.split(", "):
                entry = by_id.get(eid)
                if entry is None:
                    continue
                if eid in CORRELATION_ENTRIES:
                    cats.append("correlation")
                else:
                    cats.append(_DISPOSITION_CATEGORY.get(entry.get("disposition"), "scoring"))
            out[cell] = min(cats, key=CELL_CATEGORIES.index) if cats else "unexplained"
    return out


def open_defect_share(metrics, languages, categories, ungated=()):
    """{metric: (open_defect_cells, comparable_cells)} for every gated metric.

    Comparable = the languages with a numeric value (n/a excluded, as in the
    consistency score). A cell not in `categories` is in band. This is the
    number the consistency badge cannot express: how much of a metric's red
    is a finding somebody still owes, as opposed to accepted design, language
    morphology or an echo of another cell.
    """
    out = {}
    for metric, values in metrics.items():
        if metric in ungated:
            continue
        comparable = [lang for lang in languages if isinstance(values.get(lang), (int, float))]
        if not comparable:
            continue
        open_cells = sum(
            1 for lang in comparable
            if categories.get((metric, lang)) in OPEN_DEFECT_CATEGORIES
        )
        out[metric] = (open_cells, len(comparable))
    return out


def decayed_entries(ledger_entries, oob_cells, na_cells=frozenset()):
    """Validated, still-reproducing entries whose signal x languages_seen names
    no out-of-band cell and no n/a cell (keyword-rosetta#75's check, made standing).

    An entry earns its keep two ways: it explains a red cell, or it is the
    reviewed reason an n/a cell is n/a (GATING.md "Unreviewed absences stay
    loud"). One that does neither -- every cell it claims sits in band -- is
    excusing nothing: the upstream fix landed and `still_reproduces` was never
    flipped, or the cross-product over-claims. Returns [(entry_id, claimed)].
    """
    out = []
    for e in ledger_entries:
        if e.get("status") != "validated" or e.get("still_reproduces") is False:
            continue
        signals = [s for s in (e.get("signal") or "").split("|") if s]
        langs = e.get("languages_seen") or []
        if not signals or not langs or langs == ["all"]:
            continue
        claimed = [(s, l) for s in signals for l in langs]
        if not any(c in oob_cells or c in na_cells for c in claimed):
            out.append((e["id"], len(claimed)))
    return out


def derivation_inputs(metric, risk_inputs=None, include_context=False):
    """The measured inputs a derived metric is built from, as cache column names.

    DERIVED_INPUTS for the structural composites; the engine's own risk assembly
    (`risk_inputs`, read off `_registry.risk_dependencies` at regen time) for the
    risk_* family; () for a metric with no known edges. `engine` inputs
    (unreferenced_by_name, duplicate_logic, the sec_* family) are synthesized downstream
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
        # gitgalaxy#2908 Phase 3: the per-unit edges (units_public /
        # units_documented), already cache column names.
        ) + tuple(spec.get("units", ()))
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
    # gitgalaxy#2908 Phase 3 replaced the density formula: the score is now a
    # pure per-unit coverage ratio (public-weighted units exposed / total, x the
    # umbrella shield) with NO loc term, no floor, no sigmoid. This entry is the
    # proof the epic's leak row asked for: any residual rank correlation is the
    # units_public/units_documented composition of `main` (the api-contract
    # split, ledgered `units-public-main-outside-api-contract`) riding the band
    # tolerance of the held unit inputs -- unit composition, not length.
    "risk_documentation": "no LOC term since gitgalaxy#2908 Phase 3: a pure per-unit coverage "
                          "ratio (signal_processor.py `_calc_documentation`), constant across "
                          "languages sharing the held unit profile -- the rho -0.83 leak this "
                          "row used to carry is resolved by construction; variation between "
                          "profiles is main's units_public/units_documented split, the api "
                          "contract cells",
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
        # gitgalaxy#2908 Phase 4: a POPULATION-BASED formula (per-unit `units`
        # edges) is a PURE function of its held inputs -- no loc, no constant,
        # nothing else free. The band-hold above is the wrong instrument there:
        # ±25% leaves unit-composition variation on the table (main's 12-vs-13
        # public split, the api contract cells), and any correlation it produces
        # is input composition wearing length's rank order, not a LOC term. So
        # these are held EXACTLY: within the languages sharing the modal held
        # profile, the score must be constant -- emitted as verdict "invariant",
        # the proof row #2908 asked the leak table to carry. Residual variation
        # inside an exactly-held profile would be a real finding and is
        # correlated like any other metric.
        spec = (risk_inputs or {}).get(metric) or {}
        if spec.get("units"):
            profiles = collections.Counter(
                tuple(metrics[i].get(lang) for i in held) for lang in langs
            )
            if not profiles:
                continue
            modal = max(profiles, key=profiles.get)
            langs = [
                lang for lang in langs
                if tuple(metrics[i].get(lang) for i in held) == modal
            ]
            if len(langs) < LEAK_MIN_LANGUAGES:
                continue
            if len({values[lang] for lang in langs}) < 2:
                out.append({
                    "metric": metric,
                    "n": len(langs),
                    "rho": 0.0,
                    "verdict": "invariant",
                    "held": list(held),
                    "stratum": None,
                    "where": LENGTH_TERMS.get(metric),
                })
                continue
            rho = _spearman([xs_all[lang] for lang in langs], [values[lang] for lang in langs])
            if abs(rho) < LEAK_WEAK_RHO:
                continue
            out.append({
                "metric": metric,
                "n": len(langs),
                "rho": round(rho, 3),
                "verdict": "leak" if abs(rho) >= LEAK_RHO else "weak",
                "held": list(held),
                "stratum": None,
                "where": LENGTH_TERMS.get(metric),
            })
            continue
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
    out.sort(key=lambda r: (r["verdict"] == "invariant", -abs(r["rho"])))
    return out


def unmeasurable_risk_cells(deps, definitions, observed, populations=None):
    """n/a cells among the DERIVED risk_* metrics, plus the mismatches found.

    `populations` is {language: functions_found} (0 or None = no unit population)
    for the population-based formulas -- see the gitgalaxy#2908 branch below.

    The planted signals get n/a straight off the registry: no rule, no nonzero,
    incomparable (docs/GATING.md). The risk_* columns are one step downstream --
    formulas over those same signals -- and had no n/a mechanism at all, so a
    language whose inputs are structurally absent was scored as a -100% outlier
    against languages that actually measured something.

    A risk metric is n/a for a language only when ALL FOUR hold:

      1. its formula consumes at least one registry-governed signal;
      2. every one of those signals has a None rule for that language;
      3. it consumes no engine-derived input (unreferenced_by_name, duplicate_logic,
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
        # gitgalaxy#2908 Phase 3 (D6): a POPULATION-BASED formula (non-empty
        # `units` edges) is a ratio over the extracted units, so its n/a basis
        # is an empty unit population -- `functions_found` 0 or itself n/a --
        # never rule absence. Its governed signals (per-unit reflection) are
        # weight modifiers, not the measurable substance: a language with no
        # reflection rule still has a fully measurable documentation ratio.
        if dep.get("units"):
            for lang, values in sorted(observed.items()):
                if metric not in values:
                    continue
                if (populations or {}).get(lang) not in (0, None):
                    continue
                value = values[metric]
                if value:
                    mismatches.append((lang, metric, value))
                else:
                    na.setdefault(lang, []).append(metric)
            continue
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
    # gitgalaxy#2795: and the rules that govern the structure counts, for the same
    # reason -- `_dependency_capture` is not planted and not a risk input, but a
    # language that nulled it would make `dependency_links` incomparable, and an
    # absence nothing has reviewed must stay loud rather than quietly excuse a cell.
    return sorted(set(PLANTED) | extra | set(STRUCTURE_GOVERNORS.values()))


def classify_risk_na(risk_na, deps, signal_na_state, population_state=None):
    """{metric: {lang: "ledgered"|"unreviewed"}} for derived n/a cells.

    `population_state` is {language: bool} -- whether the language's empty unit
    population is itself accounted for -- consumed by the population-based
    branch (gitgalaxy#2908 Phase 3).

    A derived n/a is a mechanical consequence of its input signals' absences, so
    it inherits their review status rather than opening a parallel backlog: the
    cell is "ledgered" only when EVERY governed input is itself ledgered for that
    language. An input nobody has reviewed keeps the derived cell loud too --
    GATING.md rule 2, composed. `signal_na_state` is classify_na()'s output.
    """
    out = {}
    for lang, metrics in risk_na.items():
        for metric in metrics:
            if deps[metric].get("units"):
                # gitgalaxy#2908 Phase 3 (D6): a population-based n/a inherits
                # the review state of the POPULATION's own absence -- the
                # structure-count n/a for functions_found (markdown, sqlite) or
                # a validated entry that names functions_found for a language
                # whose population records a comparable 0 (html,
                # `html-probe-bodies-are-empty-by-design`).
                covered = (population_state or {}).get(lang, False)
            else:
                covered = all(
                    signal_na_state.get(sig, {}).get(lang) == "ledgered"
                    for sig in deps[metric]["governed"]
                )
            out.setdefault(metric, {})[lang] = "ledgered" if covered else "unreviewed"
    return out


def unmeasurable_structure_cells(definitions, observed, population_less=()):
    """n/a cells among the STRUCTURE COUNT columns, plus the mismatches found.

    Same four-condition test gitgalaxy#2669 F.3 defined for the derived risk_*
    columns (`unmeasurable_risk_cells`), applied one family over. A structure
    count is n/a for a language only when ALL FOUR hold:

      1. the column has a governing registry rule at all (STRUCTURE_GOVERNORS);
      2. that rule governs nothing for this language -- either it is None, or
         (gitgalaxy#2792, `functions_found` only) it is present but can never
         capture an author-written name, so the engine can never populate the
         column from source and a 0 means "not expressible as measured";
      3. the count reads no engine-synthesized input that can be nonzero
         regardless of the registry. True by construction for this family: each
         column is `len()` of exactly what its governing rule produced;
      4. the observed value really is 0 -- the scan confirming that 1-3 pinned it.

    (4) is the same rug-guard as F.3's, and it is not theoretical here: the slicer
    synthesizes buckets in modes that never consult `func_start` at all, and
    orphan conversion synthesizes `api`. A cell that passes 1-3 and still measures
    nonzero is returned as a *mismatch* and left comparable -- printed loudly,
    never absorbed.

    Returns ({language: sorted [metric]}, [(language, metric, observed)]).
    """
    rules = {lang: d.get("rules") or {} for lang, d in definitions.items()}
    population_less = set(population_less or ())
    na, mismatches = {}, []
    for metric, governor in sorted(STRUCTURE_GOVERNORS.items()):
        for lang, values in sorted(observed.items()):
            if lang not in rules or metric not in values:
                continue
            ungoverned = rules[lang].get(governor) is None or (
                metric in STRUCTURE_LABEL_ONLY and lang in population_less
            )
            if not ungoverned:
                continue
            value = values[metric]
            if value:
                mismatches.append((lang, metric, value))
            else:
                na.setdefault(lang, []).append(metric)
    return {k: sorted(v) for k, v in na.items()}, mismatches


def classify_structure_na(structure_na, signal_na_state, ledger_entries=()):
    """{metric: {lang: "ledgered"|"unreviewed"}} for structure-count n/a cells.

    Two ways to be reviewed, matching the two ways a governing rule can govern
    nothing:

      * the rule is ABSENT -- inherited, not invented (`classify_risk_na`'s
        doctrine): the count carries the rule's own review status and opens no
        parallel backlog row, so na_check.py keeps auditing language/signal.
      * the rule is PRESENT but names only slicer buckets (gitgalaxy#2792). There
        is no rule absence for na_check to have an opinion about, so this one is
        reviewed the ordinary way -- a validated entry naming the language and
        the COUNT (`slicer-segments-statements-not-functions`). Inheriting here
        would be wrong twice over: it would read a review of `func_start`'s
        presence as a review of what its matches mean.
    """
    validated = [e for e in ledger_entries if e.get("status") == "validated"]
    out = {}
    for lang, metrics in structure_na.items():
        for metric in metrics:
            governor = STRUCTURE_GOVERNORS[metric]
            covered = signal_na_state.get(governor, {}).get(lang) == "ledgered" or any(
                lang in e.get("languages_seen", [])
                and metric in (e.get("signal") or "").split("|")
                for e in validated
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
    "raw_state_unreferenced": "Unreferenced by name", "def_encapsulation": "Encapsulation (raw)",
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
# Chart groups, in pipeline order. Titles key CHART_BLURBS; the four not-gated groups
# are drawn with a "NOT GATED*" tag and the footnote explains why (D4 step 2 of
# gitgalaxy docs/contract_roadmap.md). Gating semantics live in CONTEXT_METRICS /
# VOCABULARY_METRICS / ungated_metrics(), not here: this is only how the picture reads.
CHART_STRUCTURE = ["func_start", "args", "class_start", "functions_found", "classes_found", "dependency_links"]
CHART_GRAPH = ["pagerank_score", "normalized_blast_radius", "betweenness_score", "closeness_score",
               "producer_ratio", "popularity", "dependency_density"]
CHART_LENGTH = ["total_loc", "coding_loc", "avg_func_loc", "comment_lines"]
CHART_VOCAB = ["token_mass", "keyword_hits", "structural_mass", "control_flow_ratio"]
# Rows the chart skips because they duplicate another row; the report tables and
# the cache keep them. pagerank (structure count) == pagerank_score (measure) in
# every language: same number, two columns.
CHART_HIDDEN = {"pagerank": "identical to pagerank_score"}
CHART_BLURBS = {
    "structural extraction": "the slicer: functions, parameters, classes and dependency edges — the spread of one program's counts across languages, not recall",
    "keyword extraction": "one rule per signal; every count here was planted on purpose, in every language",
    "non-planted keyword extraction": "rules the risk formulas read that the corpus never plants — nothing here was written, so every language should read 0",
    "dependency graph creation": "graph measures over the same three planted imports (pagerank_score = pagerank; shown once)",
    "internal function metrics": "per-function and census measures derived from the signals",
    "calculated risk exposure — per file": "what the product reports, per file (banded within the strictness stratum where a constant is read)",
    "program size & vocabulary": "how long the same program came out, and how the language spells it: token and keyword tallies, and the ratios that divide by them",
    "per-unit attributes": "unit totals the per-unit risk ratios read (gitgalaxy#2908); gated per file by the manifests, reported here as attribution edges",
    "commit age": "temporal, not content",
}


def _pretty(name):
    return name


def _kept_languages(languages, values, medians, presence=None):
    """The languages _row_stats kept for this row, in the order its devs come back."""
    if languages is None:
        return None
    if presence is not None:
        # gitgalaxy#2796: mirror _row_stats' presence path -- same filter, same order.
        return [l for l, v, p in zip(languages, values, presence) if v is not None and p is not None]
    if medians is not None:
        pairs = [(l, v, m) for l, v, m in zip(languages, values, medians) if v is not None and m is not None]
        if pairs and all(m > 0 for _, _, m in pairs):
            return [l for l, _, _ in pairs]
    return [l for l, v in zip(languages, values) if v is not None]


def _esc(t):
    return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _fit_labels(items, width, char_w=4.9, gap=6):
    """Keep the most extreme labels that fit in `width`; items = [(x, lang, dev)]."""
    items = sorted(items, key=lambda t: -abs(t[2]))
    kept, used = [], 0.0
    for x, lang, dev in items:
        w = len(lang) * char_w + gap
        if used + w > width:
            break
        kept.append((x, lang))
        used += w
    return sorted(kept)


def _place_labels(items, lo, hi, char_w=4.9, gap=6):
    """items = [(x, text)] sorted by x -> [(x_center, text)] pushed apart so the label
    boxes never overlap and stay inside [lo, hi]: one pass right, one pass back left."""
    out = []
    for x, text in items:
        w = len(text) * char_w
        x = max(lo + w / 2, min(hi - w / 2, x))
        if out:
            px, ptext = out[-1]
            need = (len(ptext) * char_w) / 2 + w / 2 + gap
            if x - px < need:
                x = px + need
        out.append([x, text])
    for i in range(len(out) - 1, -1, -1):
        x, text = out[i]
        w = len(text) * char_w
        if x + w / 2 > hi:
            out[i][0] = hi - w / 2
        if i + 1 < len(out):
            nx, ntext = out[i + 1]
            need = (len(ntext) * char_w) / 2 + w / 2 + gap
            if nx - out[i][0] < need:
                out[i][0] = nx - need
    return [(x, t) for x, t in out]


def write_variance_chart(groups, n_langs, na_by_metric=None, medians=None,
                         languages=None, unexplained=(), categories=None, headline=None,
                         presence=None):
    """Strip-plot SVG. groups = [(title, {metric: [values-per-language]}, gated)].

    Colour encodes CAUSE, not magnitude (gitgalaxy docs/contract_roadmap.md D4):
    a dot inside the band is green; outside it, red when `categories` says the
    cell is an open engine defect (OPEN_DEFECT_CATEGORIES) and grey when it is a
    documented variation (a scoring choice, language inherency, an echo). Each
    gated row carries a three-share bar -- in band / documented / open defect --
    with the ACCOUNTED share printed inside (in band + documented: every
    comparable cell whose verdict is not an open defect; a documented variation
    is measured and explained, so it does not subtract from the badge) and the
    open-defect count after it. The in-band story stays as counts: the n/n label
    in the band's corner and a "N doc" tally in the row's mono extras.
    Languages at the same strip position collapse into ONE dot sized by
    population, with the count printed for clusters -- so "40 languages sit
    exactly on the median" is visible instead of 40 overplotted circles.
    Open-defect languages are named above the strip, documented ones below; on
    not-gated rows the languages beyond +-50% are named. Every group opens with
    an axis row and faint guides at +-25% / +-50%.

    `medians` = {metric: [per-language reference median]} for rows banded against
    something other than the global median (F.3). `languages` aligns with each
    metric's value list. `unexplained` = {(metric, lang)} drawn as a red ring.
    `categories` = {(metric, lang): cause} from categorize_out_of_band().
    `headline` = (open_defect_cells, comparable_cells) from open_defect_share(), so
    the tile prints the same number the report does; computed from the drawn rows
    when absent. Returns (shares, skipped, inert, agreement) exactly as before.
    """
    label_w, bar_w, strip_w, pad, row_h = 256, 118, 560, 16, 36
    width = pad + label_w + pad + bar_w + pad + strip_w + pad
    strip_x0 = pad + label_w + pad + bar_w + pad
    half = strip_w / 2
    px_per_dev = half / 1.1
    unexplained = set(unexplained)
    categories = categories or {}
    na_by_metric = na_by_metric or {}

    def x_of(dev):
        return strip_x0 + half + max(-1.1, min(1.1, dev)) * px_per_dev

    ink, muted, faint = "#1b2430", "#5c6670", "#9aa4ad"
    green, band = "#2f855a", "#dcefe0"
    grey_dot, grey_lab, red, red_lab = "#a3acb3", "#6b7680", "#c0392b", "#9e2b21"

    prepared, shares, n_rows, skipped, inert, agreement = [], {}, 0, [], [], []
    for title, metrics, gated in groups:
        rows = []
        for name, values in metrics.items():
            if name in CHART_HIDDEN:
                continue
            row_meds = (medians or {}).get(name)
            row_pres = (presence or {}).get(name)
            st = _row_stats(values, row_meds, presence=row_pres)
            if st is None:
                (inert if is_inert(values) else skipped).append(name)
                continue
            devs, green_share, med, basis = st
            kept = _kept_languages(languages, values, row_meds, presence=row_pres) or []
            n = len(devs)
            n_open = sum(1 for i, d in enumerate(devs)
                         if abs(d) > GREEN_DEV and i < len(kept)
                         and categories.get((name, kept[i])) in OPEN_DEFECT_CATEGORIES)
            n_doc = sum(1 for d in devs if abs(d) > GREEN_DEV) - n_open
            rows.append((name, devs, green_share, med, basis, kept, n_open, n_doc))
            if gated:
                shares[name] = green_share
            if basis == "agreement":
                agreement.append(name)
        # best -> worst: least open defect first, then most in band
        rows.sort(key=lambda r: (r[6] / max(len(r[1]), 1), -r[2]))
        if rows:
            prepared.append((title, rows, gated))
            n_rows += len(rows)

    avg_share = statistics.mean(shares.values()) if shares else 0.0
    if headline:
        n_open_cells, n_comparable = headline
    else:
        n_open_cells = sum(r[6] for _, rows, gated in prepared if gated for r in rows)
        n_comparable = sum(len(r[1]) for _, rows, gated in prepared if gated for r in rows)
    open_share = n_open_cells / n_comparable if n_comparable else 0.0

    header_h = 200
    height = header_h + sum(54 for _ in prepared) + n_rows * row_h + 62
    s = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'font-family="Inter, system-ui, sans-serif" font-size="12">',
        f'<rect width="{width}" height="{height}" fill="#ffffff"/>',
        f'<text x="{pad}" y="30" font-size="19" font-weight="700" fill="{ink}">'
        f"One program, {n_langs} languages — does GitGalaxy count it the same everywhere?</text>",
        f'<text x="{pad}" y="52" fill="{muted}">The same 12-probe program, written in every language. The engine should '
        f"extract the same counts from each;</text>",
        f'<text x="{pad}" y="68" fill="{muted}">every dot is one language\'s deviation from the cross-language median. '
        f'<tspan font-weight="600" fill="{red}">Red</tspan> is an open engine defect — a rule matching the wrong construct,</text>',
        f'<text x="{pad}" y="84" fill="{muted}">or a scoring weight sitting inside a count — the work left. '
        f'<tspan font-weight="600" fill="{grey_lab}">Grey</tspan> is a documented variation: the language cannot express the construct,</text>',
        f'<text x="{pad}" y="100" fill="{muted}">a deliberate scoring choice, or an echo of another row. Each row\'s bar: in band '
        f"(±{GREEN_DEV:.0%} of the median) · documented · open defect; the badge prints the accounted share — "
        f"everything that is not an open defect.</text>",
    ]
    tiles = [
        (f"{open_share:.1%}", f"open-defect share · {n_open_cells} of {n_comparable} cells", red),
        (f"{avg_share:.0%}", f"average share in band, {len(shares)} gated metrics", ink),
        (f"{len(unexplained)}", "cells with no verdict at all", ink),
        (f"{n_langs}", "languages", ink),
    ]
    tile_w = (width - pad * 2) / len(tiles)
    for i, (big, cap, col) in enumerate(tiles):
        tx = pad + i * tile_w
        s.append(f'<text x="{tx:.0f}" y="134" font-size="22" font-weight="700" fill="{col}">{big}</text>')
        s.append(f'<text x="{tx:.0f}" y="150" font-size="10.5" fill="{muted}">{cap}</text>')
    ly, lx = 174, pad
    legend = [(green, "in band"), (grey_dot, "documented variation"), (red, "open defect"),
              ("cluster", "count = languages on that dot"),
              ("ring", "no verdict yet"), ("na", "n/a — no rule for this language")]
    for col, lab in legend:
        if col == "cluster":
            s.append(f'<circle cx="{lx + 5}" cy="{ly - 4}" r="5.5" fill="{green}" fill-opacity=".85"/>')
            s.append(f'<text x="{lx + 5}" y="{ly - 1.5}" font-size="7" font-weight="700" fill="#ffffff" '
                     f'text-anchor="middle">3</text>')
        elif col == "ring":
            s.append(f'<circle cx="{lx + 5}" cy="{ly - 4}" r="5" fill="none" stroke="{red}" stroke-width="1.6"/>')
        elif col == "na":
            s.append(f'<text x="{lx}" y="{ly}" font-size="9.5" fill="{faint}" font-family="ui-monospace, Menlo, monospace">n/a</text>')
            lx += 14
        else:
            s.append(f'<circle cx="{lx + 5}" cy="{ly - 4}" r="4.5" fill="{col}" fill-opacity=".7"/>')
        s.append(f'<text x="{lx + 15}" y="{ly}" font-size="10.5" fill="{muted}">{lab}</text>')
        lx += 15 + len(lab) * 6.2 + 22
    s.append(f'<text x="{pad}" y="{ly + 15}" font-size="10.5" fill="{faint}">'
             f"strip: median at the centre · shaded band ±{GREEN_DEV:.0%} · ticks ±50% · clipped at ±110% · "
             f"open-defect languages named above the strip, documented ones below (not-gated rows: beyond ±50%)</text>")

    y = header_h
    for title, rows, gated in prepared:
        y += 24
        s.append(f'<line x1="{pad}" y1="{y - 14}" x2="{width - pad}" y2="{y - 14}" stroke="#e3e6ea"/>')
        s.append(f'<text x="{pad}" y="{y + 4}" font-size="13" font-weight="700" fill="{ink}" '
                 f'letter-spacing=".6">{_esc(title.upper())}</text>')
        tx = pad + 8.2 * len(title) + 20
        if not gated:
            s.append(f'<text x="{tx:.0f}" y="{y + 4}" font-size="10" font-weight="700" fill="{faint}" '
                     f'letter-spacing=".5">NOT GATED*</text>')
            tx += 78
        blurb = CHART_BLURBS.get(title, "")
        if blurb:
            s.append(f'<text x="{tx:.0f}" y="{y + 4}" font-size="11.5" fill="{muted}">{_esc(blurb)}</text>')
        if gated and rows:
            gavg = statistics.mean(r[2] for r in rows)
            g_open = sum(r[6] for r in rows)
            g_n = sum(len(r[1]) for r in rows)
            s.append(f'<text x="{width - pad}" y="{y + 4}" font-size="11.5" font-weight="700" fill="{ink}" text-anchor="end">'
                     f'group: {gavg:.0%} in band · <tspan fill="{red}">{g_open} open defect{"" if g_open == 1 else "s"} '
                     f'({g_open / g_n:.0%})</tspan></text>')
        y += 22
        ay = y + 2
        for dev, lab in ((-1.0, "−100%"), (-0.5, "−50%"), (-GREEN_DEV, f"−{GREEN_DEV:.0%}"), (0, "median"),
                         (GREEN_DEV, f"+{GREEN_DEV:.0%}"), (0.5, "+50%"), (1.0, "+100%")):
            s.append(f'<text x="{x_of(dev):.1f}" y="{ay}" font-size="8.5" fill="{faint}" text-anchor="middle" '
                     f'font-family="ui-monospace, Menlo, monospace">{lab}</text>')
        group_top = ay + 4
        group_bottom = group_top + len(rows) * row_h
        for dev in (-0.5, -GREEN_DEV, GREEN_DEV, 0.5):
            s.append(f'<line x1="{x_of(dev):.1f}" y1="{group_top}" x2="{x_of(dev):.1f}" y2="{group_bottom}" '
                     f'stroke="#d9dee2" stroke-dasharray="1,3"/>')
        y += 8
        for name, devs, green_share, med, basis, kept, n_open, n_doc in rows:
            cy = y + row_h / 2
            n = len(devs) or 1
            s.append(f'<text x="{pad}" y="{cy + 4}" fill="{ink}" font-size="12" '
                     f'font-family="ui-monospace, Menlo, monospace">{_esc(name)}</text>')
            extras = []
            if basis == "agreement":
                extras.append("exact")
            elif basis == "declaration":
                extras.append("presence")
            n_na = len(na_by_metric.get(name, {}))
            if n_na:
                extras.append(f"n/a {n_na}")
            if gated and n_doc:
                extras.append(f"{n_doc} doc")
            if extras:
                s.append(f'<text x="{pad + label_w}" y="{cy + 4}" fill="{faint}" font-size="9" text-anchor="end" '
                         f'font-family="ui-monospace, Menlo, monospace">{" · ".join(extras)}</text>')
            bx = pad + label_w + pad
            if gated:
                bh = 14
                g_w, d_w, o_w = bar_w * green_share, bar_w * n_doc / n, bar_w * n_open / n
                s.append(f'<rect x="{bx}" y="{cy - bh / 2}" width="{bar_w}" height="{bh}" fill="#eceff2" rx="2"/>')
                s.append(f'<rect x="{bx}" y="{cy - bh / 2}" width="{g_w:.1f}" height="{bh}" fill="{green}" rx="2"/>')
                if d_w:
                    s.append(f'<rect x="{bx + g_w:.1f}" y="{cy - bh / 2}" width="{d_w:.1f}" height="{bh}" fill="{grey_dot}"/>')
                if o_w:
                    s.append(f'<rect x="{bx + g_w + d_w:.1f}" y="{cy - bh / 2}" width="{o_w:.1f}" height="{bh}" fill="{red}"/>')
                # The badge prints the ACCOUNTED share (everything that is not an
                # open defect), not the in-band share: a documented variation is a
                # measured, explained difference -- next to a group called
                # "structural extraction", printing the in-band share read as
                # recall ("it only finds 95% of functions") when the misses are 0.
                # The in-band count keeps its n/n label in the band's corner.
                acct = (n - n_open) / n
                inside = acct >= 0.3
                s.append(f'<text x="{(bx + 5) if inside else (bx + g_w + d_w + o_w + 5):.1f}" y="{cy + 4}" font-size="10.5" '
                         f'font-weight="700" fill="{"#ffffff" if inside else ink}">{acct:.0%}</text>')
                if n_open:
                    s.append(f'<text x="{bx + bar_w + 4}" y="{cy + 4}" font-size="9" font-weight="700" fill="{red}">{n_open}</text>')
            else:
                s.append(f'<text x="{bx + bar_w}" y="{cy + 4}" font-size="10" fill="{faint}" text-anchor="end">not gated*</text>')
            sh = 12
            s.append(f'<rect x="{x_of(-1.1):.1f}" y="{cy - sh / 2}" width="{strip_w}" height="{sh}" fill="#f4f5f7" rx="3"/>')
            s.append(f'<rect x="{x_of(-GREEN_DEV):.1f}" y="{cy - sh / 2}" '
                     f'width="{x_of(GREEN_DEV) - x_of(-GREEN_DEV):.1f}" height="{sh}" fill="{band}"/>')
            for e in (-0.5, 0.5):
                s.append(f'<line x1="{x_of(e):.1f}" y1="{cy - sh / 2}" x2="{x_of(e):.1f}" y2="{cy + sh / 2}" '
                         f'stroke="#cfd5da" stroke-dasharray="2,2"/>')
            s.append(f'<line x1="{x_of(0):.1f}" y1="{cy - sh / 2 - 2}" x2="{x_of(0):.1f}" y2="{cy + sh / 2 + 2}" stroke="{faint}"/>')
            # Languages at the same strip position and cause collapse into one
            # dot sized by population, count printed for clusters. 40 languages
            # agreeing exactly used to render as 40 fully-overplotted circles --
            # the row's strongest claim, invisible. Cluster key rounds the pixel
            # position, so exact ties collapse and near-ties (< 0.1px apart)
            # merge rather than smear; a mixed-cause tie stays two dots.
            red_labels, grey_labels, clusters, rings = [], [], {}, []
            for i, d in enumerate(devs):
                lang = kept[i] if i < len(kept) else None
                if abs(d) <= GREEN_DEV:
                    col = green
                elif not gated:
                    col = grey_dot
                    if abs(d) > 0.5 and lang:
                        grey_labels.append((x_of(d), lang, d))
                else:
                    is_open = categories.get((name, lang)) in OPEN_DEFECT_CATEGORIES
                    col = red if is_open else grey_dot
                    if lang:
                        (red_labels if is_open else grey_labels).append((x_of(d), lang, d))
                clusters[(round(x_of(d), 1), col)] = clusters.get((round(x_of(d), 1), col), 0) + 1
                if lang and (name, lang) in unexplained:
                    rings.append(x_of(d))
            for (cx, col), count in clusters.items():
                r = min(4.2 + 1.1 * math.sqrt(count - 1), 7.0)
                s.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" fill="{col}" '
                         f'fill-opacity="{".85" if count > 1 else ".6"}"/>')
                if count >= 3:
                    s.append(f'<text x="{cx:.1f}" y="{cy + 2.5:.1f}" font-size="7" font-weight="700" fill="#ffffff" '
                             f'text-anchor="middle" font-family="ui-monospace, Menlo, monospace">{count}</text>')
                elif count == 2:
                    s.append(f'<text x="{cx + r + 2:.1f}" y="{cy + 2.5:.1f}" font-size="6.5" font-weight="700" '
                             f'fill="{col}" font-family="ui-monospace, Menlo, monospace">2</text>')
            for rx in rings:
                s.append(f'<circle cx="{rx:.1f}" cy="{cy:.1f}" r="7" fill="none" stroke="{red}" stroke-width="1.6"/>')
            # How many languages actually sit in the band, printed in the band's own
            # bottom-right corner. The bar to the left already gives the SHARE; a
            # reader comparing two rows with the same percentage still has to know
            # whether that is 40 of 46 or 4 of 5 (n varies per row -- n/a cells and
            # population-less languages drop out), and the dots are too dense to
            # count by eye. Drawn AFTER the dots and carrying a white halo
            # (paint-order: stroke, then fill): the band is only `sh` tall and the dots
            # are centred in it, so anything near +25% sits under this label.
            n_green = sum(1 for d in devs if abs(d) <= GREEN_DEV)
            s.append(f'<text x="{x_of(GREEN_DEV) - 2.5:.1f}" y="{cy + sh / 2 - 1.5:.1f}" font-size="7.5" '
                     f'fill="{green}" text-anchor="end" font-family="ui-monospace, Menlo, monospace" '
                     f'paint-order="stroke" stroke="#ffffff" stroke-width="2.4" stroke-linejoin="round">'
                     f'{n_green}/{n}</text>')
            lo, hi = x_of(-1.1), x_of(1.1)
            for x, lang in _place_labels(_fit_labels(red_labels, strip_w), lo, hi):
                s.append(f'<text x="{x:.1f}" y="{cy - sh / 2 - 3}" font-size="8" fill="{red_lab}" text-anchor="middle">{lang}</text>')
            for x, lang in _place_labels(_fit_labels(grey_labels, strip_w), lo, hi):
                s.append(f'<text x="{x:.1f}" y="{cy + sh / 2 + 9}" font-size="8" fill="{grey_lab}" text-anchor="middle">{lang}</text>')
            y += row_h
    foot_y = height - 42
    s.append(f'<text x="{pad}" y="{foot_y}" font-size="10" fill="{muted}">* not gated: languages vary too much in how they '
             f"express this — program length, token vocabulary, inputs the corpus does not plant, commit age — for a "
             f"cross-language band to mean anything.</text>")
    s.append(f'<text x="{pad}" y="{foot_y + 13}" font-size="10" fill="{muted}">Shown for context, never scored. '
             f"Every dot outside the band on a gated row has a verdict in deviation_ledger.json; the cause behind each "
             f"colour is in docs/bias_data.json (cell_categories).</text>")
    s.append(f'<text x="{pad}" y="{foot_y + 28}" font-size="10" fill="{faint}">keyword-rosetta · tools/bias_report.py · '
             f"band ±{GREEN_DEV:.0%} of the cross-language median (exact agreement where the median is 0) · "
             f"cause categories: gitgalaxy docs/contract_roadmap.md</text>")
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

    # Checked BEFORE the first scan, not after all 46: the mismatch is a property
    # of the environment, so it is knowable in one second and costs a 30-minute
    # regen to discover afterwards (see engine_provenance's own docstring).
    engine_commit, scanner_root, engine_mismatch = engine_provenance()
    if engine_mismatch and "--allow-engine-mismatch" not in sys.argv:
        print(f"ABORT: {engine_mismatch}")
        return 1
    print(f"engine: {engine_commit or '<not a git checkout>'} at {scanner_root or vl.GALAXYSCOPE_BIN}")

    colmap = vl._signal_columns()
    all_totals, all_risks, all_struct, all_measures, zero_dep, all_units = {}, {}, {}, {}, {}, {}
    for lang in languages:
        print(f"scanning {lang}...")
        (
            all_totals[lang],
            all_risks[lang],
            all_struct[lang],
            all_measures[lang],
            zero_dep[lang],
            all_units[lang],
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

    # ...and the same question one step to the SIDE, for the structure counts
    # (gitgalaxy#2795). These read engine columns rather than registry rules, so
    # they were the last gated family with no n/a mechanism at all: markdown was
    # n/a on `func_start` and a -100% outlier on `functions_found` in the same
    # report. The governors' own review state comes off the registry the same way
    # the planted signals' does, so a structure count can never be excused by a
    # ledger entry its governing rule does not have.
    struct_na, struct_mismatches = unmeasurable_structure_cells(
        definitions, all_struct, population_less_languages(definitions)
    )
    governor_na_state = classify_na(
        ledger["entries"],
        {
            lang: sigs
            for lang, sigs in unmeasurable_signals(
                definitions, sorted(set(STRUCTURE_GOVERNORS.values())), include_exempt=True
            ).items()
            if lang in languages
        },
    )
    struct_na_by_metric = classify_structure_na(
        struct_na, governor_na_state, ledger["entries"]
    )
    na_by_metric.update(struct_na_by_metric)
    for lang, metrics in struct_na.items():
        for metric in metrics:
            all_struct[lang][metric] = None

    # gitgalaxy#2796: cells a validated ledger entry declares CROSS-PLANT-INCOMPARABLE
    # -- their value is dictated by a different plant, so they are not a comparable
    # reading of THIS signal. kotlin's classes_found IS its `globals` plant (Kotlin has
    # no module-level mutable state, so the two globals must be `object` singletons, and
    # an object is a class), not an independent class-detection measurement. Marked n/a
    # the same shape as the structure/census n/a passes above, so it leaves the row's
    # comparable denominator instead of scoring red against a stratum it does not belong
    # to.
    for signal, lang in ledger_incomparable_cells(ledger["entries"]):
        if lang in languages and signal in all_struct.get(lang, {}):
            all_struct[lang][signal] = None
            na_by_metric.setdefault(signal, {})[lang] = "ledgered"

    # The risk n/a pass runs AFTER the structure one (gitgalaxy#2908 Phase 4):
    # risk_documentation is population-based, so its n/a basis and review state
    # both come from `functions_found` -- the observed population and whether its
    # absence (or comparable zero) is itself accounted for.
    validated_live = [
        e for e in ledger["entries"]
        if e.get("status") == "validated" and e.get("still_reproduces") is not False
    ]
    populations = {lang: all_struct[lang].get("functions_found") for lang in languages}
    population_state = {
        lang: (
            struct_na_by_metric.get("functions_found", {}).get(lang) == "ledgered"
            or any(
                lang in e.get("languages_seen", [])
                and "functions_found" in (e.get("signal") or "").split("|")
                for e in validated_live
            )
        )
        for lang, pop in populations.items()
        if pop in (0, None)
    }
    risk_na, risk_mismatches = unmeasurable_risk_cells(
        deps, definitions, all_risks, populations=populations
    )
    risk_na_by_metric = classify_risk_na(risk_na, deps, dep_na_state, population_state)
    na_by_metric.update(risk_na_by_metric)
    for lang, metrics in risk_na.items():
        for metric in metrics:
            all_risks[lang][metric] = None
    if risk_mismatches:
        print(
            f"MISMATCH: {len(risk_mismatches)} derived cell(s) whose every "
            "registry (or population) input is absent still measured nonzero "
            "(left comparable):"
        )
        for lang, metric, value in risk_mismatches:
            print(f"  {lang}/{metric} = {value:.4f} (inputs: "
                  f"{deps[metric].get('units') or deps[metric]['governed']})")
    if struct_mismatches:
        print(
            f"MISMATCH: {len(struct_mismatches)} structure count(s) whose governing "
            "registry rule is absent still measured nonzero (left comparable):"
        )
        for lang, metric, value in struct_mismatches:
            print(f"  {lang}/{metric} = {value} (governed by: {STRUCTURE_GOVERNORS[metric]})")

    # ...and once more for the census (gitgalaxy#2866): `raw_state_unreferenced`
    # is a splice-computed measure, the last gated column with no n/a mechanism.
    # `governor_na_state` already carries `func_start`'s review status (it is a
    # structure governor), so markdown's rule-absence inheritance costs nothing
    # extra; the positional declarations are reviewed via their ledger entries.
    census_na, census_mismatches = unmeasurable_census_cells(definitions, all_measures)
    census_na_by_metric = classify_census_na(
        census_na, governor_na_state, ledger["entries"]
    )
    na_by_metric.update(census_na_by_metric)
    for lang, metrics in census_na.items():
        for metric in metrics:
            all_measures[lang][metric] = None
    if census_mismatches:
        print(
            f"MISMATCH: {len(census_mismatches)} census cell(s) the registry calls "
            "unanswerable still measured nonzero (left comparable -- if the language "
            "declares invocation_model, the declaration is not reaching the detector):"
        )
        for lang, metric, value in census_mismatches:
            print(f"  {lang}/{metric} = {value}")

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
    # gitgalaxy#2796: the declaration-requirement banding axis. `classes_found` is
    # banded on container PRESENCE within two strata (a file that IS a container ->
    # >=1; a file where a type is optional -> 0), not on a cross-language count median
    # that would paint cobol/jcl/dockerfile's correct morphology red. Distinct from the
    # strictness `strata` above -- a language's stratum differs by metric family.
    declaration_sensitive = ("classes_found",)
    decl_strata = declaration_strata(languages)
    declaration_presence = {m: decl_strata for m in declaration_sensitive}
    # Chart groups in pipeline order (gitgalaxy docs/contract_roadmap.md D4): the
    # structural extraction first, then the planted keywords, the dependency graph,
    # the derived descriptors, the scores the product reports; then the not-gated
    # groups. Titles are keyed by CHART_BLURBS. Every column still lands in the
    # cache (CHART_HIDDEN only hides a duplicate row from the picture).
    def series(c):
        if c in PLANTED:
            return [None if c in na_map.get(lang, ()) else all_totals[lang].get(c, 0) for lang in languages]
        if c in struct_names:
            return [all_struct[lang].get(c) for lang in languages]
        if c in measure_names:
            return [all_measures[lang].get(c) for lang in languages]
        if c in risk_names:
            return [all_risks[lang].get(c) for lang in languages]
        if c in unplanted_inputs:
            return [None if lang in dep_na_state.get(c, {}) else all_totals[lang].get(c, 0) for lang in languages]
        if c in UNIT_METRICS:
            return [all_units[lang].get(c) for lang in languages]
        return None

    def group(names):
        return {c: series(c) for c in names if series(c) is not None}

    placed = set(CHART_STRUCTURE) | set(CHART_GRAPH) | set(CHART_LENGTH) | set(CHART_VOCAB)
    groups = [
        ("structural extraction", group(CHART_STRUCTURE + ["pagerank"]), True),
        ("keyword extraction", group([c for c in PLANTED if c not in placed]), True),
        # Directly after the planted keywords, because it asks the same question with
        # the answer inverted: the corpus plants nothing these rules match, so the
        # honest reading is 0 in every language and any nonzero cell is a rule firing
        # on something nobody wrote. That is a comparable claim -- scored on exact
        # agreement against the zero median, the same basis class_start already uses --
        # not the "languages vary too much to band" context the group used to sit in.
        ("non-planted keyword extraction", group(unplanted_inputs), True),
        ("dependency graph creation", group(CHART_GRAPH), True),
        ("internal function metrics", group([c for c in measure_names if c not in placed]), True),
        ("calculated risk exposure — per file",
         group([c for c in risk_names if c not in TEMPORAL_METRICS and c not in measure_names]), True),
        ("program size & vocabulary", group(CHART_LENGTH + CHART_VOCAB), False),
        # gitgalaxy#2908: the per-unit attribute totals -- attribution edges for
        # the per-unit risk formulas, reported not gated (see UNIT_METRICS).
        ("per-unit attributes", group(list(UNIT_METRICS)), False),
        ("commit age", group([c for c in risk_names if c in TEMPORAL_METRICS]), False),
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
        # WHICH engine produced these numbers (keyword-rosetta ledger-hygiene work).
        # `engine_mode` says how the engine was built; this says which engine it was.
        # Until it existed the commit lived only in bias-history.yml's commit message,
        # so a locally regenerated cache recorded nothing and a stale-engine run was
        # indistinguishable from a current one in the artifact itself.
        "engine_commit": engine_commit,
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
        # gitgalaxy#2908: per-unit attribute totals -- reported, never gated.
        "unit_metrics": list(UNIT_METRICS),
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

    # E.1 (gitgalaxy#2669): which out-of-band cells are already accounted for.
    verdicts = explain_out_of_band(
        cache["metrics"], languages, ledger["entries"],
        {c: dict(zip(languages, [all_struct[lang].get(c) for lang in languages]))
         for c in struct_names},
        risk_inputs=deps, strata=strata, constant_sensitive=constant_sensitive, ungated=ungated,
        presence=declaration_presence,
    )
    unexplained = sorted(k for k, (st, _) in verdicts.items() if st == "unexplained")
    by_status = collections.Counter(st for st, _ in verdicts.values())
    # Phase 0 (gitgalaxy docs/contract_roadmap.md): what each red cell IS, and the
    # open-defect share the consistency badge cannot express. Cached so
    # issue_status.py and ad hoc readers roll up the same way.
    categories = categorize_out_of_band(verdicts, ledger["entries"])
    by_category = collections.Counter(categories.values())
    defect_share = open_defect_share(cache["metrics"], languages, categories, ungated=ungated)
    cache["cell_categories"] = {f"{m}/{l}": c for (m, l), c in sorted(categories.items())}
    cache["open_defect_share"] = {m: list(v) for m, v in sorted(defect_share.items())}
    (REPO_ROOT / "docs" / "bias_data.json").write_text(
        json.dumps(cache, indent=1) + "\n"
    )

    refs = reference_medians(cache["metrics"], languages, strata, constant_sensitive)
    shares, skipped, inert, agreement = write_variance_chart(
        groups, len(languages), na_by_metric,
        medians={m: [refs[m].get(lang) for lang in languages] for m in constant_sensitive if m in refs},
        presence={m: [decl_strata.get(lang) for lang in languages] for m in declaration_sensitive},
        languages=languages, unexplained=set(unexplained), categories=categories,
        headline=(sum(o for o, _ in defect_share.values()), sum(n for _, n in defect_share.values())),
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
    n_na_struct = sum(len(v) for v in struct_na_by_metric.values())
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
    if n_na_struct:
        lines += [
            f"**Structure counts:** and {n_na_struct} cells are n/a in the STRUCTURE "
            "COUNTS group (gitgalaxy#2795). These columns read the engine's own "
            "`function_count`/`class_count`/`import_count` rather than a registry rule, "
            "so the rule-absence inference above never reached them and a language could "
            "be n/a on `func_start` and a −100% outlier on `functions_found` in the same "
            "report — the group's consistency scores were measured over a larger "
            "population than the rules they summarise. Each count now names the rule it "
            "is a tally of and inherits that rule's review status. `dependency_links` is "
            "governed by `_dependency_capture`, **not** by `import`: since gitgalaxy#2638 "
            "the two diverge, and markdown records 3 real edges with no `import` rule — a "
            "comparable cell that stays scored. A governing rule can also be present and "
            "govern nothing (gitgalaxy#2792): sqlite is sliced by Mode E, which never "
            "consults `func_start` for a name — it labels every bucket after the igniter "
            "keyword — so the language has no function population at all. That cell is "
            "reviewed by an entry naming the count itself, not inherited from a rule "
            "whose presence says nothing about what its matches mean.",
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

    n_open = sum(by_category.get(c, 0) for c in OPEN_DEFECT_CATEGORIES)
    n_gated_cells = sum(n for _, n in defect_share.values())
    n_open_cells = sum(o for o, _ in defect_share.values())
    worst_open = sorted(
        ((o / n, m, o, n) for m, (o, n) in defect_share.items() if o),
        reverse=True,
    )[:5]
    na_cells = {(sig, lang) for sig, per_lang in na_by_metric.items() for lang in per_lang}
    na_cells |= {(sig, lang) for sig, per_lang in dep_na_state.items() for lang in per_lang}
    decayed = decayed_entries(ledger["entries"], oob_all, na_cells)
    lines += ["## What the red cells are", "",
              "A verdict says a cell is accounted for; it does not say what the cell *is*, and the "
              "consistency badges above paint a validated \"this language cannot express that\" the "
              "same red as an open engine defect. Folding each ledgered cell's dispositions into one "
              "cause (most severe first where an entry list mixes them) gives the split that the "
              "badge cannot: how much of the red is a finding somebody still owes. The **open-defect "
              "share** counts `unexplained`, `extraction` and `correlation` cells over every comparable "
              "cell of the gated metrics; scoring choices are ledgered design, inherency and echo are "
              "not findings at all. Cause categories, the roadmap they come from and what each one's "
              "right response is: gitgalaxy `docs/contract_roadmap.md`.", "",
              f"**Open-defect share: {n_open_cells} of {n_gated_cells} comparable cells "
              f"({n_open_cells / n_gated_cells:.1%})** across {len(defect_share)} gated metrics; "
              f"{n_open} of the {len(categories)} out-of-band cells are open defects.", "",
              "| cause | cells | what it is |",
              "|---|---|---|"]
    for cat in CELL_CATEGORIES:
        n = by_category.get(cat, 0)
        label = f"**{cat}**" if cat in OPEN_DEFECT_CATEGORIES else cat
        lines.append(f"| {label} | {n} | {CATEGORY_MEANING[cat]} |")
    lines += [""]
    if worst_open:
        lines += ["Metrics carrying the most open defect, by share of their comparable cells:", ""]
        lines += [f"- `{m}` — {o} of {n} ({share:.0%})" for share, m, o, n in worst_open]
        lines += [""]
    if decayed:
        lines += ["Ledger entries that currently explain **no** out-of-band cell (validated, still "
                  "reproducing, but their signal x language cross-product lands entirely in band — "
                  "keyword-rosetta#75's decay check): "
                  + ", ".join(f"`{eid}`" for eid, _ in decayed) + ". Narrow or retire them.", ""]

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
    lines += ["", "## Non-planted keyword extraction", "",
              "The risk formulas read registry signals the SPEC does not plant: "
              + ", ".join(f"`{s}`" for s in unplanted_inputs)
              + ". Nothing in the corpus was written for these rules to match, so the honest reading "
              "is **0 in every language** and any nonzero cell is a rule matching a token the program "
              "carries for some other reason. That is a comparable claim, so since 2026-09-07 the "
              "group is **scored** (on exact agreement against the zero median, the basis every "
              "zero-median metric uses) rather than charted as context next to program length. Each "
              "nonzero cell needs a verdict like any other: the sweep that turned the scoring on "
              "audited all 37 by running each language's own rule over its code and comment streams, "
              "and they resolve to the language's mandatory form (a JavaScript declaration cannot "
              "avoid `const`), a token planted for another signal and counted again here (`eval` is "
              "the high_risk_execution plant), or a signal the SPEC does plant in a language or two "
              "without giving it a manifest column (`[SPEC-2732]`) -- all ledgered as "
              "`non-planted-rules-match-idiom-and-planted-tokens`, with the one real defect it found "
              "split out as `makefile-dead-code-reads-prose-labels` (gitgalaxy#2851). "
              f"{n_unplanted_oob} cells are out of band now:", ""]
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
              "such. A per-unit ratio (gitgalaxy#2908: `risk_documentation`) is a pure function of "
              "its held inputs, so those are held EXACTLY rather than banded -- languages sharing "
              "the modal unit profile must score identically, and a constant score there is printed "
              "as **invariant**: the formula cannot read length, by measurement.", ""]
    if leaks:
        lines += ["| metric | languages | stratum | rho | verdict | inputs held in band | where length enters |",
                  "|---|---|---|---|---|---|---|"]
        for r in leaks:
            held = ", ".join(f"`{h}`" for h in r["held"]) if r["held"] else "*(none known)*"
            if r["verdict"] == "invariant":
                held += " *(held exactly)*"
            where = r["where"] or "**not located yet** — the more interesting finding"
            label = {"leak": "**leak**", "weak": "weak", "invariant": "invariant — the proof"}[r["verdict"]]
            lines.append(f"| `{r['metric']}` | {r['n']} | {r.get('stratum') or '—'} | {r['rho']:+.2f} | "
                         f"{label} | {held} | {where} |")
        lines += [""]
    else:
        lines += ["No derived metric correlates with `coding_loc` at "
                  f"|rho| ≥ {LEAK_WEAK_RHO} over ≥ {LEAK_MIN_LANGUAGES} languages.", ""]

    lines += ["## Cross-language variance chart", "",
              "![variance chart](bias_variance_chart.svg)", "",
              "Colour encodes **cause**, not magnitude: a dot inside ±"
              f"{GREEN_DEV:.0%} of the cross-language median is green; outside it, **red** when the cell is an "
              "open engine defect (`unexplained`, `extraction`, `correlation` in the cause table above) and "
              "**grey** when it is a documented variation (a scoring choice, language inherency, or an echo of "
              "another row). Each gated row's bar splits its languages the same way — in band · documented · "
              "open defect — with the **accounted share** printed inside (in band + documented: everything "
              "that is not an open defect — a documented variation is measured and explained, so it does not "
              "subtract from the badge) and the open-defect count after it; the in-band count keeps its n/n "
              "label in the band's corner, and languages at the same position collapse into one dot carrying "
              "their count, so exact agreement is visible instead of overplotted. Rows run "
              "best → worst (least open defect first). The header's first number is the open-defect share, the "
              f"number to drive to 0. Average share in band across {len(shares)} gated metrics: **{avg_share:.0%}**; "
              f"{n_strong} metrics hold ≥80% of languages in band. Weakest by in-band share: "
              + ", ".join(f"{k} {v:.0%}" for k, v in weakest) + ". "
              + (f"*exact* marks a metric scored on **exact agreement** with a zero median "
                 f"(relative deviation is undefined there, so the score is the share of "
                 f"languages sitting exactly on it): {', '.join(agreement)}. "
                 if agreement else "")
              + (f"Skipped (no values recorded): {', '.join(skipped)}. " if skipped else "")
              + (f"**Inert** (every language records exactly 0, so the column asks no "
                 f"cross-language question — scored as no result rather than as unanimous "
                 f"agreement): {', '.join(inert)}. " if inert else "")
              + "Not-gated groups (program size & vocabulary, commit age) are drawn "
              "for context and never scored: languages vary too much in how they express these for a "
              "cross-language band to mean anything. Non-planted keyword extraction is NOT one of "
              "them -- nothing was written for those rules to match, so 0 everywhere is a comparable "
              "expectation and the group is scored against it. "
              + ", ".join(f"`{k}` is not drawn ({v})" for k, v in CHART_HIDDEN.items()) + ".",
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
            if name in struct_na.get(lang, ()):
                vals.append("n/a" if struct_na_by_metric[name][lang] == "ledgered" else "n/a†")
                continue
            v = all_struct[lang].get(name)
            vals.append("—" if v is None else (f"{v:.4f}" if isinstance(v, float) else str(v)))
        lines.append(f"| {name} | " + " | ".join(vals) + " |")
    if n_na_struct:
        lines += ["", "n/a = the registry rule this count is a tally OF is absent for the "
                  "language (`functions_found` ← `func_start`, `classes_found` ← "
                  "`class_start`, `dependency_links` ← `_dependency_capture`) — or, for "
                  "`functions_found`, present but able to name only slicer buckets "
                  "(gitgalaxy#2792) — and the scan confirms the count is 0; or the cell is "
                  "CROSS-PLANT-INCOMPARABLE (gitgalaxy#2796): its value is dictated by a "
                  "different plant, so it is not an independent reading of this signal "
                  "(kotlin `classes_found` IS its `globals` plant — objects are Kotlin's "
                  "only module-level state). Either way: incomparable, excluded from bands "
                  "and medians; † = not yet backed by a validated ledger entry."]

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
            if col in census_na.get(lang, ()):
                vals.append("n/a" if census_na_by_metric[col][lang] == "ledgered" else "n/a†")
                continue
            v = all_measures[lang].get(col)
            vals.append("—" if v is None else f"{v:.4g}")
        lines.append(f"| {col} | " + " | ".join(vals) + " |")
    if any(census_na.values()):
        lines += ["", "n/a = the registry says this census is unanswerable for the language "
                  "-- `invocation_model` is not `by_name` (the extracted units execute in "
                  "written order, gitgalaxy#2806/#2866) or no `func_start` rule exists to "
                  "produce a population (gitgalaxy#2795's inference) -- and the scan "
                  "confirms 0 (incomparable, excluded from bands and medians); † = the "
                  "declaration is not yet backed by a validated ledger entry."]

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
        f"{by_status.get('derived', 0)} derived; {n_context_oob} context cells not counted, "
        f"{n_unplanted_oob} non-planted cells now scored)"
    )
    print(
        f"cause split: " + ", ".join(f"{c} {by_category.get(c, 0)}" for c in CELL_CATEGORIES)
        + f" -- open-defect share {n_open_cells}/{n_gated_cells}"
        + (f"; decayed ledger entries: {len(decayed)}" if decayed else "")
    )
    n_leak = sum(1 for r in leaks if r["verdict"] == "leak")
    n_inv = sum(1 for r in leaks if r["verdict"] == "invariant")
    print(
        f"length leaks: {n_leak} leak / {len(leaks) - n_leak - n_inv} weak / {n_inv} invariant -- "
        + (", ".join(f"{r['metric']} {r['rho']:+.2f}" for r in leaks if r["verdict"] == "leak")
           or "none")
    )
    # keyword-rosetta#75: surface orphan ledger tokens on every regen (the cache
    # this reads was just written above). Report-only here; the baseline gate lives
    # in tools/ledger_orphan_check.py --ci. A rising count means collective entries
    # are decaying -- a token stopped excusing any out-of-band cell and nobody
    # noticed. This is the per-TOKEN refinement of the `decayed ledger entries`
    # count printed just above, which is whole-entry and so blind to an entry that
    # decays one token at a time (batch5's shape); the two read the same bands and
    # cannot disagree. Partial-decay entries are the scope-down candidates
    # (docs/GATING.md, ledger _doc rule).
    import ledger_orphan_check

    orphans, _details, by_entry = ledger_orphan_check.analyse()
    n_partial = sum(1 for b in by_entry.values() if b["orphan"] and b["live"])
    print(
        f"orphan ledger tokens: {len(orphans)} across "
        f"{sum(1 for b in by_entry.values() if b['orphan'])} entries "
        f"({n_partial} partially decayed -- scope-down candidates; "
        "tools/ledger_orphan_check.py)"
    )
    if gate and unexplained:
        print("--gate: unexplained out-of-band cells remain; epic close criterion not met")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
