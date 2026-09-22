"""Validate a manifest's calls_out_to arrays against docs/calls_out_truth.json.

The truth file is the corpus-design oracle for the Information Flow Graph metric
(SPEC rule 5, gitgalaxy#3264 Phase 3): it was hand-derived from the data/<lang>/
sources with the engine NOT in the loop. Running this before applying a
`rebless.py` diff breaks the circularity of blessing whatever the engine emits:

  FAIL  a forbidden name (decoy or keyword trap) appears in any calls_out_to,
        an entry_required callee is missing from the entry node,
        or an expect_empty language has any non-empty calls_out_to.
  WARN  a periphery callee is missing (precision-first engines may skip them).

Usage:
    python tools/check_calls_out_truth.py <lang> [...]   # named languages
    python tools/check_calls_out_truth.py --all          # every language in the truth file
    python tools/check_calls_out_truth.py <lang> --manifest <path>   # override manifest

Exit 0 clean (warnings allowed), 1 any failure, 2 truth/manifest missing.
"""

import argparse
import json
import pathlib
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = REPO_ROOT / "data"
TRUTH = REPO_ROOT / "docs" / "calls_out_truth.json"


def observed_calls(manifest):
    """{func_name: calls_out_to list} across every file in the manifest."""
    nodes = {}
    for file_entry in manifest.get("files", {}).values():
        for func, node in file_entry.get("expected_function_nodes", {}).items():
            if "calls_out_to" in node:
                nodes[func] = node["calls_out_to"]
    return nodes


def check(lang, truth, manifest):
    """Returns (failures, warnings) for one language."""
    failures, warnings = [], []
    entry = truth[lang]
    nodes = observed_calls(manifest)
    forbidden = set(truth["_meta"]["global_forbidden"]) | set(entry.get("forbidden_everywhere", []))

    for func, calls in nodes.items():
        bad = forbidden.intersection(calls)
        if bad:
            failures.append(f"{lang}: {func} contains forbidden name(s) {sorted(bad)}")

    if entry.get("expect_empty"):
        for func, calls in nodes.items():
            if calls:
                failures.append(f"{lang}: expect_empty but {func} has calls_out_to {calls}")
        return failures, warnings

    entry_node = entry["entry_node"]
    if entry_node not in nodes:
        failures.append(f"{lang}: entry node {entry_node!r} has no calls_out_to in the manifest")
    else:
        missing = set(entry["entry_required"]) - set(nodes[entry_node])
        if missing:
            failures.append(f"{lang}: entry {entry_node} missing required callee(s) {sorted(missing)}")

    for func, planted in entry.get("periphery", {}).items():
        if func not in nodes:
            warnings.append(f"{lang}: periphery function {func!r} not in manifest")
            continue
        skipped = set(planted) - set(nodes[func])
        if skipped:
            warnings.append(f"{lang}: {func} misses periphery callee(s) {sorted(skipped)}")

    return failures, warnings


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("languages", nargs="*", help="language folder names")
    parser.add_argument("--all", action="store_true", help="check every language in the truth file")
    parser.add_argument("--manifest", help="manifest path override (single-language runs only)")
    args = parser.parse_args(argv)

    if not TRUTH.exists():
        print(f"ERROR truth file missing: {TRUTH}")
        return 2
    truth = json.loads(TRUTH.read_text(encoding="utf-8"))
    langs = [k for k in truth if k != "_meta"] if args.all else args.languages
    if not langs:
        parser.error("name at least one language or pass --all")
    if args.manifest and len(langs) != 1:
        parser.error("--manifest only applies to a single language")

    total_failures = 0
    for lang in langs:
        if lang not in truth:
            print(f"ERROR {lang}: not in {TRUTH.name}")
            total_failures += 1
            continue
        manifest_path = pathlib.Path(args.manifest) if args.manifest else DATA / lang / "expected_signals.json"
        if not manifest_path.exists():
            print(f"ERROR {lang}: manifest missing: {manifest_path}")
            return 2
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        failures, warnings = check(lang, truth, manifest)
        for line in failures:
            print(f"FAIL {line}")
        for line in warnings:
            print(f"WARN {line}")
        if not failures:
            print(f"PASS {lang}")
        total_failures += len(failures)

    return 1 if total_failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
