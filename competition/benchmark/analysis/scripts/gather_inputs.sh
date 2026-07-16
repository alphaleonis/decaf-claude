#!/usr/bin/env bash
# Gather the analysis inputs for one subject: list its DONE cells, emit costs.json (per-cell cost/
# timing/tokens for the metrics engine), and print the paths the LLM stages need (findings bundles,
# the review diff, the ground truth). Usage: gather_inputs.sh <subject_id>
set -euo pipefail
BENCH_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SID="${1:?usage: gather_inputs.sh <subject_id>}"
PAD="$(printf '%02d' "$SID")"
RUNS="$BENCH_DIR/runs"
FIX="$(ls "$BENCH_DIR/subjects/$PAD-"*.json 2>/dev/null | head -1)"
[ -f "$FIX" ] || { echo "no fixture for subject $SID"; exit 1; }
OUT="$BENCH_DIR/analysis/subject-$PAD"; mkdir -p "$OUT"
merge="$(jq -r .merge_sha "$FIX")"

# costs.json — per-cell cost/timing/tokens from DONE cells of this subject
tmp="$(mktemp)"
for m in "$RUNS"/"${SID}"__*/meta.json; do
  [ -f "$m" ] || continue
  jq -c 'select(.status=="done") | {tool, repeat, cost_usd:(.cost_usd|tonumber),
         wall:.wall_clock_s, ws_output:.session_tokens.output, subagents:.session_tokens.subagents,
         max_subagent_s:.session_tokens.max_subagent_duration_s, session_id, findings_dir:("runs/"+.run_id+"/findings")}' "$m"
done > "$tmp"
jq -s --argjson sid "$SID" --slurpfile fx "$FIX" \
  '{subject_id:$sid, lang:$fx[0].lang, size:$fx[0].size, repo:$fx[0].repo, pr:$fx[0].pr,
    merge_sha:$fx[0].merge_sha, cells:.}' "$tmp" > "$OUT/costs.json"
rm -f "$tmp"

n="$(jq '.cells|length' "$OUT/costs.json")"
echo "subject $SID ($(jq -r .lang "$FIX")/$(jq -r .size "$FIX")) — $(jq -r .repo "$FIX")#$(jq -r .pr "$FIX")"
echo "done cells: $n   ->  $OUT/costs.json"
echo "output dir: $OUT"
echo "ground truth: $FIX  (.ground_truth)"
echo "review diff (FULL PR — canonical, what valid tools reviewed): gh pr diff $(jq -r .pr "$FIX") -R $(jq -r .repo "$FIX")"
echo "  NOTE: do NOT use merge^1..merge for grading — it only equals the full PR for squash-merges."
echo "findings bundles (per cell):"
jq -r '.cells[] | "  \(.tool) r\(.repeat): \(.findings_dir)"' "$OUT/costs.json"
