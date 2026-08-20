#!/usr/bin/env bash
# Prove that a GRADING or ANNOTATION pass did not read what it was supposed to be blind to (dcc-hsy8).
#
# Usage: verify_grading_isolation.sh <subject-dir> --session <id> [--session <id> ...]
#        verify_grading_isolation.sh <subject-dir> --precheck
#
# The mirror of verify_cell_isolation.sh, pointed the other way. That script asks whether a REVIEWER
# read the answers; this asks whether a JUDGE read the tools' work, or an ANNOTATOR read the result
# its verdict decides. Both blinds were being held by convention, and both have already slipped:
#
#   - A 90,902-byte `ours-audit` report sat in the PostHog-posthog-55149 checkout while both blind
#     graders worked there, because reset_repo() cleans BEFORE a cell and the last cell of a matrix
#     is never followed by one. Pass 1 disclosed that it did not open it; pass 2 never mentioned it.
#     Four more subjects were found in the same state on 2026-08-20. The blind held by luck.
#   - A matchability annotator disclosed reading `pooled/<subject>/THREAD-AXIS-NOTE.md`, which states
#     that no tool matched either of that subject's two human threads — while deciding whether those
#     threads were matchable. The hand-written forbidden list named the JSON artifacts and missed
#     every prose write-up that quotes them.
#
# So the list here is a PATTERN over prose as well as data, and `--precheck` refuses to start a pass
# in a dirty checkout rather than trusting the pass not to look.
#
# Exit 0 clean, 1 contaminated, 2 cannot tell (no transcript — which is NOT a pass).
set -uo pipefail

D="${1:?usage: verify_grading_isolation.sh <subject-dir> --session <id> | --precheck}"
shift
[ -d "$D" ] || { echo "no such subject dir: $D" >&2; exit 2; }

SESSIONS=(); PRECHECK=0
while [ $# -gt 0 ]; do
  case "$1" in
    --session) SESSIONS+=("${2:?--session needs an id}"); shift 2 ;;
    --precheck) PRECHECK=1; shift ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

# ---- precheck: nothing a grader could read may be lying in the checkout ------------------------
if [ "$PRECHECK" = "1" ]; then
  R="$D/repo"
  [ -d "$R/.git" ] || { echo "no checkout at $R — rebuild the fixture first" >&2; exit 2; }
  dirty="$(git -C "$R" status --porcelain)"
  if [ -n "$dirty" ]; then
    echo "REFUSING to grade: $D/repo is dirty. A grader working in this tree can read whatever a"
    echo "previous cell left behind — one arm's complete finding set, in the case this check exists"
    echo "for. Clean it first:  git -C $R clean -xfd && git -C $R reset --hard"
    echo
    printf '%s\n' "$dirty" | sed 's/^/    /'
    exit 1
  fi
  echo "CLEAN: $D/repo has nothing a grading pass could read that it should not."
  exit 0
fi

if [ "${#SESSIONS[@]}" -eq 0 ]; then
  echo "give at least one --session, or use --precheck" >&2; exit 2
fi

TRANSCRIPTS=()
for s in "${SESSIONS[@]}"; do
  mapfile -t -O "${#TRANSCRIPTS[@]}" TRANSCRIPTS < <(find "$HOME/.claude/projects" -name "*${s}*.jsonl" 2>/dev/null)
done
if [ "${#TRANSCRIPTS[@]}" -eq 0 ]; then
  echo "CANNOT VERIFY: no transcript found for ${SESSIONS[*]} under ~/.claude/projects." >&2
  echo "  A pass whose transcript cannot be found is UNVERIFIED, not clean." >&2
  exit 2
fi

# What a grader or annotator must not have read. Three classes, and the third is the one the
# hand-written list kept missing: PROSE that quotes the other two.
PATTERNS=(
  # the tools' own output
  'CODE_REVIEW_|\.decaf/|code-reviews/'
  'final-output\.md|cell-report\.md|/v2/runs/'
  'findings\.json|clusters\.json|extract/'
  # the result the pass is deciding
  'analysis\.json|metrics\.json'
  'verdicts-pass[0-9]|calibration-'
  # prose that quotes either — the class the enumerated list missed
  'THREAD-AXIS|TUNING-SIGNALS|PILOT-RESULTS|PRELIMINARY-COMPARISON|OURS-BUGS|SINGLE-SEAT'
  'RESULTS\.md|-RESULTS|GRADING-INTEGRITY'
  # tool identity, which every blind stage must not see
  'ours-bugs|ours-review|ours-audit|superpowers|anthropic-code-review|comprehensive-review|pr-review-toolkit'
)

echo "Grading isolation check: $D"
echo "  sessions:    ${SESSIONS[*]}"
echo "  transcripts: ${#TRANSCRIPTS[@]}"
echo

hits=0
for p in "${PATTERNS[@]}"; do
  # grep -c prints 0 and exits 1 on no match; sum rather than let the failure append a second zero.
  c="$(grep -hcE "$p" "${TRANSCRIPTS[@]}" 2>/dev/null | awk '{s+=$1} END{print s+0}')"
  if [ "${c:-0}" != "0" ]; then
    printf '  HIT   %-60s %s line(s)\n' "$p" "$c"
    hits=$((hits + c))
  else
    printf '  clean %-60s\n' "$p"
  fi
done

echo
if [ "$hits" != "0" ]; then
  echo "CONTAMINATED (or a false positive worth reading): $hits transcript lines reference tool"
  echo "output, the result being decided, or a write-up quoting either. Read them before trusting"
  echo "this pass — a mention in a tool RESULT is a read; a mention in the prompt is not, and a"
  echo "pass that says it declined to open a file is disclosing, not leaking."
  echo
  echo "  Context (first 8):"
  grep -hEn "$(IFS='|'; echo "${PATTERNS[*]}")" "${TRANSCRIPTS[@]}" 2>/dev/null \
    | head -8 | cut -c1-200 | sed 's/^/    /'
  exit 1
fi
echo "CLEAN: no transcript reference to tool output, the pending result, or a write-up quoting them."
