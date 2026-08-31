"""Mine per-language keyword menus from GitGalaxy's live rule registry.

For each language and each public signal rule, scrape word-like literal candidates
out of the compiled pattern's source, then keep only candidates the rule itself
matches when planted standalone — so every menu entry is plantable by construction.
Two match contexts are tried per candidate (the bare token as its own line, and the
token surrounded by spaces) because some rules anchor to line start/end.

Usage:
    python tools/keyword_menu.py            # write docs/menus/<language>.json for all
    python tools/keyword_menu.py python     # one language, print to stdout too
"""

import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _registry import CORE_SIGNALS, active_rules, load_definitions

MENU_DIR = pathlib.Path(__file__).resolve().parent.parent / "docs" / "menus"

# Word-ish runs inside a pattern source, allowing the joiners that appear inside
# real keywords (os\.system, @todo, #include, type: ignore is out of scope).
_CANDIDATE = re.compile(r"[@#]?[A-Za-z_][A-Za-z0-9_]*(?:(?:\\\.|::|->|\s)[A-Za-z_][A-Za-z0-9_]*)*")

# Pattern-source runs that are regex syntax, not keywords.
_META = {"b", "B", "s", "S", "w", "W", "d", "D", "n", "t", "A", "Z", "P", "x"}


def _candidates(pattern_source):
    seen = []
    for m in _CANDIDATE.finditer(pattern_source):
        tok = m.group(0).replace("\\.", ".")
        # Strip a leading escape residue like the 'b' of \b glued by the scraper.
        if tok in _META or len(tok) < 2:
            continue
        if tok not in seen:
            seen.append(tok)
    return seen


def _plantable(rule, token):
    """A token is plantable if the rule matches it in a bare context."""
    for context in (token, f" {token} ", f"{token}\n"):
        try:
            if rule.search(context):
                return True
        except Exception:
            return False
    return False


def build_menu(lang, rules):
    menu = {}
    for key, rule in sorted(rules.items()):
        if key.startswith("_") or rule is None or not hasattr(rule, "pattern"):
            continue
        plantable = [t for t in _candidates(rule.pattern) if _plantable(rule, t)]
        menu[key] = {
            "core": key in CORE_SIGNALS,
            "keywords": plantable,
            "pattern_defined": True,
        }
    return menu


def main(argv):
    definitions = load_definitions()
    langs = active_rules(definitions)
    targets = argv[1:] or sorted(langs)
    MENU_DIR.mkdir(parents=True, exist_ok=True)
    for lang in targets:
        if lang not in langs:
            print(f"unknown/inactive language: {lang}", file=sys.stderr)
            return 1
        menu = build_menu(lang, langs[lang])
        out = MENU_DIR / f"{lang}.json"
        out.write_text(json.dumps(menu, indent=2, ensure_ascii=False) + "\n")
        empty = [k for k, v in menu.items() if v["core"] and not v["keywords"]]
        note = f"  (core signals with no plantable literal: {empty})" if empty else ""
        print(f"{lang}: {len(menu)} signals -> {out.relative_to(MENU_DIR.parent.parent)}{note}")
        if len(argv) == 2:
            print(json.dumps(menu, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
