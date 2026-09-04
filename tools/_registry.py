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
    """{risk_metric: {"calc","governed","engine"}} derived from the live engine.

    `governed` are inputs the LANGUAGE_DEFINITIONS registry controls (so a None
    rule pins them to zero for that language); `engine` are inputs synthesized
    downstream of the registry (orphaned_logic, duplicate_logic, the sec_*
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

    per_calc, owner = {}, {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("_calc"):
            v = _SignalUses()
            v.visit(node)
            per_calc[node.name] = v.keys
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
        out[f"risk_{k.value}"] = {
            "calc": fn,
            "governed": sorted(x for x in keys if x in governed_signals),
            "engine": sorted(x for x in keys if x not in governed_signals),
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
# Scoring tiers (Fc / Irc constants, gitgalaxy#2653)
# ---------------------------------------------------------------------------
# signal_processor._get_tier assigns every language one of three scoring tiers by
# literal set membership; tier3 (the default) carries an implicit-risk term
# (irc / mass_loc) and a lower documentation credit than tier1. The rosetta
# corpus reads that as cross-language bias unless it is held equal, so the
# length-leak check (gitgalaxy#2669 F.1) needs the sets and F.3 will normalise
# by them. Read off the live source, never hand-copied.
def scoring_tiers(languages):
    """{language: "tier1"|"tier2"|"tier3"} as signal_processor._get_tier assigns them."""
    src = pathlib.Path(GITGALAXY_PATH, SIGNAL_PROCESSOR).read_text()
    sets = {}
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.FunctionDef) and node.name == "_get_tier":
            for stmt in node.body:
                if (
                    isinstance(stmt, ast.Assign)
                    and len(stmt.targets) == 1
                    and isinstance(stmt.targets[0], ast.Name)
                    and isinstance(stmt.value, ast.Set)
                ):
                    sets[stmt.targets[0].id] = {
                        e.value for e in stmt.value.elts
                        if isinstance(e, ast.Constant) and isinstance(e.value, str)
                    }
            break
    if "explicit" not in sets or "structured" not in sets:
        raise RuntimeError(
            "signal_processor._get_tier no longer defines the `explicit`/`structured` "
            "sets this loader reads -- update scoring_tiers() to match the engine"
        )
    return {
        lang: "tier1" if lang in sets["explicit"]
        else "tier2" if lang in sets["structured"]
        else "tier3"
        for lang in languages
    }
