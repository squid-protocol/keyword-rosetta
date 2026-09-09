"""Re-bless one language's manifest against a named engine, doing the scan + diff +
apply + note + optional ledger-retire + re-verify loop a rebless PR does by hand
today (keyword-rosetta#113 -- the same JSON edit was hand-written four times across
gitgalaxy#2908's first two phases).

Usage:
    python tools/rebless.py <lang> --engine <gitgalaxy-worktree> --note "<dated sentence>" \\
        [--retire <ledger-id> --resolved-by gitgalaxy#N --verdict "<text>"] \\
        [--add-keys k1,k2] [--dry-run]

Scans data/<lang> with the named engine the way verify_language.py does (same
GALAXYSCOPE_BIN/GITGALAXY_PATH/PYTHONPATH `--engine` mechanism, see
`_registry.apply_engine`), diffs observed vs data/<lang>/expected_signals.json, and:

  --dry-run   prints the diff (file, key, old -> new) and, if --retire is given,
              the ledger entry that would be retired -- no files written.
  otherwise   applies ONLY the cells that moved, appends --note to the manifest's
              `notes` (a running prose string -- see any existing manifest for the
              "<dated sentence> (issue#N): ..." shape to match), optionally retires
              one deviation_ledger.json entry (appends --verdict to its own verdict
              field, sets still_reproduces: false and resolved_by), re-serializes
              both files with their real formatting (manifest: indent=2,
              ensure_ascii=False; ledger: ensure_ascii=True -- the round-trip is
              asserted against each file BEFORE any edit, and the tool refuses to
              write if a file doesn't already round-trip that way, so a rebless
              diff is never noise from reformatting untouched entries), then
              re-runs verify_language.py <lang> and exits with its status.

Nothing moving and no --retire is not an error: it prints "nothing moved" and exits
0 with no writes -- safe to run speculatively.

--add-keys k1,k2 adds brand-new manifest keys a diff alone can't add on its own (a
key missing from expected_signals.json is "absent", not "changed") -- for a rule
that used to be None and just gained one; see AGENTS.md hard rule 8. Every added
key must actually appear in the scan schema (skipped with a warning otherwise).
"""

import argparse
import json
import pathlib
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import _registry

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent


def _assert_roundtrip(path, ensure_ascii):
    """Load path and refuse to proceed if it doesn't already serialize back to
    itself under (indent=2, ensure_ascii=ensure_ascii) -- see module docstring."""
    raw = path.read_text(encoding="utf-8")
    data = json.loads(raw)
    reserialized = json.dumps(data, indent=2, ensure_ascii=ensure_ascii) + "\n"
    if reserialized != raw:
        raise SystemExit(
            f"{path}: does not round-trip under indent=2, ensure_ascii={ensure_ascii} "
            "-- refusing to write (would clobber real formatting with reformatting "
            "noise). Fix the file's own formatting first."
        )
    return data


def _write(path, data, ensure_ascii):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=ensure_ascii) + "\n", encoding="utf-8")


def _qualify_issue(ref):
    """`gitgalaxy#N` -> `squid-protocol/gitgalaxy#N`, matching every existing
    resolved_by value; anything already qualified or more complex passes through."""
    if ref.startswith("gitgalaxy#"):
        return "squid-protocol/" + ref
    return ref


def diff_manifest(manifest, observed, add_keys):
    """(moved, warnings). moved is [(file, key, old_or_None, new)]."""
    moved, warnings = [], []
    for fname, expectations in manifest.get("files", {}).items():
        obs = observed.get(fname)
        if obs is None:
            warnings.append(f"{fname}: NOT SCANNED (skipped)")
            continue
        for key, want in expectations.items():
            got = obs.get(key)
            if got is None:
                warnings.append(f"{fname}: signal {key!r} not in scan schema (skipped)")
            elif got != want:
                moved.append((fname, key, want, got))
        for key in add_keys:
            if key in expectations:
                continue
            got = obs.get(key)
            if got is None:
                warnings.append(f"{fname}: --add-keys {key!r} not in scan schema (skipped)")
                continue
            moved.append((fname, key, None, got))
    return moved, warnings


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("language")
    parser.add_argument("--engine", required=True, metavar="WORKTREE")
    parser.add_argument("--note", required=True)
    parser.add_argument("--retire", metavar="LEDGER_ID")
    parser.add_argument("--resolved-by", metavar="ISSUE")
    parser.add_argument("--verdict", metavar="TEXT")
    parser.add_argument("--add-keys", metavar="k1,k2")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.retire and not (args.resolved_by and args.verdict):
        parser.error("--retire needs both --resolved-by and --verdict")

    _registry.apply_engine(args.engine)
    import verify_language  # deferred: must import after apply_engine sets its env

    language_dir = REPO_ROOT / "data" / args.language
    manifest_path = language_dir / "expected_signals.json"
    if not manifest_path.exists():
        sys.exit(f"no manifest at {manifest_path}")

    manifest = _assert_roundtrip(manifest_path, ensure_ascii=False)
    add_keys = [k.strip() for k in args.add_keys.split(",")] if args.add_keys else []

    colmap = verify_language._signal_columns()
    with tempfile.TemporaryDirectory(prefix=f"rebless_{args.language}_") as tmp:
        db_path = verify_language.scan(language_dir, pathlib.Path(tmp))
        observed = verify_language.observed_signals(db_path, colmap)

    moved, warnings = diff_manifest(manifest, observed, add_keys)
    for w in warnings:
        print(f"  ! {w}")
    if moved:
        print(f"{args.language}: {len(moved)} cell(s) moved against {args.engine}")
        for fname, key, old, new in moved:
            was = "absent" if old is None else old
            print(f"  {fname}: {key} {was} -> {new}")
    else:
        print(f"{args.language}: nothing moved against {args.engine}")

    retired_entry, ledger, ledger_path = None, None, REPO_ROOT / "deviation_ledger.json"
    if args.retire:
        ledger = _assert_roundtrip(ledger_path, ensure_ascii=True)
        retired_entry = next((e for e in ledger["entries"] if e["id"] == args.retire), None)
        if retired_entry is None:
            sys.exit(f"no ledger entry {args.retire!r}")
        print(f"retire {args.retire}: still_reproduces -> false, "
              f"resolved_by {_qualify_issue(args.resolved_by)}")

    if not moved and not args.retire:
        print("nothing to write")
        return 0

    if args.dry_run:
        print("--dry-run: no files written")
        return 0

    for fname, key, _old, new in moved:
        manifest["files"][fname][key] = new
    note = args.note.strip()
    existing = manifest.get("notes", "")
    manifest["notes"] = f"{existing.rstrip()} {note}".strip() if existing else note
    _write(manifest_path, manifest, ensure_ascii=False)

    if args.retire:
        retired_entry["verdict"] = f"{retired_entry['verdict'].rstrip()} {args.verdict.strip()}"
        retired_entry["still_reproduces"] = False
        retired_entry["resolved_by"] = _qualify_issue(args.resolved_by)
        _write(ledger_path, ledger, ensure_ascii=True)

    return verify_language.verify(args.language)


if __name__ == "__main__":
    sys.exit(main())
