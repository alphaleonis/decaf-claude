#!/usr/bin/env sh
# Verify how skills and agents point at the files they read.
#
# Claude Code does not attach a file named by an `@path.md` line in a SKILL.md or an agent file, so
# a skill or agent reads a bundled file only when its text says to. ${CLAUDE_PLUGIN_ROOT} and
# ${CLAUDE_SKILL_DIR} are substituted before the model sees the text; a relative path does not
# resolve inside an agent, which is not told where its file lives.
#
# Checks, over decaf-*/skills/*/SKILL.md and decaf-*/agents/*.md:
#   1. No `@path.md` reference.
#   2. No relative `../conventions/` or `../../conventions/` path.
#   3. Every ${CLAUDE_PLUGIN_ROOT}/... and ${CLAUDE_SKILL_DIR}/... path names an existing file.
#
# Usage: scripts/check-skill-references.sh   # non-zero exit on any finding

set -eu

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
status=0

report() {
   echo "$1"
   status=1
}

for file in $(find "$ROOT"/decaf-* \( -path '*/skills/*/SKILL.md' -o -path '*/agents/*.md' \) -type f | sort); do
   rel=${file#"$ROOT/"}
   plugin_root="$ROOT/$(echo "$rel" | cut -d/ -f1)"
   skill_dir=$(dirname "$file")

   grep -nE '(^|[[:space:](`])@[^[:space:]`)]*\.md' "$file" | while IFS= read -r hit; do
      echo "AT-REFERENCE: $rel:$hit"
   done | grep . && status=1 || true

   grep -nE '(^|[^A-Za-z_}])(\.\./)+conventions/' "$file" | while IFS= read -r hit; do
      echo "RELATIVE-PATH: $rel:$hit"
   done | grep . && status=1 || true

   for token in $(grep -oE '\$\{CLAUDE_(PLUGIN_ROOT|SKILL_DIR)\}/[A-Za-z0-9_./-]+' "$file" | sort -u); do
      case "$token" in
         '${CLAUDE_PLUGIN_ROOT}'/*) target="$plugin_root/${token#'${CLAUDE_PLUGIN_ROOT}'/}" ;;
         '${CLAUDE_SKILL_DIR}'/*) target="$skill_dir/${token#'${CLAUDE_SKILL_DIR}'/}" ;;
      esac
      target=${target%.}
      [ -f "$target" ] || report "MISSING-FILE: $rel names $token, which does not exist"
   done
done

[ "$status" -eq 0 ] && echo "OK: skill and agent references are read instructions on existing files"
exit "$status"
