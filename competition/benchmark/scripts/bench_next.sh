#!/usr/bin/env bash
# Run the next pending cell(s), or a specific one.
# Usage: bench_next.sh [--count N] [--tool <id>] [--subject <id>] [<run_id>]
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

[ -f "$MANIFEST" ] || { echo "No manifest. Run /bench-init first."; exit 1; }

COUNT=1; TOOL=""; SUBJECT=""; EXPLICIT=""
while [ $# -gt 0 ]; do
  case "$1" in
    --count)   COUNT="$2"; shift 2;;
    --tool)    TOOL="$2"; shift 2;;
    --subject) SUBJECT="$2"; shift 2;;
    --*)       echo "unknown flag: $1"; exit 2;;
    *)         EXPLICIT="$1"; shift;;
  esac
done

if [ -n "$EXPLICIT" ]; then
  bash "$BENCH_DIR/scripts/run_cell.sh" "$EXPLICIT"
  exit $?
fi

mapfile -t rids < <(
  jq -r --arg t "$TOOL" --arg s "$SUBJECT" \
    'select(.status=="pending")
     | select($t=="" or .tool==$t)
     | select($s=="" or (.subject_id|tostring)==$s)
     | .run_id' "$MANIFEST" | head -n "$COUNT"
)

if [ "${#rids[@]}" -eq 0 ]; then
  echo "No pending cells match (tool='${TOOL:-any}' subject='${SUBJECT:-any}')."
  exit 0
fi

echo "Running ${#rids[@]} cell(s): ${rids[*]}"
echo
for r in "${rids[@]}"; do
  set +e; bash "$BENCH_DIR/scripts/run_cell.sh" "$r"; rc=$?; set -e
  if [ "$rc" -eq 75 ]; then
    echo
    echo "⛔ Subscription usage/session limit reached — stopping the batch. '$r' and any remaining"
    echo "   cells are left PENDING; just re-run /bench-run after the limit resets to continue."
    exit 0
  fi
  if [ "$rc" -eq 76 ]; then echo "[$r] left PENDING — could not reconstruct full-PR review diff (see stderr)"; echo; continue; fi
  [ "$rc" -ne 0 ] && echo "[$r] run_cell exited $rc (recorded as failed — see runs/$r/stderr.log)"
  echo
done
echo "Done. /bench-status for progress."
