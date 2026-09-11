"""Shared access to the live GitGalaxy language registry.

Every tool in this repo derives from the LANGUAGE_DEFINITIONS in a real GitGalaxy
checkout — nothing hand-copies keyword lists, so the corpus can't drift stale the
way a hand-written matrix would. Point GITGALAXY_PATH at the checkout; the default
assumes the sibling layout used on the dev box.
"""

import ast
import os
import pathlib
import sys

GITGALAXY_PATH = os.environ.get(
    "GITGALAXY_PATH", "/srv/storage_16tb/projects/gitgalaxy/v6"
)


def apply_engine(worktree):
    """Point GITGALAXY_PATH, PYTHONPATH and (best-effort) GALAXYSCOPE_BIN at a
    gitgalaxy worktree -- the recipe every rule-contract-audit session hand-runs
    (that skill's L20-32) done once, in code, instead of copied into each
    session's notes (keyword-rosetta#113).

    PYTHONPATH is prepended, not just GITGALAXY_PATH set, because a subprocess
    `galaxyscope` binary (verify_language.py's scan(), any GALAXYSCOPE_BIN) is a
    separate interpreter with its own editable install; only PYTHONPATH shadows
    that for a child process. GALAXYSCOPE_BIN is set only if unset AND the
    worktree carries its own venv -- worktrees rarely build one, and the normal
    shape is a fixed venv binary (e.g. the main checkout's) whose import the
    PYTHONPATH shadow redirects, matching the audit skill's
    `GALAXYSCOPE_BIN=<main .venv>/bin/galaxyscope` + worktree PYTHONPATH recipe.

    Must run before the caller's own `from _registry import GITGALAXY_PATH` (or
    any `os.environ.get("GALAXYSCOPE_BIN", ...)`) executes -- those bind to
    whatever the env vars say at that line, not to a later mutation.
    """
    global GITGALAXY_PATH
    path = pathlib.Path(worktree).expanduser().resolve()
    if not path.is_dir():
        raise SystemExit(f"--engine {worktree}: no such directory")
    worktree = str(path)
    os.environ["GITGALAXY_PATH"] = worktree
    os.environ["PYTHONPATH"] = worktree + os.pathsep + os.environ.get("PYTHONPATH", "")
    GITGALAXY_PATH = worktree
    venv_bin = path / ".venv" / "bin" / "galaxyscope"
    if venv_bin.exists():
        os.environ.setdefault("GALAXYSCOPE_BIN", str(venv_bin))
    return worktree


def consume_engine_arg(argv):
    """Pull a `--engine WORKTREE` pair out of argv (if present) and apply it.

    Returns the remaining argv. Call this before importing anything that reads
    GITGALAXY_PATH/GALAXYSCOPE_BIN at import time (see apply_engine's docstring).
    """
    out = list(argv)
    if "--engine" in out:
        i = out.index("--engine")
        if i + 1 >= len(out):
            raise SystemExit("--engine needs a path")
        apply_engine(out[i + 1])
        del out[i : i + 2]
    return out

# The 20-key core set every Tier-1 language defines (measured 2026-08-31; re-derived
# live by tier_report() below rather than trusted, so a registry change surfaces
# as a tier change, not a silent lie).
CORE_SIGNALS = [
    "func_start",
    "branch",
    "import",
    "args",
    "api",
    "doc",
    "planned_debt",
    "fragile_debt",
    "safety",
    "safety_bypasses",
    "io",
    "globals",
    "encapsulation",
    "test",
    "high_risk_execution",
    "dead_code",
    "ownership",
    "telemetry",
    "state_mutation",
    "cleanup",
]


def load_definitions():
    if GITGALAXY_PATH not in sys.path:
        sys.path.insert(0, GITGALAXY_PATH)
    from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

    return LANGUAGE_DEFINITIONS


def active_rules(definitions):
    """{language: rules-dict} for languages with at least one non-None rule."""
    out = {}
    for lang, d in definitions.items():
        rules = d.get("rules") or {}
        if any(v is not None for v in rules.values()):
            out[lang] = rules
    return out


