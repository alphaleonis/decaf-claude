#!/usr/bin/env bash
# METHODOLOGY-v2 §4b (build the fixture + verify airtight) for a pooled fixture directory.
# ONE fetch only: a second fetch of the base re-shallows the repo and discards the deep history.
set -euo pipefail
D="${1:?usage: build_pooled_repo.sh <v2/pooled/DIR>}"
REPO=$(jq -r '.repo' "$D/fixture.json"); CP=$(jq -r '.checkpoint.sha' "$D/fixture.json")
BASE=$(jq -r '.checkpoint.base' "$D/fixture.json"); PR=$(jq -r '.pr' "$D/fixture.json")
R="$D/repo"
rm -rf "$R"; git init -q "$R"
git -C "$R" remote add origin "https://github.com/$REPO"
git -C "$R" fetch -q --depth 500 origin "$CP"      # ONE fetch — never also fetch BASE
git -C "$R" checkout -q -f "$CP"
git -C "$R" clean -qxfd
git -C "$R" remote remove origin
depth=$(git -C "$R" rev-list --count HEAD)
dirty=$(git -C "$R" status --porcelain | wc -l | tr -d ' ')
remotes=$(git -C "$R" remote -v | wc -l | tr -d ' ')
# Suppressions justified: `grep -r` exits 1 when it finds nothing, and finding nothing is the GOOD
# outcome here — under `pipefail` the `|| true` is what keeps the script alive to report it. The
# result is printed either way, so "clean" is a measurement rather than a silence.
leak=$(grep -rlE "pull/$PR|#$PR\b" "$R" 2>/dev/null | head -1 || true)
# Suppression justified: a branchless yes/NO probe. Both branches are reported in the line below,
# so an absent merge base is visible rather than swallowed.
base_ok=$(git -C "$R" cat-file -e "${BASE}^{commit}" 2>/dev/null && echo yes || echo NO)
printf '  %-30s depth=%-6s dirty=%-3s remotes=%-3s base_present=%-4s %s\n' \
  "$REPO#$PR" "$depth" "$dirty" "$remotes" "$base_ok" "$([ -n "$leak" ] && echo "LEAK:$leak" || echo clean)"
