#!/usr/bin/env bash
# Gather the evidence needed to audit one v1 subject's ground truth (nib dcc-5xad).
#
# Usage: audit_subject.sh <subject_id>
#
# Answers, for the merged range the v1 fixture reviewed:
#   - which files the FIX/REVERT PR touches, and whether they appear in the reviewed diff
#   - the fix's own diff, so its shape can be compared to what the ground truth claims
#   - the PR's review threads and cross-references
#
# This is an AUDITOR tool: it uses the real `gh` deliberately. The point of a retrospective key is
# that the key-builder sees everything the world eventually learned. Never run it inside a cell.
set -euo pipefail

SID="${1:?usage: audit_subject.sh <subject_id>}"
V2="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BENCH="$(dirname "$V2")"
FIX_JSON="$(ls "$BENCH"/subjects/$(printf %02d "$SID")-*.json)"

REPO=$(jq -r '.repo' "$FIX_JSON")
PR=$(jq -r '.pr' "$FIX_JSON")
BASE=$(jq -r '.base_ref' "$FIX_JSON")
MERGE=$(jq -r '.merge_sha' "$FIX_JSON")
FIXPR_URL=$(jq -r '.ground_truth.revert_pr // .ground_truth.fixing_pr // empty' "$FIX_JSON")
FIXPR=$(basename "${FIXPR_URL:-}")

OUT="$V2/analysis/subject-$(printf %02d "$SID")/audit"
mkdir -p "$OUT"

echo "== subject $SID: $REPO#$PR  (fix: #${FIXPR:-none}) =="

# Files in the reviewed range (what a v1 reviewer actually saw).
# Suppressions in this script are justified by what it collects: an AUDIT EVIDENCE BUNDLE for a
# subject that may legitimately have no fix PR, no revert and no linked issue. Absence IS the
# finding here, and the verdicts drawn from these files are written up by hand in
# GROUND-TRUTH-AUDIT.md, where a missing artifact is visible as a missing file.
gh api "repos/$REPO/pulls/$PR/files" --paginate --jq '.[].filename' 2>/dev/null | sort -u > "$OUT/reviewed-files.txt"
echo "reviewed range: $(wc -l < "$OUT/reviewed-files.txt") files"

if [ -n "$FIXPR" ]; then
  gh api "repos/$REPO/pulls/$FIXPR/files" --paginate \
    --jq '.[] | "\(.filename)\t+\(.additions)/-\(.deletions)"' 2>/dev/null > "$OUT/fix-files.txt" || true
  echo "fix PR:         $(wc -l < "$OUT/fix-files.txt") files"

  # The presence test: does the fix touch anything the reviewer was shown?
  cut -f1 "$OUT/fix-files.txt" | sort -u > "$OUT/.fixnames"
  comm -12 "$OUT/reviewed-files.txt" "$OUT/.fixnames" > "$OUT/overlap.txt"
  echo
  echo "-- OVERLAP (fix files that were in the reviewed diff): $(wc -l < "$OUT/overlap.txt") --"
  cat "$OUT/overlap.txt"
  echo
  echo "-- fix-only files (NOT shown to the reviewer) --"
  comm -13 "$OUT/reviewed-files.txt" "$OUT/.fixnames"
  rm -f "$OUT/.fixnames"

  gh pr view "$FIXPR" -R "$REPO" --json title,body,mergedAt \
    --jq '"TITLE: \(.title)\nMERGED: \(.mergedAt)\n\nBODY:\n\(.body)"' > "$OUT/fix-pr.txt" 2>/dev/null || true
  gh pr diff "$FIXPR" -R "$REPO" > "$OUT/fix.diff" 2>/dev/null || true
  echo
  echo "-- fix diff size: $(wc -l < "$OUT/fix.diff") lines -> $OUT/fix.diff --"
fi

# Review threads + cross-references on the ORIGINAL pr (key candidate sources, Step 5).
gh api graphql -f query="
{ repository(owner:\"${REPO%%/*}\", name:\"${REPO##*/}\") { pullRequest(number:$PR) {
  createdAt mergedAt
  reviewThreads(first:100) { nodes { isResolved isOutdated path line
    comments(first:5){nodes{author{login} createdAt bodyText}} } }
  timelineItems(first:100, itemTypes:[CROSS_REFERENCED_EVENT]) {
    nodes { ... on CrossReferencedEvent { source {
      ... on PullRequest { number title } ... on Issue { number title } } } } } } } }" \
  > "$OUT/pr-context.json" 2>/dev/null || true

if [ -s "$OUT/pr-context.json" ]; then
  echo
  echo "-- threads by author (human vs bot) --"
  jq -r '[.data.repository.pullRequest.reviewThreads.nodes[]
          | .comments.nodes[0].author.login] | group_by(.) | map({(.[0]): length}) | add // {}' "$OUT/pr-context.json"
  echo "-- cross-references: $(jq '[.data.repository.pullRequest.timelineItems.nodes[]|select(.source!=null)]|length' "$OUT/pr-context.json") --"
fi

echo
echo "evidence -> $OUT"
