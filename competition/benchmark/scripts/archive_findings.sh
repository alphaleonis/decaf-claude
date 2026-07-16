#!/usr/bin/env bash
# Assemble a complete findings bundle for a run into <findings_dir>, so grading never depends on
# the orchestrator's final message alone:
#   00-final-output.md         — the orchestrator's final result text (same as ../raw_output.md)
#   subagent-NN-<agent>.md     — each subagent's FULL text output (deduped by message id)
# Tool-written report files (ours/tag1) are copied here separately by run_cell.
# Usage: archive_findings.sh <session_id> <findings_dir> <raw_output_path>
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

sid="${1:?session_id}"; fdir="${2:?findings_dir}"; raw="${3:-}"
mkdir -p "$fdir"
[ -n "$raw" ] && [ -f "$raw" ] && cp "$raw" "$fdir/00-final-output.md"

sadir="$(find "$HOME/.claude/projects" -maxdepth 3 -type d -path "*/${sid}/subagents" 2>/dev/null | head -1)"
n=0
if [ -n "$sadir" ]; then
  shopt -s nullglob
  for sf in "$sadir"/*.jsonl; do
    n=$((n+1)); a="$(basename "$sf" .jsonl)"
    { echo "# subagent $a"; echo
      jq -rs '[.[] | select(.type=="assistant")] | group_by(.message.id) | map(.[-1])
              | .[] | .message.content[]? | select(.type=="text") | .text' "$sf" 2>/dev/null
    } > "$fdir/subagent-$(printf '%02d' "$n")-$a.md"
  done
fi
echo "  findings bundle: final-output + $n subagent output(s) -> $fdir"
