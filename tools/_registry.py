"""Shared access to the live GitGalaxy language registry.

Every tool in this repo derives from the LANGUAGE_DEFINITIONS in a real GitGalaxy
checkout — nothing hand-copies keyword lists, so the corpus can't drift stale the
way a hand-written matrix would. Point GITGALAXY_PATH at the checkout; the default
assumes the sibling layout used on the dev box.
"""

import os
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
