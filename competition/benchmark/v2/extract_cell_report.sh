#!/usr/bin/env bash
# Recover a cell's COMPLETE review from its transcript (nib dcc-vkeh).
#
# Usage: extract_cell_report.sh <cell-dir>     # writes <cell-dir>/cell-report.md
#
# WHY THIS EXISTS
#
# `run_cell_v2.sh` writes final-output.md from `jq -r '.result'`, which is the session's FINAL
# assistant message and nothing else. That is the whole review only for a tool whose last act is to
# print it. Measured on the comprehensive-review pilot probe: the report was assistant block 5
# (11,605 chars), the session ended with a 3,104-char addendum opening "Everything else in my
# previous report stands unchanged", and final-output.md captured only the addendum. 76% of the
# tool's output — including every original finding — was absent from the file the scorer reads.
#
# Nothing detected it. The file was well-formed, non-empty, and plausible prose, so every guard in
# the pipeline passed. A tool that reports then keeps working would have been scored on a fragment,
# and the bias runs one way: it removes findings, so the tool looks quieter and more precise than it
# is. This is the harness's recurring silent-failure shape (CLAUDE.md) in its most expensive form —
# not "empty vs failed" but "partial vs complete", which is harder to see.
#
# MAIN CHAIN ONLY. Sub-agent sidechains are excluded deliberately: a finding a sub-agent produced but
# the orchestrator never surfaced is not something the reader was shown. That reported-vs-found
# distinction is a scored axis (dcc-c92m), and folding sidechains in here would silently credit every
# tool with its sub-agents' full output.
set -uo pipefail

D="${1:?usage: extract_cell_report.sh <cell-dir>}"
[ -d "$D" ] || { echo "no such cell dir: $D" >&2; exit 2; }

SESSION="$(jq -r '.session_id // empty' "$D/meter.json" 2>/dev/null)"
if [ -z "$SESSION" ]; then
  echo "CANNOT EXTRACT: no session_id in $D/meter.json" >&2
  exit 2
fi

mapfile -t TRANSCRIPTS < <(find "$HOME/.claude/projects" -name "*${SESSION}*.jsonl" 2>/dev/null)
if [ "${#TRANSCRIPTS[@]}" -eq 0 ]; then
  echo "CANNOT EXTRACT: no transcript for session $SESSION" >&2
  exit 2
fi

OUT="$D/cell-report.md"
: > "$OUT"
for t in "${TRANSCRIPTS[@]}"; do
  jq -r 'select(.type=="assistant" and (.isSidechain != true))
         | .message.content[]? | select(.type=="text") | .text' "$t" 2>/dev/null \
    | sed '/^$/N;/^\n$/D' >> "$OUT"
  printf '\n' >> "$OUT"
done

full=$(wc -c < "$OUT" | tr -d ' ')
final=$(wc -c < "$D/final-output.md" 2>/dev/null | tr -d ' '); final="${final:-0}"

if [ "$full" -eq 0 ]; then
  echo "[$(basename "$D")] EXTRACTION EMPTY: transcript held no main-chain assistant text" >&2
  exit 3
fi

# Report the ratio rather than silently preferring one file. A cell where the two agree needs no
# attention; a cell where final-output.md is a fraction of the transcript is the defect above, and it
# has to be visible per cell instead of discovered once and assumed everywhere.
pct=$(( final * 100 / full ))
echo "[$(basename "$D")] cell-report.md ${full}c; final-output.md ${final}c (${pct}% of it)"
if [ "$pct" -lt 80 ]; then
  echo "[$(basename "$D")] NOTE: final-output.md holds only ${pct}% of what the tool printed — score cell-report.md" >&2
fi
