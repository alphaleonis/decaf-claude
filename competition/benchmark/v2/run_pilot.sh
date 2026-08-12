#!/usr/bin/env bash
# Drive a whole subject x tool x repeat matrix through run_cell_v2.sh (nib dcc-vkeh).
#
# Usage:
#   run_pilot.sh <subjects-csv> <tools-csv> [repeats]
#   BENCH_SHIM=off run_pilot.sh dotnet-efcore-34127 ours-review 1
#
# Example:
#   bash v2/run_pilot.sh dotnet-efcore-34127,prometheus-prometheus-18081 \
#        ours-bugs,ours-review,ours-audit,anthropic-code-review,superpowers 2
#
# Cells run STRICTLY SEQUENTIALLY. run_cell_v2.sh resets the subject's checkout before every cell
# (`checkout -f` + `clean -xfd`), so two cells sharing a checkout would destroy each other's working
# tree mid-review. Two subjects have two checkouts and could in principle run side by side; that is
# left out deliberately, because a cell that dies from API contention is indistinguishable in the
# artifacts from a tool that found nothing.
#
# Resumable: a cell whose final-output.md is already non-empty is SKIPPED, so an interrupted run
# continues where it stopped. A cell that ran and produced nothing is NOT skipped — it is re-run,
# because an empty output is a failure to fix, not a result to keep (the harness's recurring
# silent-failure shape). Pass BENCH_FORCE=1 to re-run everything regardless.
set -uo pipefail

SUBJECTS="${1:?usage: run_pilot.sh <subjects-csv> <tools-csv> [repeats]}"
TOOLS="${2:?usage: run_pilot.sh <subjects-csv> <tools-csv> [repeats]}"
REPEATS="${3:-2}"
V2="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SHIM="${BENCH_SHIM:-on}"

LOG="$V2/runs/pilot-$(date -u +%Y%m%dT%H%M%SZ).tsv"
mkdir -p "$V2/runs"
printf 'subject\ttool\trepeat\tstatus\trc\twall_s\tcost_usd\tisolation\tdenied\n' > "$LOG"

total=0; ran=0; skipped=0; failed=0
IFS=',' read -r -a SUBJ_ARR <<< "$SUBJECTS"
IFS=',' read -r -a TOOL_ARR <<< "$TOOLS"

for sid in "${SUBJ_ARR[@]}"; do
  for tool in "${TOOL_ARR[@]}"; do
    for r in $(seq 1 "$REPEATS"); do
      total=$((total+1))
      out="$V2/runs/${sid}__${tool}__shim-${SHIM}__r${r}"
      # Resume: skip a cell that already SUCCEEDED. Non-empty output is not sufficient evidence of
      # that — a cell killed by an API error mid-review writes a short, well-formed prefix and then
      # stops. Measured: the null-arm ours-audit cell hit a 429 spend limit after 533s, wrote 102
      # bytes of final-output.md and 930 of cell-report.md, filed no report artifact, and would have
      # been skipped forever by an emptiness check. `is_error` in meter.json is the authority.
      if [ -z "${BENCH_FORCE:-}" ] && [ -s "$out/final-output.md" ]; then
        cell_err="$(jq -r '.is_error // false' "$out/meter.json" 2>/dev/null)"
        if [ "$cell_err" = "true" ]; then
          echo "[rerun] $sid/$tool r$r — previous attempt errored ($(jq -r '.terminal_reason // "?"' "$out/meter.json" 2>/dev/null)); re-running" >&2
        else
          echo "[skip] $sid/$tool r$r — already has output"
          printf '%s\t%s\t%s\tskipped\t\t\t\t\t\n' "$sid" "$tool" "$r" >> "$LOG"
          skipped=$((skipped+1)); continue
        fi
      fi

      t0=$(date +%s)
      BENCH_REPEAT="$r" bash "$V2/run_cell_v2.sh" "$sid" "$tool"
      rc=$?
      wall=$(( $(date +%s) - t0 ))

      # Every field below is read back from the artifacts rather than from the runner's stdout, so a
      # row in this log is a claim about what is on disk.
      cost="$(jq -r '.total_cost_usd // ""' "$out/meter.json" 2>/dev/null)"
      iso="$(head -1 "$out/isolation.txt" 2>/dev/null | tr -d '\t' | cut -c1-40)"
      denied="$(grep -c 'DENY' "$out/access.log" 2>/dev/null || true)"

      # An API error (429 spend/rate limit, 5xx) leaves rc=1 AND a partial, well-formed report. Name
      # it distinctly from a runner fault: the fix is to wait and re-run, not to debug the harness.
      api_err="$(jq -r '.api_error_status // empty' "$out/meter.json" 2>/dev/null)"
      if [ -n "$api_err" ]; then
        status="api-error-$api_err"; failed=$((failed+1))
        echo "[$sid/$tool] API $api_err — cell truncated mid-review, DO NOT SCORE; re-run when the limit clears" >&2
      elif [ "$rc" -ne 0 ]; then
        status="runner-error"; failed=$((failed+1))
      elif [ ! -s "$out/final-output.md" ]; then
        # Distinguished from a clean run on purpose: the two are indistinguishable downstream, and
        # scoring an empty cell as "found nothing" is how a broken cell becomes a published number.
        status="EMPTY-OUTPUT"; failed=$((failed+1))
      else
        status="ok"; ran=$((ran+1))
      fi
      printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
        "$sid" "$tool" "$r" "$status" "$rc" "$wall" "$cost" "$iso" "$denied" >> "$LOG"
    done
  done
done

echo
echo "=== pilot matrix: $total cells — $ran ok, $skipped skipped, $failed failed"
echo "=== log: $LOG"
if [ "$failed" -gt 0 ]; then
  echo "=== failed cells (do not score these):"
  awk -F'\t' 'NR>1 && ($4=="runner-error" || $4=="EMPTY-OUTPUT")' "$LOG"
fi
sum="$(awk -F'\t' 'NR>1 && $7!="" {s+=$7} END {printf "%.2f", s}' "$LOG")"
echo "=== cost this invocation (excludes skipped cells): \$$sum"
exit $(( failed > 0 ? 1 : 0 ))
