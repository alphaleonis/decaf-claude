#!/usr/bin/env bash
# Find pooled-adjudication subject candidates (nib dcc-ixyy).
#
# Usage: find_candidates.sh <owner/repo> [merged_after] [min_threads]
#
# Emits TSV: repo#pr, mergedAt, size band, +add/-del, files, review threads, title.
#
# Selection rules it enforces (METHODOLOGY-v2 sections 3 and 6):
#   - merged after the cutoff of the newest roster model AND the judge (both Opus 5, 2026-05)
#   - carries real human review threads, since those are a scored target (the miss detector)
# Sorted by comment volume, because thread count cannot be filtered server-side and comments
# correlate with it. Size bands follow the v1 convention: S <100, M 100-500, L >500 changed lines.
#
# AUDITOR tool: uses the real `gh` deliberately. Never run inside a review cell.
set -euo pipefail

REPO="${1:?usage: find_candidates.sh <owner/repo> [merged_after] [min_threads]}"
AFTER="${2:-2026-05-01}"
MIN_THREADS="${3:-5}"

# Fail loudly. A transient GraphQL error silently swallowed by `2>/dev/null` produces zero rows,
# which is indistinguishable from "this repo has no candidates" — observed exactly that on two repos.
resp="$(gh api graphql -f query="
{ search(query: \"repo:$REPO is:pr is:merged merged:>=$AFTER sort:comments-desc\", type: ISSUE, first: 100) {
    nodes { ... on PullRequest {
      number title mergedAt additions deletions changedFiles
      reviewThreads(first: 1) { totalCount }
      author { login }
    } } } }" 2>&1)"

if ! printf '%s' "$resp" | jq -e '.data.search.nodes' >/dev/null 2>&1; then
  echo "ERROR: $REPO returned no usable search payload — not an empty result:" >&2
  printf '%s\n' "$resp" | head -c 400 >&2; echo >&2
  exit 4
fi

printf '%s' "$resp" \
| jq -r --arg repo "$REPO" --argjson min "$MIN_THREADS" '
  .data.search.nodes[]
  | select(.number != null)
  | select(.reviewThreads.totalCount >= $min)
  # Bot-authored PRs (dependency bumps, release chores) are not review subjects.
  | select((.author.login // "") | test("(?i)bot$|\\[bot\\]|renovate|dependabot") | not)
  | (.additions + .deletions) as $sz
  | select($sz >= 20)
  | (if $sz < 100 then "S" elif $sz <= 500 then "M" else "L" end) as $band
  | [ "\($repo)#\(.number)", (.mergedAt|.[0:10]), $band, "+\(.additions)/-\(.deletions)",
      "\(.changedFiles)f", "\(.reviewThreads.totalCount)thr", (.title|.[0:70]) ] | @tsv'
