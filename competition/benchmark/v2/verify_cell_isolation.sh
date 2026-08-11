#!/usr/bin/env bash
# Prove, per cell, that it did not read the answers off the filesystem (nib dcc-suz4, found by dcc-3cm6).
#
# Usage: verify_cell_isolation.sh <cell-dir>            # e.g. v2/runs/sveltejs-kit-15685__ours-review__shim-on__r1
#        verify_cell_isolation.sh <cell-dir> --session <session-id>
#
# WHY THIS EXISTS
#
# A cell runs `cd v2/pooled/<subject>/repo` under `--dangerously-skip-permissions`, so it has no path
# gating at all. Three relative paths from that working directory reach scoring ground truth:
#
#   ../threads.json                     this subject's admitted threads, with path:line and body
#   ../../*/threads.json                every other subject's
#   ../../../analysis/*/answer-key.json the anchor keys
#   ../../../runs/*/final-output.md     every earlier cell's output (the v1 dcc-2cxq shape)
#
# `reset_repo()` cleans inside the checkout only, so none of it is in scope. Preventing this needs a
# permission posture or a sandbox — that decision is dcc-suz4. This script is the DETECTION half, and
# it is the same instrument that actually settled the v1 stray-report question: only the transcripts
# record what was read, so the outputs alone could not have answered it.
#
# Exit 0 clean, 1 contaminated, 2 cannot tell (no transcript — which is NOT a pass).
set -uo pipefail

D="${1:?usage: verify_cell_isolation.sh <cell-dir> [--session <id>]}"
SESSION="${3:-}"
[ -d "$D" ] || { echo "no such cell dir: $D" >&2; exit 2; }

# The cell's own session id, recorded by run_cell_v2.sh in meter.json.
if [ -z "$SESSION" ] && [ -f "$D/meter.json" ]; then
  SESSION="$(jq -r '.session_id // empty' "$D/meter.json" 2>/dev/null)"
fi
if [ -z "$SESSION" ]; then
  echo "CANNOT VERIFY: no session id in $D/meter.json and none given with --session." >&2
  echo "  A cell whose transcript cannot be found is UNVERIFIED, not clean." >&2
  exit 2
fi

# Claude Code writes one transcript per session under ~/.claude/projects/<slug>/<session>.jsonl,
# including every sub-agent sidechain. Search by id rather than guessing the project slug.
mapfile -t TRANSCRIPTS < <(find "$HOME/.claude/projects" -name "*${SESSION}*.jsonl" 2>/dev/null)
if [ "${#TRANSCRIPTS[@]}" -eq 0 ]; then
  echo "CANNOT VERIFY: no transcript found for session $SESSION under ~/.claude/projects." >&2
  echo "  A cell whose transcript cannot be found is UNVERIFIED, not clean." >&2
  exit 2
fi

# Paths that are ground truth or another cell's work. Matched as substrings of the transcript, which
# catches both the relative form a cell would type and the absolute form a tool call records.
PATTERNS=(
  'threads\.json'
  'answer-key\.json'
  'fixture\.json'
  'final-output\.md'
  '/v2/analysis/'
  '/v2/runs/'
  '/v2/pooled/[^/]*/(threads|fixture)'
  'HARNESS-REVIEW|GROUND-TRUTH-AUDIT|CANDIDATES\.md|METHODOLOGY'
)

echo "Cell isolation check: $D"
echo "  session:    $SESSION"
echo "  transcripts: ${#TRANSCRIPTS[@]}"
echo

hits=0
for p in "${PATTERNS[@]}"; do
  # grep -c prints 0 and exits 1 on no match; capture rather than let `n || 0` append a second zero.
  c="$(grep -hcE "$p" "${TRANSCRIPTS[@]}" 2>/dev/null | awk '{s+=$1} END{print s+0}')"
  if [ "${c:-0}" != "0" ]; then
    printf '  HIT   %-46s %s line(s)\n' "$p" "$c"
    hits=$((hits + c))
  else
    printf '  clean %-46s\n' "$p"
  fi
done

echo
if [ "$hits" != "0" ]; then
  echo "CONTAMINATED (or a false positive worth reading): $hits transcript lines reference scoring"
  echo "artifacts. Read them before scoring this cell — a mention in a tool RESULT is a read; a"
  echo "mention in the prompt or in a refusal is not."
  echo
  echo "  Context (first 5):"
  grep -hEn "$(IFS='|'; echo "${PATTERNS[*]}")" "${TRANSCRIPTS[@]}" 2>/dev/null \
    | head -5 | cut -c1-200 | sed 's/^/    /'
  exit 1
fi
echo "CLEAN: no transcript reference to any scoring artifact."
