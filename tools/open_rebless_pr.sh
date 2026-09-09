#!/usr/bin/env bash
# tools/open_rebless_pr.sh <gitgalaxy-issue-number> [--gitgalaxy <checkout>] [--dry-run]
#
# Given a merged engine issue number N: confirms squid-protocol/gitgalaxy's
# origin/main actually carries a commit mentioning #N, finds the pushed
# rebless/<N>-* or replant/<N>-* branch in THIS repo, and opens the PR with a
# standard body -- the "what moved" table (each touched manifest's diff against
# main, in the same `file: key old -> new` shape rebless.py --dry-run prints),
# a ledger line naming any deviation_ledger.json ids the branch touched, a
# verification line, and the Cross-repo note AGENTS.md rule 5 requires.
# Automates the step AGENTS.md rule 4 and the rule-contract-audit skill's Phase 4
# both describe by hand once the engine PR has merged (keyword-rosetta#113).
#
# Usage:
#   tools/open_rebless_pr.sh <N>                        # open the PR
#   tools/open_rebless_pr.sh <N> --dry-run               # print the PR, don't open it
#   tools/open_rebless_pr.sh <N> --gitgalaxy <checkout>  # override the engine checkout
#
# Env:
#   GITGALAXY_PATH   sibling gitgalaxy checkout to confirm the commit against
#                    (default: the layout _registry.py assumes)
#
# Requires `gh` authenticated against this repo.

set -euo pipefail

if [ $# -lt 1 ]; then
  echo "usage: open_rebless_pr.sh <gitgalaxy-issue-number> [--gitgalaxy <checkout>] [--dry-run]" >&2
  exit 2
fi
N="$1"
shift
GITGALAXY="${GITGALAXY_PATH:-/srv/storage_16tb/projects/gitgalaxy/v6}"
DRY_RUN=0
while [ $# -gt 0 ]; do
  case "$1" in
    --gitgalaxy) GITGALAXY="$2"; shift 2 ;;
    --dry-run) DRY_RUN=1; shift ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

if [ ! -d "$GITGALAXY" ]; then
  echo "gitgalaxy checkout not found at $GITGALAXY (set GITGALAXY_PATH or --gitgalaxy)" >&2
  exit 1
fi

echo "fetching squid-protocol/gitgalaxy origin/main..." >&2
git -C "$GITGALAXY" fetch -q origin main
ENGINE_SHA="$(git -C "$GITGALAXY" log origin/main -E --grep="#${N}([^0-9]|\$)" --format=%H -1 || true)"
if [ -z "$ENGINE_SHA" ]; then
  echo "engine origin/main carries no commit mentioning #${N} -- has the engine PR merged yet?" >&2
  exit 1
fi
ENGINE_SHORT="$(git -C "$GITGALAXY" rev-parse --short "$ENGINE_SHA")"
echo "engine main carries $ENGINE_SHORT (mentions #${N})" >&2

git fetch -q origin
BRANCH="$(git for-each-ref \
  --format='%(refname:short)' \
  "refs/remotes/origin/rebless/${N}-*" "refs/remotes/origin/rebless/gitgalaxy-${N}-*" \
  "refs/remotes/origin/replant/${N}-*" "refs/remotes/origin/replant/gitgalaxy-${N}-*" \
  | head -1)"
if [ -z "$BRANCH" ]; then
  echo "no pushed rebless/${N}-* or replant/${N}-* branch found on origin" >&2
  exit 1
fi
LOCAL_BRANCH="${BRANCH#origin/}"
echo "found branch $BRANCH" >&2

MERGE_BASE="$(git merge-base origin/main "$BRANCH")"

BODY_FILE="$(mktemp)"
python3 - "$MERGE_BASE" "$BRANCH" "$N" "$ENGINE_SHORT" > "$BODY_FILE" <<'PYEOF'
import json
import subprocess
import sys

base, branch, n, engine_short = sys.argv[1:5]


def show(ref, path):
    res = subprocess.run(["git", "show", f"{ref}:{path}"], capture_output=True, text=True)
    return json.loads(res.stdout) if res.returncode == 0 else None


def changed_files(pattern):
    res = subprocess.run(
        ["git", "diff", "--name-only", base, branch, "--", pattern],
        capture_output=True, text=True, check=True,
    )
    return [f for f in res.stdout.splitlines() if f]


moved_lines, langs = [], []
for path in changed_files("data/*/expected_signals.json"):
    lang = path.split("/")[1]
    langs.append(lang)
    old = show(base, path) or {"files": {}}
    new = show(branch, path) or {"files": {}}
    for fname, new_expect in new.get("files", {}).items():
        old_expect = old.get("files", {}).get(fname, {})
        for key, val in new_expect.items():
            was = old_expect.get(key)
            if was != val:
                moved_lines.append(f"  {path}: {fname}.{key} {'absent' if was is None else was} -> {val}")

ledger_ids = []
if changed_files("deviation_ledger.json"):
    old = show(base, "deviation_ledger.json") or {"entries": []}
    new = show(branch, "deviation_ledger.json") or {"entries": []}
    old_by_id = {e["id"]: e for e in old.get("entries", [])}
    for e in new.get("entries", []):
        if old_by_id.get(e["id"]) != e:
            ledger_ids.append(e["id"])

print(f"Corpus re-bless against engine main, companion to the merged engine PR "
      f"squid-protocol/gitgalaxy#{n} (rosetta:rebless-owed).")
print()
print(f"What moved (engine main `{engine_short}`):")
print()
print("```")
print("\n".join(moved_lines) if moved_lines else "(no manifest cell moved)")
print("```")
if ledger_ids:
    print()
    print("Ledger: " + ", ".join(sorted(set(ledger_ids))))
print()
langs = sorted(set(langs))
print(f"Verification: `tools/verify_language.py` PASS for: {', '.join(langs) if langs else '(none)'}")
print()
print(f"Cross-repo: engine PR squid-protocol/gitgalaxy#{n} merged first (`{engine_short}`); "
      "this re-bless follows against engine main. bias-history.yml regenerates the "
      "chart/cache on merge.")
print(f"__LANGS__={','.join(langs)}")
PYEOF

LANGS_LINE="$(tail -1 "$BODY_FILE")"
LANGS="${LANGS_LINE#__LANGS__=}"
sed -i '$ d' "$BODY_FILE"
TITLE="rebless(${LANGS//,/, }): companion to squid-protocol/gitgalaxy#${N}"

if [ "$DRY_RUN" = "1" ]; then
  echo "--- would open PR: $LOCAL_BRANCH -> main ---"
  echo "title: $TITLE"
  echo
  cat "$BODY_FILE"
  exit 0
fi

gh pr create --base main --head "$LOCAL_BRANCH" --title "$TITLE" --body-file "$BODY_FILE"
