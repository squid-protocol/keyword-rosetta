"""Size the corpus's ledgered FP shapes against real-world code.

The control corpus proves each shape EXISTS; this tool measures how often each
one fires in the wild, by grepping the shape's signature across a real corpus
(default: a language-crucible checkout — the same pinned corpus gitgalaxy's own
golden masters scan). Output: docs/incidence_report.md.

Each measurement is an ESTIMATE from the shape's lexical signature, not an
engine run — good for sizing ("affects N% of files"), not for exact counts.

Usage:
    python tools/incidence_report.py [/path/to/crucible/data]
"""

import json
import os
import pathlib
import re
import statistics
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = REPO_ROOT / "docs" / "incidence_report.md"
DEFAULT_CORPUS = "/srv/storage_16tb/projects/all_language_repo/data"

DEBT = r"(?:HACK|FIXME|XXX|BUG|KLUDGE|TODO|WIP|STUB)"

# (ledger id, issue, description, {language-dir: [extensions]}, per-file counter)
def count_pattern(pat, flags=0):
    rx = re.compile(pat, flags)
    return lambda text: len(rx.findall(text))

# ------------------------------------------------------------------------------
# The documentation row (gitgalaxy#2908 Phase 5) is NOT a lexical shape: the
# per-unit coverage ratio's real-world behaviour -- how many files carry a
# single extracted unit (D5's 0-or-100 question), and whether any reaches a
# hitlist -- can only be read off an engine run. It is rendered as its own
# clearly-labelled section from gitgalaxy's committed golden master (the
# engine's own scan of this same crucible corpus), found via GITGALAXY_PATH;
# when no golden master is reachable the section says so instead of guessing.
def documentation_section():
    gg = os.environ.get("GITGALAXY_PATH", "")
    golden = pathlib.Path(gg) / "tests" / "golden_master_audit.json" if gg else None
    lines = ["", "## The documentation score, per unit (gitgalaxy#2908) -- engine run, not lexical", ""]
    if not (golden and golden.is_file()):
        lines += ["*(set `GITGALAXY_PATH` to a gitgalaxy checkout to render this section "
                  "from `tests/golden_master_audit.json`)*"]
        return lines
    d = json.loads(golden.read_text())

    def num(x):
        try:
            return float(str(x).rstrip("%").replace(",", ""))
        except (ValueError, TypeError):
            return None

    files = []
    for g in d["6. Parsed Files (Scanned Artifacts)"].values():
        for f in (g.get("Files") or {}).values():
            v = num(f.get("4. Vulnerability & Risk Exposures", {}).get("Documentation Exposure"))
            if v is None:
                continue
            fn = f.get("5. Function Analysis") or []
            entries = fn.values() if isinstance(fn, dict) else fn
            units = sum(1 for x in entries if isinstance(x, dict))
            loc = num(f.get("3. Architectural Profile", {}).get("Coding LOC")) or 0.0
            files.append((v, units, loc))
    scored = [(v, u, loc) for v, u, loc in files if u > 0]
    na = len(files) - len(scored)
    one = [(v, u, loc) for v, u, loc in scored if u == 1]
    one100 = [x for x in one if x[0] == 100.0]
    top20 = sorted(scored, key=lambda x: (-x[0], -x[2]))[:20]
    one_in_top = sum(1 for x in top20 if x[1] == 1)
    vals = [v for v, _, _ in scored]
    lines += [
        f"`risk_documentation` is a ratio over extracted units since gitgalaxy#2938; a file "
        f"with no units is n/a (D6), and a one-unit file reads 0 or 100 with no damping (D5). "
        f"Measured on the golden master's engine run over this same crucible corpus:",
        "",
        f"- {len(scored)} scored files, {na} n/a (no units); mean {statistics.mean(vals):.1f}, "
        f"median {statistics.median(vals):.1f}; {sum(1 for v in vals if v == 100)} at 100, "
        f"{sum(1 for v in vals if v == 0)} at 0.",
        f"- one-unit files: {len(one)} ({len(one) / len(scored):.0%} of scored); "
        f"{len(one100)} read 100; **{one_in_top} reach the top-20 hitlist** "
        f"(score desc, coding-LOC tiebreak) -- the roll-ups are mass-weighted, so the "
        f"0-or-100 granularity of a one-unit file stays out of the maintainer-facing lists. "
        f"D5 (no damping) was confirmed on this evidence (gitgalaxy#2908 Phase 5).",
    ]
    return lines


