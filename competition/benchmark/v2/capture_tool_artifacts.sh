#!/usr/bin/env bash
# Copy a tool's own written artifacts out of the checkout before the next cell destroys them
# (nib dcc-vkeh).
#
# Usage: capture_tool_artifacts.sh <cell-dir> <repo-dir>   # writes <cell-dir>/tool-artifacts/
#
# WHY THIS EXISTS
#
# Several tools write their real report INTO the working tree and print only a summary. decaf's
# presets do exactly this: `.decaf/code-reviews/CODE_REVIEW_<ts>.md` holds every finding, while the
# terminal gets a verdict and the top few. `run_cell_v2.sh` then resets the checkout before the NEXT
# cell (`checkout -f` + `clean -xfd`), so the report is deleted by the following run and the scorer
# never sees it.
#
# Measured on the pilot probes: the `ours-review` cell announced
# `.decaf/code-reviews/CODE_REVIEW_2026-08-11_17-07-31.md` with "2 Critical, 1 Medium, 3 Minor"; the
# three Minor findings existed only in that file, and it was gone before it could be read. Precision
# and trivia ratio are counts over reported findings, so losing the minor ones inflates precision for
# exactly the tools that file a full report — the opposite bias to the `.result` truncation, and
# just as silent.
#
# Generic on purpose: it captures whatever the tool left behind rather than a hard-coded `.decaf`,
# because the next tool to do this will not use that path.
set -uo pipefail

D="${1:?usage: capture_tool_artifacts.sh <cell-dir> <repo-dir>}"
REPO="${2:?usage: capture_tool_artifacts.sh <cell-dir> <repo-dir>}"
DEST="$D/tool-artifacts"
MANIFEST="$D/tool-artifacts.tsv"

# Build output, dependency trees and VCS internals. These are what a cell produces by BUILDING, not
# by reviewing, and they run to gigabytes.
SKIP_RE='(^|/)(\.git|node_modules|vendor|target|dist|obj|bin|artifacts|packages|\.venv|__pycache__|\.gradle|\.nuget)(/|$)'
MAX_BYTES=$((512 * 1024))

mkdir -p "$DEST"
printf 'status\tpath\tbytes\tnote\n' > "$MANIFEST"

if [ ! -d "$REPO/.git" ]; then
  printf 'error\t\t\tno git checkout at %s\n' "$REPO" >> "$MANIFEST"
  echo "[$(basename "$D")] artifact capture: NO CHECKOUT at $REPO" >&2
  exit 2
fi

copied=0; skipped=0; total=0
# -uall lists individual untracked files rather than collapsing a new directory to one entry, which
# is what `.decaf/code-reviews/` would otherwise be.
while IFS= read -r line; do
  [ -z "$line" ] && continue
  path="${line:3}"
  path="${path%\"}"; path="${path#\"}"
  total=$((total + 1))
  if printf '%s' "$path" | grep -qE "$SKIP_RE"; then
    printf 'skipped\t%s\t\tbuild output or dependency tree\n' "$path" >> "$MANIFEST"
    skipped=$((skipped + 1)); continue
  fi
  src="$REPO/$path"
  [ -f "$src" ] || { printf 'skipped\t%s\t\tnot a regular file\n' "$path" >> "$MANIFEST"; skipped=$((skipped+1)); continue; }
  sz=$(wc -c < "$src" | tr -d ' ')
  if [ "$sz" -gt "$MAX_BYTES" ]; then
    printf 'skipped\t%s\t%s\tover %s byte cap\n' "$path" "$sz" "$MAX_BYTES" >> "$MANIFEST"
    skipped=$((skipped + 1)); continue
  fi
  mkdir -p "$DEST/$(dirname "$path")"
  cp -p "$src" "$DEST/$path" && \
    { printf 'copied\t%s\t%s\t\n' "$path" "$sz" >> "$MANIFEST"; copied=$((copied + 1)); } || \
    { printf 'error\t%s\t%s\tcopy failed\n' "$path" "$sz" >> "$MANIFEST"; }
done < <(git -C "$REPO" status --porcelain -uall 2>/dev/null)

# `git status` cannot see a path the SUBJECT repo happens to gitignore, and a tool's report location
# is chosen by the tool, not by the subject. `.decaf/` is the known case (every decaf preset declares
# `.decaf/code-reviews/CODE_REVIEW_*.md` as its findings_file in tools.json). Sweep the declared
# locations directly so a subject whose .gitignore happens to cover one does not silently drop it.
# Add a directory here whenever a tool in tools.json declares a findings_file outside the ones listed.
for known in .decaf; do
  [ -d "$REPO/$known" ] || continue
  while IFS= read -r f; do
    rel="${f#$REPO/}"
    [ -e "$DEST/$rel" ] && continue          # already taken by the status walk
    sz=$(wc -c < "$f" | tr -d ' ')
    total=$((total + 1))
    if [ "$sz" -gt "$MAX_BYTES" ]; then
      printf 'skipped\t%s\t%s\tover %s byte cap\n' "$rel" "$sz" "$MAX_BYTES" >> "$MANIFEST"
      skipped=$((skipped + 1)); continue
    fi
    mkdir -p "$DEST/$(dirname "$rel")"
    cp -p "$f" "$DEST/$rel" && \
      { printf 'copied\t%s\t%s\tgitignored path, swept by name\n' "$rel" "$sz" >> "$MANIFEST"; copied=$((copied + 1)); }
  done < <(find "$REPO/$known" -type f 2>/dev/null)
done

# "Nothing captured" has two very different causes and they must not look alike: a tool that writes
# no artifact is normal, a capture that failed to run is a data loss. The manifest exists either way
# and records which.
echo "[$(basename "$D")] tool artifacts: $copied copied, $skipped skipped, $total changed paths seen"
if [ "$copied" -eq 0 ] && [ "$total" -gt 0 ]; then
  echo "[$(basename "$D")] NOTE: tool changed $total path(s) but none were captured — see $MANIFEST" >&2
fi
exit 0
