#!/usr/bin/env bash
# Run one benchmark v2 review cell under time-boxed tool access.
#
# Usage: run_cell_v2.sh <subject_id> <tool_id>
#
# Differences from v1 run_cell.sh:
#   - reviews a CHECKPOINT diff range from the local fixture, never a PR number
#   - `gh` is shimmed to refuse anything created after the checkpoint (v2/shim/gh)
#   - WebFetch/WebSearch are disallowed; `docs-at` gives date-pinned documentation instead
#   - every external access is logged for the post-run leak audit
set -euo pipefail

SID="${1:?usage: run_cell_v2.sh <subject_id> <tool_id>}"
TOOL="${2:?usage: run_cell_v2.sh <subject_id> <tool_id>}"
V2="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BENCH="$(dirname "$V2")"
source "$BENCH/config.env"

FIX="$(ls "$V2"/subjects/$(printf %02d "$SID")-*.json)"
REPO="$V2/repos/$SID"
CP="$(jq -r '.checkpoint.sha'  "$FIX")"
BASE="$(jq -r '.checkpoint.base' "$FIX")"
DATE="$(jq -r '.checkpoint.date' "$FIX" | cut -c1-10)"

OUT="$V2/runs/${SID}__${TOOL}"; rm -rf "$OUT"; mkdir -p "$OUT"

export BENCH_CHECKPOINT_DATE="$DATE"
export BENCH_REAL_GH="$(command -v gh)"
export BENCH_ACCESS_LOG="$OUT/access.log"
: > "$BENCH_ACCESS_LOG"
export PATH="$V2/shim:$PATH"

REPO_SLUG="$(jq -r '.repo' "$FIX")"; PRNUM="$(jq -r '.pr' "$FIX")"

case "$TOOL" in
  ours-review) INVOKE="Use the Skill tool to run /decaf-quality-dev:code-review with arguments: review --report" ;;
  ours-bugs)   INVOKE="Use the Skill tool to run /decaf-quality-dev:code-review with arguments: bugs --report" ;;
  ours-audit)  INVOKE="Use the Skill tool to run /decaf-quality-dev:code-review with arguments: audit --report" ;;
  anthropic-code-review)
    INVOKE="Use the Skill tool to run \`code-review:code-review\` — the plugin-qualified command from code-review@claude-plugins-official. It is NOT \`decaf-quality:code-review\`: a different tool ships a skill of the same bare name, so never invoke a bare /code-review, and abort rather than substituting anything else if the qualified skill does not resolve.

This is pull request #$PRNUM of $REPO_SLUG. The repository is checked out locally at the exact commit under review, and the local checkout is AUTHORITATIVE — use \`git diff\` against it rather than fetching the diff remotely. Do NOT pass --comment and do NOT post anything to GitHub. Print every finding you would post, with file:line references." ;;
  *) echo "unknown tool: $TOOL" >&2; exit 2 ;;
esac

PROMPT="$INVOKE

Review the code changes in this repository from commit $BASE to commit $CP (i.e. \`git diff $BASE $CP\`). This is a proposed change under review; it has NOT been merged.

REVIEW-ONLY: do not post anything anywhere, and do not attempt to modify the code.

Environment notes:
- The repository is checked out locally at the change under review. Full git history is available — use \`git log\`, \`git blame\`, and \`git show\` freely to understand prior work.
- Network documentation lookup is available through \`docs-at <url>\`, which returns the page as it existed at the time of this change. Use it for library and framework API reference. WebFetch and WebSearch are unavailable.
- \`gh\` is restricted to information that existed at the time of this change.

Report every finding with a file:line reference and a clear statement of what is wrong."

echo "[$SID/$TOOL] checkpoint ${CP:0:12} (base ${BASE:0:12}), date $DATE, model $BENCH_MODEL effort $BENCH_EFFORT"
t0=$(date +%s)
set +e
( cd "$REPO" && claude -p "$PROMPT" \
    --model "$BENCH_MODEL" --effort "$BENCH_EFFORT" \
    --disallowedTools WebFetch WebSearch \
    $PERM_FLAGS --output-format json ) > "$OUT/meter.json" 2> "$OUT/stderr.log"
rc=$?
set -e
t1=$(date +%s)

jq -r '.result // empty' "$OUT/meter.json" > "$OUT/final-output.md" 2>/dev/null || true
cost=$(jq -r '.total_cost_usd // "?"' "$OUT/meter.json" 2>/dev/null)
echo "[$SID/$TOOL] rc=$rc wall=$((t1-t0))s cost=\$$cost -> $OUT"
echo "[$SID/$TOOL] external accesses: $(wc -l < "$BENCH_ACCESS_LOG") ($(grep -c DENY "$BENCH_ACCESS_LOG" || true) denied)"