SHAPES = [
    ("php-open-tag-counts-branch", "#2541",
     "branch +1 per `<?php`/`<?=` open tag (ternary-? alternation matches the tag)",
     {"php": [".php", ".phtml"]},
     count_pattern(r"<\?(?:php|=)?")),

    ("go-import-counts-bypass", "#2542",
     "safety_bypasses +1 per quoted import (dot-import alternation's dot is optional)",
     {"go": [".go"]},
     count_pattern(r'\bimport\s+(?:\.\s+)?"|^\s+(?:[a-zA-Z0-9_.]+\s+)?"[a-zA-Z0-9_.\-/]+"$', re.M)),

    ("cobol-hyphen-identifier-debt-leak", "#2537",
     "fragile/planned_debt counted inside hyphenated identifiers (BUG-COUNT, WS-FIX-FLAG)",
     {"cobol": [".cbl", ".cob", ".cpy"]},
     count_pattern(rf"[A-Z0-9]-{DEBT}\b|\b{DEBT}-[A-Z0-9]")),

    ("css-hyphen-identifier-debt-leak", "#2537 (predicted class)",
     "same leak shape in css class names (.bug-icon, .todo-list)",
     {"css": [".css", ".scss", ".less"]},
     count_pattern(rf"[.#][\w-]*(?:{DEBT})-[\w-]*|[.#][\w-]+-(?:{DEBT})\b", re.I)),

    ("kotlin-return-in-branch", "#2545",
     "branch +1 per return statement (6-language family; kotlin shown)",
     {"kotlin": [".kt", ".kts"]},
     count_pattern(r"\breturn\b")),

    ("solidity-return-in-branch", "#2545",
     "branch +1 per return statement (6-language family; solidity shown)",
     {"solidity": [".sol"]},
     count_pattern(r"\breturn\b")),

    ("string-literal-branch-keywords", "#2535/#2546",
     "branch keywords inside double-quoted literals (phantom flux trigger candidates)",
     {"python": [".py"], "javascript": [".js"], "c": [".c", ".h"], "ruby": [".rb"]},
     count_pattern(r'"[^"\n]*\b(?:if|while|for|try)\b[^"\n]*"')),

    ("swift-open-api-fp", "#2544",
     "api-exposure from the bare word `open` outside declaration position",
     {"swift": [".swift"]},
     lambda t: max(0, len(re.findall(r"\bopen\b", t))
                   - len(re.findall(r"\bopen\s+(?:class|func|var|let|struct|enum|protocol|extension)\b", t)))),

    ("html-script-func-start-unreachable", "#2549",
     "script/style tags whose func_start credit is silently lost end-to-end",
     {"html": [".html", ".htm"]},
     count_pattern(r"<(?:script|style)\b")),
]


def main(argv):
    corpus = pathlib.Path(argv[1] if len(argv) > 1 else DEFAULT_CORPUS)
    if not corpus.is_dir():
        print(f"corpus not found: {corpus}")
        return 1

    lines = [
        "# Real-World Incidence of Ledgered Shapes",
        "",
        f"Generated by `tools/incidence_report.py` against `{corpus}` "
        "(the language-crucible corpus — real, licensed, pinned code; the same corpus "
        "gitgalaxy's golden masters scan).",
        "",
        "The control corpus proves each shape exists; this table sizes it in the wild. "
        "Counts are lexical estimates from each shape's signature, not engine runs — "
        "use them for 'how big is this' framing, not exact accounting.",
        "",
        "| shape | issue | affected files | occurrences | per affected file |",
        "|---|---|---|---|---|",
    ]
    details = []
    for shape_id, issue, desc, langs, counter in SHAPES:
        total_files = affected = occurrences = 0
        for lang_dir, exts in langs.items():
            base = corpus / lang_dir
            if not base.is_dir():
                continue
            for f in base.rglob("*"):
                if f.suffix.lower() not in exts or not f.is_file():
                    continue
                try:
                    text = f.read_text(errors="ignore")
                except OSError:
                    continue
                total_files += 1
                n = counter(text)
                if n:
                    affected += 1
                    occurrences += n
        pct = f"{affected}/{total_files} ({affected / total_files:.0%})" if total_files else "corpus has none"
        per = f"{occurrences / affected:.1f}" if affected else "—"
        issue_link = re.sub(
            r"#(\d+)",
            r"[#\1](https://github.com/squid-protocol/gitgalaxy/issues/\1)",
            issue,
        )
        lines.append(f"| `{shape_id}` | {issue_link} | {pct} | {occurrences} | {per} |")
        details.append(f"- **`{shape_id}`** — {desc} (languages: {', '.join(langs)})")

    lines += documentation_section()

    lines += ["", "## Shape descriptions", ""] + details + [
        "",
        "A shape at ~100% of files (php open tag, go imports, return-counting) is a "
        "constant per-file bias — it shifts every score in that language uniformly. A "
        "sparse shape (debt-in-identifiers) is a per-repo hazard — invisible until it "
        "isn't. Both kinds are already baked into every real scan GitGalaxy has ever "
        "produced for these languages; fixing the filed issues re-baselines them.",
        "",
    ]
    OUT.write_text("\n".join(lines))
    print(f"wrote {OUT.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
