"""Baseline-gated audit of unreviewed n/a cells (rule-absent signals).

A signal with no rule in a language's registry entry is n/a (incomparable) in
the bias tooling -- but an absence is only *legitimately* n/a once a validated
deviation-ledger entry names that language and signal and records why the
concept isn't expressible (docs/GATING.md "n/a semantics"; jcl's safety rule
was None right up until gitgalaxy#2610 proved real morphology, so an absence
is never simply assumed fine).

This check recomputes the unreviewed set live -- the language registry from the
GITGALAXY_PATH checkout, the ledger from this repo -- so it needs NO scan and
runs in seconds, in both repos' CI:

  * here (verify.yml): a corpus PR cannot introduce a new unreviewed absence
    (e.g. by deleting a ledger entry without restoring the rule);
  * in gitgalaxy (rosetta-audit.yml): an engine PR that removes/nulls a rule
    must ship the ledger entry justifying it, or fail at the source.

Baseline-gated like gitgalaxy's ruff/mypy audits: docs/na_baseline.json holds
the known backlog (epic gitgalaxy#2560's review worklist); --ci fails only on
NEW unreviewed cells beyond it. After reviewing cells (ledgering the real
morphology or fixing the engine gap), run --regenerate to shrink the baseline.

Usage:
    python tools/na_check.py               # report everything
    python tools/na_check.py --ci          # exit 1 on new unreviewed cells
    python tools/na_check.py --regenerate  # rewrite docs/na_baseline.json
"""

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _registry import load_definitions, unmeasurable_signals
from bias_report import PLANTED, classify_na

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
BASELINE = REPO_ROOT / "docs" / "na_baseline.json"


def current_unreviewed():
    languages = sorted(
        p.parent.name for p in (REPO_ROOT / "data").glob("*/expected_signals.json")
    )
    na_map = {
        lang: sigs
        for lang, sigs in unmeasurable_signals(load_definitions(), list(PLANTED)).items()
        if lang in languages
    }
    ledger = json.loads((REPO_ROOT / "deviation_ledger.json").read_text())["entries"]
    cls = classify_na(ledger, na_map)
    return sorted(
        f"{lang}/{sig}"
        for sig, per_lang in cls.items()
        for lang, state in per_lang.items()
        if state == "unreviewed"
    )


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    unreviewed = current_unreviewed()

    if mode == "--regenerate":
        BASELINE.write_text(json.dumps({"unreviewed": unreviewed}, indent=1) + "\n")
        print(f"wrote {BASELINE.relative_to(REPO_ROOT)} ({len(unreviewed)} cells)")
        return 0

    baseline = set(
        json.loads(BASELINE.read_text())["unreviewed"] if BASELINE.exists() else []
    )
    new = [c for c in unreviewed if c not in baseline]
    resolved = sorted(baseline - set(unreviewed))

    print(f"unreviewed n/a cells: {len(unreviewed)} ({len(baseline)} baselined)")
    if resolved:
        print(f"resolved since baseline (run --regenerate to shrink it): {resolved}")
    if new:
        print("NEW unreviewed rule absences (not in docs/na_baseline.json):")
        for c in new:
            print(f"  - {c}")
        print(
            "Each needs either a validated ledger entry naming the language and "
            "signal (real morphology), or the rule restored/added (engine gap) -- "
            "see docs/GATING.md 'n/a semantics'."
        )
        return 1 if mode == "--ci" else 0
    print("no new unreviewed absences")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