# Signals that can appear in scan output even when the language defines NO rule for
# them, so rule-absence does NOT make the cell unmeasurable. Proven empirically:
# jcl's api rule is None yet a/b/c record api=3 -- galaxyscope's Contextual Baseline
# Fix synthesizes api from orphan conversion (ledger: api-contextual-baseline-fix).
NA_EXEMPT = {"api"}


def unmeasurable_signals(definitions, signals, include_exempt=False):
    """{language: sorted [signal]} where the rule is None/absent in the registry.

    For these cells the engine can never report a nonzero -- a measured 0 there is
    "the concept is not expressible as measured", NOT "the engine found nothing".
    The bias tooling renders them n/a (incomparable) instead of a -100% deviation.
    This is deliberately a *mechanical* criterion; whether the absence is CORRECT
    is a separate, human question (jcl's safety rule was None until gitgalaxy#2610
    proved JCL has real error-handling morphology) -- the rosetta-language-sweep
    skill's bucket-2 check plus a validated ledger entry is what upgrades an
    absence from "unreviewed" to "ledgered". See docs/GATING.md.

    `include_exempt` keeps the NA_EXEMPT signals (api) in the result. The exemption
    exists because rule-absence alone does not make `api` unmeasurable -- orphan
    conversion synthesizes it -- so it must stay out of the planted-signal n/a
    table. But `api` is a governed input to two risk formulas, so when a derived
    cell's n/a rests on it the governance still needs a reviewable row to point at;
    without one the cell is marked unreviewed and nothing in the baseline says why.
    """
    out = {}
    for lang, rules in active_rules(definitions).items():
        missing = sorted(
            s
            for s in signals
            if (include_exempt or s not in NA_EXEMPT) and rules.get(s) is None
        )
        if missing:
            out[lang] = missing
    return out


def population_less_languages(definitions):
    """{language} whose every recorded function name is a slicer label.

    gitgalaxy#2792: a language can have a `func_start` rule and still never
    record an author-written identifier. sqlite is sliced by `mode_e`, which
    never consults `func_start` for a name at all -- it cleaves on the `;` and
    labels each bucket after the igniter keyword -- so once the engine stopped
    counting those buckets, sqlite's honest `functions_found` is 0. There is no
    population to compare, and scoring the 0 would be a bigger red deviation
    than the 31 it replaced.

    Read off the engine's own predicate rather than hand-listed here, the same
    doctrine `risk_dependencies` follows: a slicing-mode change then surfaces as
    an import/derivation failure instead of leaving a stale set quietly excusing
    comparable cells. Includes the plain rule-absence case (markdown), so it is a
    superset of the `func_start is None` languages -- and deliberately EXCLUDES
    the closed-literal `func_start` languages (dockerfile, css, html, yaml),
    whose buckets the engine still counts because they are grammar-recognised
    constructs it correctly locates (gitgalaxy#2792 declined that half with
    measurement: css scores 25/25 function precision against tree-sitter on
    exactly those names). Their cells stay scored and stay ledgered.
    """
    if GITGALAXY_PATH not in sys.path:
        sys.path.insert(0, GITGALAXY_PATH)
    from gitgalaxy.core.detector import synthesizes_all_function_names

    return {
        lang
        for lang, d in definitions.items()
        if synthesizes_all_function_names(lang, d.get("rules") or {})
    }


def tier_report(definitions):
    """(tier1_langs, tier2_missing) — tier2_missing maps language -> missing core keys."""
    tier1, tier2 = [], {}
    for lang, rules in sorted(active_rules(definitions).items()):
        missing = [k for k in CORE_SIGNALS if rules.get(k) is None]
        if missing:
            tier2[lang] = missing
        else:
            tier1.append(lang)
    return tier1, tier2


# ---------------------------------------------------------------------------
# Derived-metric dependencies (risk_* columns)
# ---------------------------------------------------------------------------
# Same doctrine as load_definitions(): derive from the live engine source rather
# than hand-copying a table, so an engine refactor surfaces as a derivation
# failure instead of a silently stale map. We AST-parse the risk vector
# assembly in metrics/signal_processor.py and record, per risk metric, which
# signals its formula actually consumes.
SIGNAL_PROCESSOR = "gitgalaxy/metrics/signal_processor.py"
EXPOSURE_VECTOR = "exposure_vector"


