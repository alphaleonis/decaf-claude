#!/usr/bin/env bash
# Summarize benchmark progress from the manifest.
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
