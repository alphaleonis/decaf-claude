#!/usr/bin/env bash
# Summarize benchmark progress from the manifest.
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

[ -f "$MANIFEST" ] || { echo "No manifest yet. Run /bench-init."; exit 0; }
total="$(wc -l < "$MANIFEST")"
echo "Benchmark: $total cells  |  model=$BENCH_MODEL  |  repeats=$REPEATS"
echo "manifest: $MANIFEST"
echo
echo "Status:"
jq -r .status "$MANIFEST" | sort | uniq -c | sed 's/^/  /'
echo
echo "By tool (done/total):"
for t in $(jq -r '.tool' "$MANIFEST" | sort -u); do
  d="$(jq -r --arg t "$t" 'select(.tool==$t and .status=="done") | .run_id' "$MANIFEST" | wc -l | tr -d ' ')"
  n="$(jq -r --arg t "$t" 'select(.tool==$t) | .run_id' "$MANIFEST" | wc -l | tr -d ' ')"
  printf "  %-26s %s/%s\n" "$t" "$d" "$n"
done
echo
echo "By subject (done/total):"
for s in $(jq -r '.subject_id' "$MANIFEST" | sort -n -u); do
  d="$(jq -r --argjson s "$s" 'select(.subject_id==$s and .status=="done") | .run_id' "$MANIFEST" | wc -l | tr -d ' ')"
  n="$(jq -r --argjson s "$s" 'select(.subject_id==$s) | .run_id' "$MANIFEST" | wc -l | tr -d ' ')"
  lang="$(jq -r --argjson s "$s" 'select(.subject_id==$s) | .lang' "$MANIFEST" | head -1)"
  size="$(jq -r --argjson s "$s" 'select(.subject_id==$s) | .size' "$MANIFEST" | head -1)"
  printf "  %2s %-11s %-7s %s/%s\n" "$s" "$lang" "$size" "$d" "$n"
done
echo
echo "Next pending:"
jq -r 'select(.status=="pending") | .run_id' "$MANIFEST" | head -6 | sed 's/^/  /'
if jq -e 'select(.status=="failed")' "$MANIFEST" >/dev/null 2>&1; then
  echo
  echo "Failed cells (re-run with /bench-run <run_id>):"
  jq -r 'select(.status=="failed") | .run_id' "$MANIFEST" | sed 's/^/  /'
fi
if [ -f "$METRICS_CSV" ]; then
  echo; echo "Metrics: $(( $(wc -l < "$METRICS_CSV") - 1 )) rows -> $METRICS_CSV"
fi
exit 0
