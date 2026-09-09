"""Print one deviation_ledger.json entry as a condensed headline, not the 3 KB
whole-entry JSON a session currently reads to check one field (keyword-rosetta#113).

Usage:
    python tools/ledger_show.py <id>                  # headline fields + verdict head/tail
    python tools/ledger_show.py <id> --short           # headline fields only, no verdict
    python tools/ledger_show.py <id> --grep <text>     # headline fields + only verdict
                                                        # sentences containing <text>
    python tools/ledger_show.py --grep <text>          # search every entry's id/signal/
                                                        # verdict for <text>; one headline
                                                        # line per match, id omitted

`--short` and `--grep` compose: `--short --grep <text>` prints headline fields for
every matching entry with no verdict text at all -- useful to scope a search before
reading any one entry in full.
"""

import json
import pathlib
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
HEADLINE_FIELDS = [
    "signal", "languages_seen", "disposition", "status",
    "still_reproduces", "upstream_issue", "resolved_by",
]


def _consume_flag_value(argv, flag):
    out = list(argv)
    value = None
    if flag in out:
        i = out.index(flag)
        if i + 1 >= len(out):
            raise SystemExit(f"{flag} needs a value")
        value = out[i + 1]
        del out[i : i + 2]
    return out, value


def headline(entry):
    lines = [f"id: {entry['id']}"]
    for field in HEADLINE_FIELDS:
        lines.append(f"{field}: {entry.get(field)}")
    return "\n".join(lines)


def verdict_view(entry, grep_text):
    verdict = entry.get("verdict") or ""
    if grep_text is None:
        if len(verdict) <= 600:
            return verdict
        return f"{verdict[:300]}\n  ...\n{verdict[-300:]}"
    needle = grep_text.lower()
    # Split on sentence boundaries (". ") rather than lines -- verdicts are prose,
    # not markdown, so there is no line structure to grep against.
    sentences = [s.strip() for s in verdict.replace("\n", " ").split(". ") if s.strip()]
    matches = [s for s in sentences if needle in s.lower()]
    if not matches:
        return f"(no verdict sentence matches {grep_text!r})"
    return "\n".join(f"- {s}" for s in matches)


def main():
    argv, grep_text = _consume_flag_value(sys.argv[1:], "--grep")
    short = "--short" in argv
    argv = [a for a in argv if a != "--short"]

    ledger = json.loads((REPO_ROOT / "deviation_ledger.json").read_text())
    entries = {e["id"]: e for e in ledger["entries"]}

    if argv:
        entry_id = argv[0]
        entry = entries.get(entry_id)
        if entry is None:
            sys.exit(f"no ledger entry {entry_id!r}")
        print(headline(entry))
        if not short:
            print()
            print(verdict_view(entry, grep_text))
        return 0

    if grep_text is None:
        sys.exit(__doc__)

    needle = grep_text.lower()
    matched = [
        e for e in ledger["entries"]
        if needle in e["id"].lower()
        or needle in (e.get("signal") or "").lower()
        or needle in (e.get("verdict") or "").lower()
    ]
    if not matched:
        print(f"no entries match {grep_text!r}")
        return 1
    for entry in matched:
        print(headline(entry))
        if not short:
            print()
            print(verdict_view(entry, grep_text))
        print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
