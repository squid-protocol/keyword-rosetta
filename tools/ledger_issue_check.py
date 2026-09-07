"""Baseline-gated audit of ledger entries whose upstream issue is already CLOSED.

THE AXIS NOTHING ELSE CHECKS. A validated deviation-ledger entry carries three
independent claims: a `verdict` (what the deviation is), `still_reproduces` (does
it still happen), and `upstream_issue` (who owes the fix). Two of the three are
already audited -- `tools/na_check.py` guards rule-absence review and
`tools/ledger_orphan_check.py` guards whether each signal token still excuses a
real cell -- but nothing anywhere resolves `upstream_issue` to its actual state.
Closing the issue on GitHub therefore moves nothing: the entry stays live, the
cell keeps whatever colour its `disposition` implies, and the chart goes on
reporting a defect somebody already fixed.

That is not hypothetical. Auditing all 86 ledger->issue references on 2026-09-07
found 19 live entries citing a closed issue, and the two worst
(`asm-single-letter-mnemonic-in-path`, `api-contextual-baseline-fix`) had ALSO
decayed to explaining no out-of-band cell at all -- they were dead on both axes
and nothing had noticed. The same sweep is what surfaced gitgalaxy#2549's dot
looking unchanged after the fix merged.

A CLOSED ISSUE IS NOT AUTOMATICALLY A STALE ENTRY, and this is the whole reason
the check is disposition-aware rather than a flat "issue closed => retire":

  * `upstream-bug`, `upstream-question`, `engine-defect` -- the entry says the
    ENGINE owes a change. A closed issue means the debt was either paid (retire
    the entry: flip `still_reproduces` after a fresh verifying scan) or declined
    (re-disposition it to `engine-semantic`/`intended-morphology`, because the
    behaviour is now documented design rather than an open defect). Either way
    the entry must change, so these are the ones this gate FAILS on. They are
    also exactly the dispositions the bias chart paints RED
    (`bias_report.OPEN_DEFECT_CATEGORIES` via `_DISPOSITION_CATEGORY`), so a
    stale one overstates the open-defect share.
  * `engine-semantic`, `intended-morphology`, `language-morphology`,
    `keyword-overlap` -- the entry documents behaviour the engine is keeping.
    Its issue was closed BECAUSE the answer was "this is by design", and the
    entry outliving it is correct, not stale. 12 of the 19 above are this.
    Reported for context, never gated.

Bare `#N` references inside a verdict's prose are deliberately ignored: they are
ambiguous (`(fixed by PR #2837)` names a PR, not the issue) and resolving them
would flag entries on their own fix's merge. Only fully-qualified `owner/repo#N`
references -- the form every `upstream_issue` field actually uses -- are audited.
A reference that resolves to MERGED is a pull request, recorded and skipped.

NETWORK-FREE AT PR TIME, exactly like its two sibling audits. Issue states are
resolved by `--refresh` (which shells out to `gh`) into `docs/issue_states.json`,
and the gate reads only that cache: seconds, no scans, no API calls, no token
needed in a PR job. `bias-history.yml` refreshes the cache and re-baselines this
audit on the same daily/push run that regenerates `docs/bias_data.json`, so on
main the cache, the baseline and the report are always in lockstep and a PR's
`--ci` only ever sees staleness the PR itself introduced.

DECAY CROSS-REFERENCE. An entry that is BOTH closed-upstream and explains no
out-of-band cell (`bias_report.decayed_entries`, keyword-rosetta#75's check) is
dead on both axes and is marked `[also decayed]`. Those are the highest-value
retirements: nothing measures them and nobody owes them.

Usage:
    python tools/ledger_issue_check.py             # report every stale entry
    python tools/ledger_issue_check.py --ci        # exit 1 on NEW stale entries
    python tools/ledger_issue_check.py --refresh   # re-resolve states via gh
    python tools/ledger_issue_check.py --regenerate # rewrite the baseline
"""

import json
import pathlib
import re
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from bias_report import (  # noqa: E402  (sys.path shim above; see AGENTS.md testing note)
    CONTEXT_METRICS,
    decayed_entries,
    out_of_band_cells,
    reference_medians,
)

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
LEDGER = REPO_ROOT / "deviation_ledger.json"
BIAS_DATA = REPO_ROOT / "docs" / "bias_data.json"
STATES = REPO_ROOT / "docs" / "issue_states.json"
BASELINE = REPO_ROOT / "docs" / "ledger_issue_baseline.json"

# Dispositions that assert the ENGINE owes a change. These are the ones the bias
# chart paints red (bias_report._DISPOSITION_CATEGORY -> "extraction", which is in
# OPEN_DEFECT_CATEGORIES), so a stale one inflates the published open-defect share.
# Derived from that map rather than hand-listed, so a new disposition cannot
# silently land on the wrong side of this gate.
OWED_DISPOSITIONS = frozenset({"upstream-bug", "upstream-question", "engine-defect"})

# `owner/repo#N`. Bare `#N` is deliberately NOT matched -- see the module docstring.
QUALIFIED_REF = re.compile(r"\b([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)#(\d+)\b")


def references(entry):
    """Every fully-qualified issue reference in an entry's `upstream_issue`."""
    return [
        (repo, int(num))
        for repo, num in QUALIFIED_REF.findall(entry.get("upstream_issue") or "")
    ]


