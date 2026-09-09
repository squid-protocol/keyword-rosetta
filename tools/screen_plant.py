"""Screen a candidate plant: which of a language's rules does this text fire?

Usage:
    echo '[("python", "os.system(cmd)", "high_risk_execution")]' | python tools/screen_plant.py
    echo '[...]' | python tools/screen_plant.py --engine <gitgalaxy-worktree>

--engine points GITGALAXY_PATH (and PYTHONPATH, for consistency with the other
tools' --engine) at a branch checkout instead of the $GITGALAXY_PATH env var,
replacing the inline `LANGUAGE_DEFINITIONS[lang]["rules"]` loop the
rule-contract-audit skill's Phase 2 was telling agents to hand-write because this
hard-coded the primary checkout (keyword-rosetta#113).
"""
import pathlib
import sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import _registry

sys.argv[1:] = _registry.consume_engine_arg(sys.argv[1:])
from _registry import GITGALAXY_PATH  # honours $GITGALAXY_PATH, so a branch worktree can be screened (gitgalaxy#2765)
sys.path.insert(0, str(GITGALAXY_PATH))
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS as LD

def screen(lang, text, want):
    rules = LD[lang]['rules']
    hits = {}
    for name, pat in rules.items():
        if name.startswith('_') or pat is None or not hasattr(pat, 'findall'):
            continue
        n = len(pat.findall(text))
        if n:
            hits[name] = n
    extra = {k: v for k, v in hits.items() if k != want}
    flag = 'CLEAN' if not extra else 'COLLATERAL'
    print(f"  [{flag}] {lang}: {text!r}")
    print(f"     {want}={hits.get(want,0)}" + (f"   also fires: {extra}" if extra else "   (nothing else)"))
    return hits

if __name__ == '__main__':
    for lang, text, want in eval(sys.stdin.read()):
        screen(lang, text, want)