class _SignalUses(ast.NodeVisitor):
    """Collects `raw_signals.get("x")` / `raw_signals["x"]` keys in one function."""

    def __init__(self):
        self.keys = set()

    @staticmethod
    def _is_signals(node):
        return isinstance(node, ast.Name) and "signal" in node.id

    def visit_Call(self, node):
        f = node.func
        if (
            isinstance(f, ast.Attribute)
            and f.attr == "get"
            and self._is_signals(f.value)
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
        ):
            self.keys.add(node.args[0].value)
        self.generic_visit(node)

    def visit_Subscript(self, node):
        if (
            self._is_signals(node.value)
            and isinstance(node.slice, ast.Constant)
            and isinstance(node.slice.value, str)
        ):
            self.keys.add(node.slice.value)
        self.generic_visit(node)


class _UnitAttrUses(ast.NodeVisitor):
    """Collects per-UNIT inputs in one function (gitgalaxy#2908 Phase 3).

    `_calc_documentation` stopped reading `raw_signals` entirely: it iterates the
    extracted units and reads `func.get("is_public")`, `func.get("is_documented")`
    and `func.get("hit_vector", {}).get("reflection_metaprogramming", 0)`. Those
    are real derivation edges -- the corpus records them as the `units_public` /
    `units_documented` function_data aggregates and the per-unit hit columns --
    and losing them would repeat the #2719 `_dynamism` lesson this module's own
    header tells: a formula input the AST walk cannot see silently drops out of
    the attribution map.

    `attrs` collects the unit attribute keys ({"is_public", "is_documented"});
    `hit_keys` collects signal names read out of a unit's own `hit_vector`.
    """

    UNIT_ATTRS = {"is_public", "is_documented"}

    def __init__(self):
        self.attrs = set()
        self.hit_keys = set()

    def visit_Call(self, node):
        f = node.func
        if (
            isinstance(f, ast.Attribute)
            and f.attr == "get"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
        ):
            key = node.args[0].value
            if key in self.UNIT_ATTRS:
                self.attrs.add(key)
            # `<unit>.get("hit_vector", {}).get("<signal>")`: the outer .get's
            # target is itself a .get("hit_vector") call.
            inner = f.value
            if (
                isinstance(inner, ast.Call)
                and isinstance(inner.func, ast.Attribute)
                and inner.func.attr == "get"
                and inner.args
                and isinstance(inner.args[0], ast.Constant)
                and inner.args[0].value == "hit_vector"
            ):
                self.hit_keys.add(key)
        self.generic_visit(node)


# The corpus column each per-unit attribute aggregates into (function_data SUMs,
# the same columns verify_language.py gates per file since gitgalaxy#2908 Phase 2).
UNIT_ATTR_COLUMNS = {"is_public": "units_public", "is_documented": "units_documented"}


def _calc_name(node):
    """`self._calc_x(...)` / `_calc_x(...)` -> "_calc_x", else None."""
    if not isinstance(node, ast.Call):
        return None
    f = node.func
    if isinstance(f, ast.Attribute) and f.attr.startswith("_calc"):
        return f.attr
    if isinstance(f, ast.Name) and f.id.startswith("_calc"):
        return f.id
    return None


