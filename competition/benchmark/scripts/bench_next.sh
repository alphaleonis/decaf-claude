#!/usr/bin/env bash
# Run the next pending cell(s), or a specific one.
# Usage: bench_next.sh [--count N] [--tool <id>] [--subject <id>] [<run_id>]
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

# The v1 dataset is void on four independent counts (see v1-archive/README.md) and has been archived.
# Running another v1 cell appends to a dataset nothing may be cited from, so refuse by default rather
# than let a stray /bench-run quietly resume it. v2 cells run through v2/run_cell_v2.sh.
if [ "${BENCH_V1_ALLOW:-0}" != "1" ]; then
  cat >&2 <<'EOF'
REFUSING: the v1 benchmark is retired and its data is archived under v1-archive/.

  Its results are void (contamination, GitHub leak, unaudited ground truth, unpinned effort) and
  the two leaks point in opposite directions, so no v1 number is citable in any form.

  For v2:      bash v2/run_cell_v2.sh <subject_id> <tool_id>
  Background:  competition/benchmark/v2/README.md, METHODOLOGY-v2.md, milestone dcc-ho2w

  To re-run v1 anyway (reproducing a leak, regenerating evidence): BENCH_V1_ALLOW=1
EOF
  exit 3
fi

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
  if [ "$rc" -eq 77 ]; then echo "[$r] left PENDING — checkout could not be reset to pristine (see stderr)"; echo; continue; fi
  [ "$rc" -ne 0 ] && echo "[$r] run_cell exited $rc (recorded as failed — see runs/$r/stderr.log)"
  echo
done
echo "Done. /bench-status for progress."
