#!/usr/bin/env bash
# Install a plugin from this working tree as a SEPARATE, side-by-side dev plugin.
#
#   scripts/install-dev-plugin.sh [plugin] [dev-name]
#   scripts/install-dev-plugin.sh decaf-quality decaf-quality-dev     # the default
#
# Why not just install from the marketplace: the marketplace is a GitHub clone, so testing a change
# means pushing, pulling the clone, and reinstalling — and that replaces the plugin you use
# everywhere else with an unverified one. A skills-dir plugin under a different name loads
# alongside the stable one, so both are callable in the same session and can be compared directly.
#
# Two things make this more than a copy:
#   1. `cp -rL` dereferences the conventions symlinks. They point outside the plugin root, and a
#      plugin can only read files inside its own directory.
#   2. Every `<plugin>:` reference inside the copy is rewritten to `<dev-name>:`. The skill
#      dispatches its agents by fully-qualified name, so without this the dev orchestrator would
#      run the STABLE plugin's agents — a chimera that measures neither version.
#
# Loads next session as <dev-name>@skills-dir. Remove with: rm -rf ~/.claude/skills/<dev-name>
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PLUGIN="${1:-decaf-quality}"
DEV="${2:-${PLUGIN}-dev}"
SRC="$REPO/$PLUGIN"
DEST="$HOME/.claude/skills/$DEV"

[ -d "$SRC" ] || { echo "no such plugin in this repo: $SRC"; exit 1; }
[ -f "$SRC/.claude-plugin/plugin.json" ] || { echo "$PLUGIN has no plugin.json"; exit 1; }

branch="$(git -C "$REPO" rev-parse --abbrev-ref HEAD 2>/dev/null || echo '?')"
sha="$(git -C "$REPO" rev-parse --short HEAD 2>/dev/null || echo '?')"
dirty=""; git -C "$REPO" diff --quiet 2>/dev/null || dirty=" +uncommitted"

rm -rf "$DEST"
mkdir -p "$HOME/.claude/skills"
cp -rL "$SRC" "$DEST"

python3 - "$DEST" "$PLUGIN" "$DEV" "$branch" "$sha$dirty" <<'PY'
import json, pathlib, sys
dest, plugin, dev, branch, sha = sys.argv[1:6]
d = pathlib.Path(dest)

mf = d / ".claude-plugin" / "plugin.json"
m = json.load(open(mf))
m["name"] = dev
base = m["description"].split("] ", 1)[-1]
m["description"] = f"[DEV COPY of {plugin} — {branch}@{sha}] {base}"
json.dump(m, open(mf, "w"), indent=3)

refs = files = 0
for p in d.rglob("*.md"):
    s = p.read_text()
    n = s.count(f"{plugin}:")
    if n:
        p.write_text(s.replace(f"{plugin}:", f"{dev}:"))
        refs += n; files += 1

leftover = sum(p.read_text().count(f"{plugin}:") for p in d.rglob("*.md"))
dangling = [str(p) for p in d.rglob("*") if p.is_symlink()]
assert leftover == 0, f"{leftover} unrewritten {plugin}: references remain"
assert not dangling, f"symlinks survived the copy: {dangling[:3]}"

print(f"  {dev}  <-  {plugin} @ {branch}@{sha}")
print(f"  rewrote {refs} namespace references across {files} files")
print(f"  skills {len(list((d/'skills').glob('*/SKILL.md')))}  agents {len(list((d/'agents').glob('*.md')))}  conventions {len(list((d/'conventions').glob('*')))}")
PY

echo
echo "Installed to $DEST"
echo "Loads as ${DEV}@skills-dir on the NEXT session — verify with: claude plugin details $DEV"
echo "It is a snapshot, not a link: re-run this after any edit to $PLUGIN/."
