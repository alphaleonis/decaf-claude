#!/usr/bin/env bash
# Regenerate results/metrics.csv from every runs/*/meta.json (source of truth).
# Whole-session token columns (ws_*) come from meta.session_tokens; orch_total is the
# orchestrator-only .usage total (diagnostic). cost_usd is the authoritative comparable.
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

cols="run_id,subject_id,lang,size,tool,repeat,model,status,is_error,wall_clock_s,max_subagent_s,duration_api_ms,num_turns,cost_usd,subagents,ws_input,ws_output,ws_cache_creation,ws_cache_read,ws_total,orch_total,findings_lines,session_id,finished_at"
echo "$cols" > "$METRICS_CSV"
shopt -s nullglob
for m in "$RUNS_DIR"/*/meta.json; do
  jq -r '[.run_id,.subject_id,.lang,.size,.tool,.repeat,.model,.status,.is_error,
          .wall_clock_s,(.session_tokens.max_subagent_duration_s // ""),.duration_api_ms,.num_turns,.cost_usd,
          (.session_tokens.subagents // ""),(.session_tokens.input // ""),(.session_tokens.output // ""),
          (.session_tokens.cache_creation // ""),(.session_tokens.cache_read // ""),(.session_tokens.total // ""),
          .total_tokens,.findings_lines,.session_id,.finished_at] | @csv' "$m"
done >> "$METRICS_CSV"
echo "metrics: $(( $(wc -l < "$METRICS_CSV") - 1 )) rows -> $METRICS_CSV"