def risk_dependencies(governed_signals):
    """{risk_metric: {"calc","governed","engine","reads_constant"}} from the live engine.

    `reads_constant` is True when the formula reads a language-level constant
    (irc/ot/fid), so the bias report bands that metric within its strictness
    stratum (gitgalaxy#2669 F.3, re-pointed at #2718's table).

    `governed` are inputs the LANGUAGE_DEFINITIONS registry controls (so a None
    rule pins them to zero for that language); `engine` are inputs synthesized
    downstream of the registry (unreferenced_by_name, duplicate_logic, the sec_*
    family) which can be nonzero no matter what the registry says, and which
    therefore block the metric from ever being called unmeasurable.

    Raises RuntimeError if the engine's risk assembly no longer looks the way
    this parser expects -- a loud failure is the point: a stale dependency map
    would quietly mark comparable cells n/a.
    """
    path = pathlib.Path(GITGALAXY_PATH) / SIGNAL_PROCESSOR
    if not path.exists():
        raise RuntimeError(f"engine source not found: {path} (set GITGALAXY_PATH)")
    tree = ast.parse(path.read_text())

    # gitgalaxy#2669 F.4: scan EVERY method, not only the _calc_ ones, so a
    # formula that reads its signals through a helper is still attributed.
    # gitgalaxy#2719 introduced exactly that: `_calc_documentation` and
    # `_calc_cog_load` no longer subscript raw_signals["reflection_metaprogramming"]
    # themselves, they call `self._dynamism(raw_signals)` -- and this map silently
    # lost the input, which had been carrying F.3's yacc cognitive-load verdict.
    per_method, calls_out, per_method_units = {}, {}, {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            v = _SignalUses()
            v.visit(node)
            per_method[node.name] = v.keys
            u = _UnitAttrUses()
            u.visit(node)
            per_method_units[node.name] = u
            calls_out[node.name] = {
                n.func.attr for n in ast.walk(node)
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
            }

    def _signals_of(name, seen=None):
        """A method's signal keys plus those of the methods it calls (transitive)."""
        seen = seen or set()
        if name in seen or name not in per_method:
            return set()
        seen.add(name)
        keys = set(per_method[name])
        for callee in calls_out.get(name, ()):
            keys |= _signals_of(callee, seen)
        return keys

    per_calc, per_calc_units, owner, reads_tier = {}, {}, {}, {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("_calc"):
            per_calc[node.name] = _signals_of(node.name)
            u = per_method_units.get(node.name)
            per_calc_units[node.name] = u.attrs if u else set()
            # A unit's own hit_vector reads are registry-governed signals too:
            # no reflection_metaprogramming rule, no per-unit reflection hits.
            per_calc[node.name] = per_calc[node.name] | (u.hit_keys if u else set())
            # F.3: does the formula read a language-level constant (irc / ot, and
            # the per-signal fidelity map that replaced the scalar fc in #2718)? A
            # bare-name reference anywhere in the body counts; the constants are
            # only ever passed in under these names.
            names = {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}
            reads_tier[node.name] = bool(names & {"irc", "fc", "ot", "fid"})
        # `cog_score, cog_raw = self._calc_cog_load(...)` / `x = self._calc_y(...)`
        if isinstance(node, ast.Assign):
            fn = _calc_name(node.value)
            if fn:
                for tgt in node.targets:
                    names = tgt.elts if isinstance(tgt, ast.Tuple) else [tgt]
                    for n in names:
                        if isinstance(n, ast.Name):
                            owner[n.id] = fn

    vector = None
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == EXPOSURE_VECTOR for t in node.targets)
            and isinstance(node.value, ast.Dict)
        ):
            vector = node.value
            break
    if vector is None:
        raise RuntimeError(
            f"could not find the `{EXPOSURE_VECTOR} = {{...}}` risk assembly in {path}"
        )

    out = {}
    for k, v in zip(vector.keys, vector.values):
        if not (isinstance(k, ast.Constant) and isinstance(k.value, str)):
            continue
        fn = _calc_name(v) or (owner.get(v.id) if isinstance(v, ast.Name) else None)
        # A key with no _calc_ behind it (churn's literal 0.0, stability's
        # separately-computed score) has no derivable signal dependency: it is
        # recorded with an empty map and can never qualify as unmeasurable.
        keys = per_calc.get(fn, set()) if fn else set()
        unit_attrs = per_calc_units.get(fn, set()) if fn else set()
        out[f"risk_{k.value}"] = {
            "calc": fn,
            "governed": sorted(x for x in keys if x in governed_signals),
            "engine": sorted(x for x in keys if x not in governed_signals),
            "reads_constant": bool(fn and reads_tier.get(fn, False)),
            # gitgalaxy#2908 Phase 3: the per-unit derivation edges, as corpus
            # column names. Non-empty marks the formula POPULATION-BASED: it is
            # a ratio over the extracted units, so its n/a basis is an empty
            # unit population (functions_found 0 or n/a), never rule absence.
            # The population count itself is an edge (every unit contributes
            # weight), and when the formula reads BOTH is_public and
            # is_documented their interaction is one too: a documented public
            # unit removes public_weight from the exposed sum where a documented
            # private unit removes 1, so the overlap total
            # (`units_public_documented`) is part of the ratio's sufficient
            # statistic, not a convenience column.
            "units": (
                (["functions_found"] if unit_attrs else [])
                + sorted(UNIT_ATTR_COLUMNS[a] for a in unit_attrs)
                + (["units_public_documented"]
                   if {"is_public", "is_documented"} <= unit_attrs else [])
            ),
        }
    if not out:
        raise RuntimeError(f"risk assembly in {path} yielded no metrics")
    return out


