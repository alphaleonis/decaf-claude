#!/usr/bin/env bash
# Recompute whole-session tokens (orchestrator + subagents) for every existing run and merge
# them into runs/*/meta.json, then rebuild metrics.csv. Use to backfill runs recorded before
# session-token capture existed. Requires the session transcripts to still be on disk.
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
