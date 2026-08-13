#!/usr/bin/env bash
# Regenerate results/metrics.csv from every runs/*/meta.json (source of truth).
# Whole-session token columns (ws_*) come from meta.session_tokens; orch_total is the
# orchestrator-only .usage total (diagnostic). cost_usd is the authoritative comparable.
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

# `effort` is empty for cells run before it was pinned (2026-08-10) — those inherited an ambient
# effort from the launching shell and no artifact records which. Empty means unknown, not "none".
cols="run_id,subject_id,lang,size,tool,repeat,model,effort,status,is_error,wall_clock_s,max_subagent_s,duration_api_ms,num_turns,cost_usd,subagents,ws_input,ws_output,ws_cache_creation,ws_cache_read,ws_total,orch_total,findings_lines,session_id,finished_at"
echo "$cols" > "$METRICS_CSV"
shopt -s nullglob
for m in "$RUNS_DIR"/*/meta.json; do
  jq -r '[.run_id,.subject_id,.lang,.size,.tool,.repeat,.model,(.effort // ""),.status,.is_error,
          .wall_clock_s,(.session_tokens.max_subagent_duration_s // ""),.duration_api_ms,.num_turns,.cost_usd,
          (.session_tokens.subagents // ""),(.session_tokens.input // ""),(.session_tokens.output // ""),
          (.session_tokens.cache_creation // ""),(.session_tokens.cache_read // ""),(.session_tokens.total // ""),
          .total_tokens,.findings_lines,.session_id,.finished_at] | @csv' "$m"
done >> "$METRICS_CSV"
echo "metrics: $(( $(wc -l < "$METRICS_CSV") - 1 )) rows -> $METRICS_CSV"