def registry_signals(definitions):
    """Every signal key the registry controls, across all languages."""
    keys = set()
    for rules in active_rules(definitions).values():
        keys |= set(rules)
    return keys


# ---------------------------------------------------------------------------
# Scoring strata (the language-level risk constants, gitgalaxy#2716)
# ---------------------------------------------------------------------------
# Until gitgalaxy#2718 the engine assigned every language one of three scoring
# tiers by literal set membership, and this loader AST-read the two sets out of
# `signal_processor._get_tier`. That function is gone: the language-level term is
# now `analysis_lens.LANGUAGE_STRICTNESS`, four yes/no columns per language, and
# `strictness_constants()` turns the count of False columns into (Irc, Ot) --
# Irc = gaps, Ot = 1 + 0.1 x gaps. A language's stratum is therefore its gap
# count, and languages with the same count carry the identical constant.
#
# The corpus still has to hold that constant equal before banding a risk metric
# (gitgalaxy#2669 F.3's decision, one layer down), which is what this feeds. It
# is imported live rather than AST-read: the engine exports the function, so
# there is nothing to re-derive and family inheritance (embedded_python -> python)
# comes for free.
#
# NOT held equal: the per-language x per-signal fidelity coefficients
# (`gitgalaxy/standards/fidelity_table.py`, also #2718). Those are generated FROM
# this corpus, so holding them equal here would be circular; a defence-credit
# deviation that survives banding may still be a fidelity cell, and the report
# says so rather than pretending otherwise.
def scoring_strata(languages):
    """{language: "irc0".."irc4"} -- languages sharing a strictness gap count."""
    if GITGALAXY_PATH not in sys.path:
        sys.path.insert(0, GITGALAXY_PATH)
    try:
        from gitgalaxy.standards.analysis_lens import (
            LANGUAGE_STRICTNESS,
            resolve_language_family,
            strictness_constants,
        )
    except ImportError as exc:  # pragma: no cover - loud on an engine rename
        raise RuntimeError(
            "analysis_lens.strictness_constants is gone -- the engine's language-level "
            "risk term moved again; update scoring_strata() to match it"
        ) from exc

    # A `None` row (data / markup / config) and a four-True row BOTH yield Irc 0,
    # but they are not the same population and must not share a reference median:
    # one is haskell/java/rust/swift, the other is css/html/markdown/yaml, whose
    # risk scores sit near zero for want of any code to score. Lumping them made
    # swift read as an outlier against a median that was really markup's.
    out = {}
    for lang in languages:
        row = LANGUAGE_STRICTNESS.get(resolve_language_family(lang))
        out[lang] = "unprofiled" if row is None else f"irc{strictness_constants(lang)[0]}"
    return out


# gitgalaxy#2796: languages whose compilation unit IS a named container -- the file
# cannot exist without a container declaration, so a nonzero class/container count is
# morphology, not an extraction defect. cobol PROGRAM-ID, jcl JOB card, dockerfile
# FROM. Deliberately a small CURATED set, not derived from the container-construct
# ledger entries' `languages_seen` (which also list plant artifacts -- kotlin's
# object-as-globals -- and out-of-scope selector cases). The "file cannot exist
# without it" test is what separates these three from a language that merely CAN
# declare a type: a `.kt`/`.py`/`.rb` file is valid with no type at all.
CONTAINER_REQUIRED_LANGUAGES = frozenset({"cobol", "jcl", "dockerfile"})


def declaration_strata(languages):
    """{language: "container-required" | "declaration-optional"} -- gitgalaxy#2796.

    The banding axis for the structure-count `classes_found` row: a language whose
    file IS a container is banded on container PRESENCE (>=1), a language where a
    type declaration is optional on ABSENCE (==0). Distinct from scoring_strata's
    strictness axis -- a language's stratum differs by metric family.
    """
    return {
        lang: ("container-required" if lang in CONTAINER_REQUIRED_LANGUAGES
               else "declaration-optional")
        for lang in languages
    }