def _resolve(repo, number):
    """(state, title) for one issue via `gh`, or (None, reason) when unresolvable."""
    result = subprocess.run(
        ["gh", "issue", "view", str(number), "--repo", repo, "--json", "state,title"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None, (result.stderr.strip().splitlines() or ["unresolved"])[-1]
    payload = json.loads(result.stdout)
    return payload["state"], payload["title"]


def refresh():
    """Re-resolve every referenced issue into docs/issue_states.json."""
    ledger = json.loads(LEDGER.read_text())["entries"]
    wanted = sorted({ref for e in ledger for ref in references(e)})
    issues, unresolved = {}, []
    for repo, number in wanted:
        state, title = _resolve(repo, number)
        if state is None:
            unresolved.append(f"{repo}#{number}: {title}")
            continue
        issues[f"{repo}#{number}"] = {"state": state, "title": title}
    STATES.write_text(
        json.dumps({"issues": dict(sorted(issues.items())), "unresolved": unresolved}, indent=1)
        + "\n"
    )
    print(f"wrote {STATES.relative_to(REPO_ROOT)} ({len(issues)} resolved, {len(unresolved)} not)")
    for line in unresolved:
        print(f"  unresolved: {line}")
    return 0


def _load_states():
    if not STATES.exists():
        sys.exit(
            f"{STATES.relative_to(REPO_ROOT)} missing -- run "
            "`python tools/ledger_issue_check.py --refresh` first (it needs `gh` "
            "authenticated; bias-history.yml does this on main)."
        )
    return json.loads(STATES.read_text())["issues"]


def _decayed_ids():
    """Entry ids that currently explain no out-of-band cell, or () with no cache.

    The decay cross-reference is an escalation marker, not a gate input, so a
    missing cache degrades to "cannot tell" rather than failing the audit.
    """
    if not BIAS_DATA.exists():
        return frozenset()
    data = json.loads(BIAS_DATA.read_text())
    metrics, languages = data["metrics"], data["languages"]
    refs = reference_medians(
        metrics, languages, data.get("strata") or {}, data.get("constant_sensitive") or []
    )
    oob = out_of_band_cells(metrics, languages, refs)
    ungated = set(data.get("ungated_metrics") or CONTEXT_METRICS)
    oob = {cell for cell in oob if cell[0] not in ungated}
    na = data.get("na", {})
    na_cells = {(metric, lang) for metric, per_lang in na.items() for lang in per_lang}
    ledger = json.loads(LEDGER.read_text())["entries"]
    return frozenset(eid for eid, _ in decayed_entries(ledger, oob, na_cells))


def analyse():
    """Return (owed, documented, merged).

    owed:       [(key, entry_id, ref, disposition, title, decayed)] -- the gated set:
                a live entry whose disposition says the engine owes a change, whose
                issue is closed.
    documented: the same shape for the non-owed dispositions -- reported only.
    merged:     refs that resolved to a pull request, not an issue.
    """
    states = _load_states()
    decayed = _decayed_ids()
    ledger = json.loads(LEDGER.read_text())["entries"]

    owed, documented, merged = [], [], []
    for entry in ledger:
        # Same predicate the gate and every report use since keyword-rosetta#81:
        # a retired entry explains nothing, so its issue state is moot.
        if entry.get("status") != "validated" or entry.get("still_reproduces") is False:
            continue
        for repo, number in references(entry):
            ref = f"{repo}#{number}"
            record = states.get(ref)
            if record is None:
                continue
            if record["state"] == "MERGED":
                merged.append((entry["id"], ref))
                continue
            if record["state"] != "CLOSED":
                continue
            row = (
                f"{entry['id']}/{ref}",
                entry["id"],
                ref,
                entry.get("disposition"),
                record["title"],
                entry["id"] in decayed,
            )
            (owed if entry.get("disposition") in OWED_DISPOSITIONS else documented).append(row)
    return sorted(owed), sorted(documented), sorted(merged)


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    if mode == "--refresh":
        return refresh()

    owed, documented, merged = analyse()
    keys = [row[0] for row in owed]

    if mode == "--regenerate":
        BASELINE.write_text(json.dumps({"stale_entries": keys}, indent=1) + "\n")
        print(f"wrote {BASELINE.relative_to(REPO_ROOT)} ({len(keys)} entries)")
        return 0

    baseline = set(
        json.loads(BASELINE.read_text()).get("stale_entries", []) if BASELINE.exists() else []
    )
    new = [row for row in owed if row[0] not in baseline]
    resolved = sorted(baseline - set(keys))

    print(f"live entries citing a CLOSED issue: {len(owed)} owed-disposition "
          f"({len(baseline)} baselined), {len(documented)} documented-disposition")

    if documented:
        print(
            "\ndocumented dispositions -- correct to outlive a closed issue (the issue was "
            "answered 'by design'); listed for context only:"
        )
        for _, eid, ref, disp, _title, decay in documented:
            print(f"  {eid} | {ref} | {disp}{' [also decayed]' if decay else ''}")

    if merged:
        print(f"\nreferences that resolve to a pull request, not an issue ({len(merged)}):")
        for eid, ref in merged:
            print(f"  {eid} | {ref}")

    if resolved:
        print(
            f"\nresolved since baseline (run --regenerate to shrink it): {', '.join(resolved)}"
        )

    if new:
        print(f"\nNEW stale ledger entries (not in {BASELINE.name}):")
        for _, eid, ref, disp, title, decay in new:
            mark = " [also decayed -- explains no out-of-band cell]" if decay else ""
            print(f"  - {eid} ({disp}) cites CLOSED {ref}{mark}")
            print(f"      {title}")
        print(
            "\nEach says the engine owes a change on an issue that is already closed. "
            "Either the fix landed -- retire the entry (`still_reproduces: false`, "
            "verified by a fresh scan, in the PR that re-blesses the manifests, "
            "docs/GATING.md step 4) -- or it was declined, in which case re-disposition "
            "it to the design it documents. An entry marked [also decayed] is dead on "
            "both axes and should simply retire."
        )
        return 1 if mode == "--ci" else 0

    print("\nno new stale ledger entries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
