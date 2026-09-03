"""Screen a candidate plant: which of a language's rules does this text fire?"""
import sys
sys.path.insert(0, '/home/joe/nyx_projects/gitgalaxy')
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
