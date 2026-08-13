#!/usr/bin/env bash
# Assemble a complete findings bundle for a run into <findings_dir>, so grading never depends on
# the orchestrator's final message alone:
#   00-final-output.md         — the orchestrator's final result text (same as ../raw_output.md)
#   subagent-NN-<agent>.md     — each subagent's FULL text output (deduped by message id)
# Tool-written report files (ours/tag1) are copied here separately by run_cell.
# Usage: archive_findings.sh <session_id> <findings_dir> <raw_output_path>
# The v1 dataset is void on four independent counts (see v1-archive/README.md) and has been archived.
# Every v1 entry point refuses by default: a banner on a command is not a control, and 11 of these 12
# scripts had none until dcc-j21q. v2 runs through v2/run_cell_v2.sh and the bench-* commands.
if [ "${BENCH_V1_ALLOW:-0}" != "1" ]; then
  cat >&2 <<'EOF'
REFUSING: the v1 benchmark is retired and its data is archived under v1-archive/.

  Its results are void (contamination, GitHub leak, unaudited ground truth, unpinned effort) and
  the two leaks point in opposite directions, so no v1 number is citable in any form.

  For v2:      /bench-status, /bench-run, /bench-analyze, /bench-synthesize
  Background:  competition/benchmark/v2/README.md, METHODOLOGY-v2.md, milestone dcc-ho2w

  To run v1 anyway (reproducing a leak, regenerating evidence): BENCH_V1_ALLOW=1
EOF
  exit 3
fi

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
