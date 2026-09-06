"""Audit SPEC §Decoys 1: does each language's comment decoy actually assert anything?

A comment decoy only tests `prism.py` comment stripping if its prose carries keywords
the language's rules would have matched in the code stream. 67 of the corpus's 180
`decoy:` lines carried none at all until keyword-rosetta#73 -- stripping a comment that
contained no keyword proves nothing.

The test is deliberately run on the prose with the COMMENT MARKER STRIPPED. A rule that
fires only with the marker present is comment-anchored (`dead_code`, `spec_exposure`, the
debt family, `doc`, `ownership`) -- those rules are *supposed* to read comments, so
counting them would let a decoy pass while asserting nothing about stripping.

Usage:
    python tools/decoy_check.py            # table; exit 0
    python tools/decoy_check.py --gate     # exit 1 if any language is under the floor

Environment:
    GITGALAXY_PATH   gitgalaxy checkout, for LANGUAGE_DEFINITIONS (see _registry.py)
"""

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _registry import GITGALAXY_PATH

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = REPO_ROOT / "data"

# SPEC §Decoys 1: 2+ code-stream keywords in prose.
FLOOR = 2

# Rules that are anchored to the comment surface for at least one language, plus the
# ones SPEC plants IN comments on purpose. Excluded from the count even when they fire
# on bare prose, because a decoy scoring off them asserts nothing about stripping.
COMMENT_STREAM = {"dead_code", "spec_exposure", "fragile_debt", "planned_debt", "doc", "ownership"}

# Languages with no code-stream signal rule at all -- nothing a comment could shield.
# Kept as an explicit list so adding one is a deliberate act, not a silent skip.
EXEMPT = {"markdown"}

CLOSERS = ("-->", "*/", '"""', "#}")


def prose(line):
    """The decoy's prose, with the comment marker and any closer removed."""
    i = line.lower().index("decoy:")
    text = line[i + len("decoy:"):]
    for closer in CLOSERS:
        text = text.replace(closer, "")
    return text.strip()


def _rules(lang):
    if GITGALAXY_PATH not in sys.path:
        sys.path.insert(0, GITGALAXY_PATH)
    from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

    return LANGUAGE_DEFINITIONS[lang]["rules"]


def hits(lang, text):
    out = {}
    for name, pat in _rules(lang).items():
        if name.startswith("_") or pat is None or not hasattr(pat, "findall"):
            continue
        count = len(pat.findall(text + "\n"))
        if count:
            out[name] = count
    return out


def designated(lang):
    """The language's main.<ext> decoy line, or None."""
    for path in sorted((DATA / lang).glob("main.*")):
        if path.suffix == ".json":
            continue
        for line in path.read_text().splitlines():
            if "decoy:" in line.lower():
                return path.name, line
    return None, None


def audit(lang):
    fname, line = designated(lang)
    if line is None:
        return fname, None, {}, {}
    code = {k: v for k, v in hits(lang, prose(line)).items() if k not in COMMENT_STREAM}
    anchored = {k: v for k, v in hits(lang, line).items() if k not in hits(lang, prose(line))}
    return fname, line, code, anchored


def main(argv):
    gate = "--gate" in argv
    under = []
    print(f"{'language':17}{'kw':>3}  {'file':16} code-stream rules the prose fires")
    for d in sorted(DATA.iterdir()):
        if not d.is_dir():
            continue
        lang = d.name
        fname, line, code, _ = audit(lang)
        if lang in EXEMPT:
            print(f"{lang:17}{'--':>3}  {'(exempt)':16} no code-stream rule is defined for this language")
            continue
        total = sum(code.values())
        if total < FLOOR:
            under.append(lang)
        flag = " " if total >= FLOOR else "!"
        print(f"{lang:17}{total:>3}{flag} {fname or '-':16} {code or '(nothing -- asserts nothing)'}")
    print()
    if under:
        print(f"{len(under)} language(s) under SPEC's {FLOOR}-keyword floor: {' '.join(under)}")
        return 1 if gate else 0
    print(f"all {len(list(DATA.iterdir())) - len(EXEMPT)} non-exempt languages meet SPEC's {FLOOR}-keyword floor")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
