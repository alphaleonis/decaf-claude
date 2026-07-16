#!/usr/bin/env bash
# Recompute whole-session tokens (orchestrator + subagents) for every existing run and merge
# them into runs/*/meta.json, then rebuild metrics.csv. Use to backfill runs recorded before
# session-token capture existed. Requires the session transcripts to still be on disk.
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

shopt -s nullglob
for m in "$RUNS_DIR"/*/meta.json; do
  sid="$(jq -r '.session_id // ""' "$m")"
  [ -z "$sid" ] && { echo "  skip $(basename "$(dirname "$m")") — no session_id"; continue; }
  ws="$(bash "$BENCH_DIR/scripts/session_tokens.sh" "$sid")"
  tmp="$(mktemp)"; jq --argjson ws "$ws" '.session_tokens=$ws' "$m" > "$tmp" && mv "$tmp" "$m"
  echo "  $(basename "$(dirname "$m")"): subagents=$(jq -r '.subagents//0' <<<"$ws") ws_output=$(jq -r '.output//"?"' <<<"$ws") ws_total=$(jq -r '.total//"?"' <<<"$ws")"
done
echo
bash "$BENCH_DIR/scripts/rebuild_metrics.sh"
