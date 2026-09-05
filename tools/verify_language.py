"""Verify one language folder end-to-end: galaxyscope scan vs expected_signals.json.

Runs the real galaxyscope CLI (--db-only) over data/<language>/ — deliberately the
full pipeline (aperture, prism, detector, census), not a direct detector call, so
file-exclusion bugs (gitgalaxy#2512 class) surface as missing files here.

Usage:
    python tools/verify_language.py python              # gate: diff vs manifest, exit 1 on mismatch
    python tools/verify_language.py python --report     # print every nonzero observed signal per file

Environment:
    GALAXYSCOPE_BIN  path to the galaxyscope binary (default: "galaxyscope" on PATH)
    GITGALAXY_PATH   gitgalaxy checkout, for the SHORT_KEY_MAP schema (see _registry.py)

What a manifest key asserts (gitgalaxy#2729):
    Every signal key is the recorder column SHORT_KEY_MAP names for it, EXCEPT the
    ones in RAW_COLUMNS, which read the engine's pre-adjustment snapshot instead.
    galaxyscope's Contextual Baseline Fix rewrites `api` in place for any imported
    file (its uncalled functions become API surface), so the adjusted arch_api
    column let 36 of 44 languages pass `api` without their api rule matching
    anything. `api` now asserts what the rule found; the conversion is pinned
    separately as `api_orphan_credit` (DERIVED_KEYS) because it is also the gate's
    only proof that the main->a->b->c import chain resolved.
"""

import json
import os
import pathlib
import sqlite3
import subprocess
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _registry import GITGALAXY_PATH

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
GALAXYSCOPE_BIN = os.environ.get("GALAXYSCOPE_BIN", "galaxyscope")


# Signals whose manifest key reads the recorder's RAW (pre-adjustment) column rather
# than the one SHORT_KEY_MAP names. gitgalaxy#2536 added the snapshots; #2729 is why
# the gate reads them: `api` must assert the api RULE, not rule + converted orphans.
# Same map bias_report.py's RISK_INPUT_COLUMNS uses for the derivation edges.
RAW_COLUMNS = {"api": "raw_arch_api"}

# Synthetic manifest keys computed from two recorder columns: key -> (minuend,
# subtrahend). `api_orphan_credit` = arch_api - raw_arch_api = the orphans the
# Contextual Baseline Fix converted into API surface for an imported file. Expect
# it to equal the file's uncalled function count in a/b/c and 0 in main (popularity
# 0): a nonzero value is the proof the import chain resolved (ledger
# api-contextual-baseline-fix).
DERIVED_KEYS = {"api_orphan_credit": ("arch_api", "raw_arch_api")}


def _signal_columns():
    """{db_column: signal_key} for every SIGNAL_SCHEMA entry (RAW_COLUMNS applied)."""
    if GITGALAXY_PATH not in sys.path:
        sys.path.insert(0, GITGALAXY_PATH)
    from gitgalaxy.recorders.record_keeper import RecordKeeper
    from gitgalaxy.standards.analysis_lens import RECORDING_SCHEMAS

    keeper = RecordKeeper()  # only need the mapping; build it via a throwaway instance
    schema = RECORDING_SCHEMAS.get("SIGNAL_SCHEMA", [])
    return {
        RAW_COLUMNS.get(key, keeper.SHORT_KEY_MAP.get(key, key)): key for key in schema
    }


def scan(language_dir, out_dir):
    """Run galaxyscope --db-only and return the produced sqlite path."""
    before = set(out_dir.glob("*"))
    result = subprocess.run(
        [GALAXYSCOPE_BIN, str(language_dir), "--db-only"],
        cwd=out_dir,
        capture_output=True,
        text=True,
        timeout=600,
    )
    dbs = sorted(p for p in out_dir.rglob("*.db") if p not in before)
    if result.returncode != 0 or not dbs:
        sys.stderr.write(result.stdout[-2000:] + result.stderr[-2000:])
        raise RuntimeError(
            f"galaxyscope failed (rc={result.returncode}, dbs found: {dbs})"
        )
    return dbs[0]


def observed_signals(db_path, colmap):
    """{file_name: {signal_key: count}} for all scanned files, plus the file list."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    have = {r[1] for r in conn.execute("PRAGMA table_info(file_data)")}
    cols = [c for c in colmap if c in have]
    derived = {k: v for k, v in DERIVED_KEYS.items() if all(c in have for c in v)}
    extra = sorted({c for pair in derived.values() for c in pair} - set(cols))
    rows = conn.execute(
        f"SELECT file_name, file_path, {', '.join(cols + extra)} FROM file_data"
    ).fetchall()
    out = {}
    for row in rows:
        signals = {colmap[c]: (row[c] or 0) for c in cols}
        for key, (minuend, subtrahend) in derived.items():
            signals[key] = (row[minuend] or 0) - (row[subtrahend] or 0)
        out[row["file_name"]] = signals
    return out


def verify(language, report=False):
    language_dir = REPO_ROOT / "data" / language
    manifest_path = language_dir / "expected_signals.json"
    if not language_dir.is_dir():
        print(f"no such language folder: {language_dir}")
        return 1

    colmap = _signal_columns()
    with tempfile.TemporaryDirectory(prefix=f"rosetta_{language}_") as tmp:
        db_path = scan(language_dir, pathlib.Path(tmp))
        observed = observed_signals(db_path, colmap)

    if report:
        print(f"=== observed nonzero signals: {language} ===")
        for fname in sorted(observed):
            nonzero = {k: v for k, v in sorted(observed[fname].items()) if v}
            print(f"\n{fname}:")
            for k, v in nonzero.items():
                print(f"  {k:32s} {v}")
        return 0

    if not manifest_path.exists():
        print(f"missing {manifest_path} — run with --report and author it first")
        return 1
    manifest = json.loads(manifest_path.read_text())

    failures = []
    expected_files = manifest.get("files", {})
    for fname, expectations in expected_files.items():
        if fname not in observed:
            failures.append(f"{fname}: NOT SCANNED (aperture/census exclusion? gitgalaxy#2512 class)")
            continue
        for key, want in expectations.items():
            got = observed[fname].get(key)
            if got is None:
                failures.append(f"{fname}: signal {key!r} not in scan schema")
            elif got != want:
                failures.append(f"{fname}: {key} expected {want}, got {got}")
    for fname in observed:
        if fname not in expected_files and fname in {"main", "a", "b", "c"}:
            failures.append(f"{fname}: scanned but missing from manifest")

    if failures:
        print(f"FAIL {language}: {len(failures)} mismatch(es)")
        for f in failures:
            print(f"  - {f}")
        return 1
    print(f"PASS {language}: {sum(len(v) for v in expected_files.values())} assertions across {len(expected_files)} files")
    return 0


def main(argv):
    if not argv[1:]:
        print(__doc__)
        return 2
    language = argv[1]
    return verify(language, report="--report" in argv)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
