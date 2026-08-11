#!/usr/bin/env bash
# Find pooled-adjudication subject candidates (nibs dcc-ixyy, dcc-2gu2).
#
# Usage: find_candidates.sh <owner/repo> [merged_after] [min_human_threads]
#
# `merged_after` also accepts a range (`2026-06-01..2026-06-30`), which searches that window instead
# of everything since. Use it to beat the 100-result sampling cap on a busy repo: slice the period
# into windows of <100 merged PRs each and the sweep is COMPLETE coverage, not a sample.
#
# Emits TSV: repo#pr, mergedAt, size band, +add/-del, files, raw threads, HUMAN threads, bot share,
# distinct human reviewers, title.
#
# Selection rules it enforces (METHODOLOGY-v2 sections 2 and 5):
#   - merged after the cutoff of the newest roster model AND the judge (both Opus 5, 2026-05)
#   - carries >= min HUMAN review threads, since those are the scored miss detector. The original
#     screen counted raw threads, and raw thread count is now substantially a property of which
#     review bots a repo has installed (dcc-qwt3: one subject passed the >=5 bar with 4 of 5 threads
#     bot-written). A thread author is a bot iff its GraphQL actor __typename is Bot OR its login is
#     in the committed bot list (pooled/bot-authors.json — covers renamed apps the live API can no
#     longer type). A name regex cannot do this: none of the ten known bot logins matches
#     `(?i)bot$|\[bot\]`. A thread whose author is deleted counts as NEITHER human nor bot —
#     conservative for a criterion that admits subjects on human count.
# Sorted by comment volume, because thread count cannot be filtered server-side and comments
# correlate with it. Size bands follow the v1 convention: S <100, M 100-500, L >500 changed lines.
#
# ⚠️ THE DEFAULT IS 2026-06-01, NOT 2026-05-01 (dcc-vvf0). Anthropic publishes no day-level training
# cutoff, so Opus 5's "2026-05" can only be read conservatively: the model may have seen anything up
# to 2026-05-31, and a subject is provably out-of-window only if it merged on 2026-06-01 or later.
# The original 2026-05-01 default admitted five subjects that merged inside May 2026; those are kept
# and flagged (see scoring/vintage.py), but no NEW subject should join them.
#
# ⚠️ SAMPLING CAP, stated because a zero here is not proof of absence: GitHub search returns at most
# 100 results and cannot filter on review-thread count, so this takes the top 100 by COMMENT volume
# as a proxy and filters those. Observed consequences: the 2026-08-10 raw screen got 0 from
# PostHog/posthog at min 5 while a 2026-08-11 rerun got 66 (the top-100-by-comments window shifts),
# and comment-sort systematically disadvantages SMALL PRs, so a zero in the S band is the least
# trustworthy zero this script can produce. For complete coverage of a repo, slice with the range
# form of merged_after until every window holds <100 merged PRs.
#
# AUDITOR tool: uses the real `gh` deliberately. Never run inside a review cell.
set -euo pipefail

REPO="${1:?usage: find_candidates.sh <owner/repo> [merged_after] [min_human_threads]}"
AFTER="${2:-2026-06-01}"
MIN_HUMAN="${3:-5}"

case "$AFTER" in
  *..*) MERGED="merged:$AFTER" ;;
  *)    MERGED="merged:>=$AFTER" ;;
esac

BOTLIST="$(dirname "$0")/pooled/bot-authors.json"
if [ ! -s "$BOTLIST" ]; then
  echo "ERROR: bot list $BOTLIST missing or empty — the human-thread criterion cannot run without" >&2
  echo "it (derive it with derive_bot_authors.py). Refusing to fall back to raw thread counts." >&2
  exit 4
fi
BOTS="$(jq -c '.bots' "$BOTLIST")"

# Fail loudly. A transient GraphQL error silently swallowed by `2>/dev/null` produces zero rows,
# which is indistinguishable from "this repo has no candidates" — observed exactly that on two repos.
resp="$(gh api graphql -f query="
{ search(query: \"repo:$REPO is:pr is:merged $MERGED sort:comments-desc\", type: ISSUE, first: 100) {
    nodes { ... on PullRequest {
      number title mergedAt additions deletions changedFiles
      reviewThreads(first: 1) { totalCount }
      author { login __typename }
    } } } }" 2>&1)"

if ! printf '%s' "$resp" | jq -e '.data.search.nodes' >/dev/null 2>&1; then
  echo "ERROR: $REPO returned no usable search payload — not an empty result:" >&2
  printf '%s\n' "$resp" | head -c 400 >&2; echo >&2
  exit 4
fi

# Phase 1 — cheap pre-filter on the search payload. Raw thread count bounds human thread count from
# above, so raw >= MIN_HUMAN is a correct pre-filter; the human criterion itself needs per-thread
# authors, fetched per candidate in phase 2 only for the survivors.
candidates="$(printf '%s' "$resp" \
| jq -r --argjson min "$MIN_HUMAN" '
  .data.search.nodes[]
  | select(.number != null)
  | select(.reviewThreads.totalCount >= $min)
  # Bot-authored PRs (dependency bumps, release chores) are not review subjects. Actor type catches
  # app accounts the regex cannot; the regex still catches human-typed automation accounts.
  | select(.author.__typename == "Bot" | not)
  | select((.author.login // "") | test("(?i)bot$|\\[bot\\]|renovate|dependabot") | not)
  | select((.additions + .deletions) >= 20)
  | "\(.number)"')"

[ -z "$candidates" ] && exit 0

# Phase 2 — per-candidate thread authors. One query per survivor; a failure here is a hard error
# for the whole run, never a silently skipped row.
OWNER="${REPO%%/*}"; NAME="${REPO##*/}"
while IFS= read -r pr; do
  detail="$(gh api graphql -f query="
  { repository(owner:\"$OWNER\", name:\"$NAME\") { pullRequest(number:$pr) {
      number title mergedAt additions deletions changedFiles
      reviewThreads(first:100) { totalCount nodes {
        comments(first:1) { nodes { author { login __typename } } }
      } } } } }" 2>&1)"
  if ! printf '%s' "$detail" | jq -e '.data.repository.pullRequest' >/dev/null 2>&1; then
    echo "ERROR: thread-author query failed for $REPO#$pr — aborting rather than skipping:" >&2
    printf '%s\n' "$detail" | head -c 400 >&2; echo >&2
    exit 4
  fi
  printf '%s' "$detail" \
  | jq -r --arg repo "$REPO" --argjson min "$MIN_HUMAN" --argjson bots "$BOTS" '
    .data.repository.pullRequest
    | (.reviewThreads.nodes | map(.comments.nodes[0].author)) as $authors
    | ($authors | map(select(. != null)
        | select(.__typename == "Bot" or (.login as $l | $bots | index($l)) != null))) as $bot
    | ($authors | map(select(. != null))
        | map(select(.__typename != "Bot" and ((.login as $l | $bots | index($l)) == null)))) as $hum
    | ($hum | map(.login) | unique) as $reviewers
    | select(($hum | length) >= $min)
    | (.additions + .deletions) as $sz
    | (if $sz < 100 then "S" elif $sz <= 500 then "M" else "L" end) as $band
    | [ "\($repo)#\(.number)", (.mergedAt|.[0:10]), $band, "+\(.additions)/-\(.deletions)",
        "\(.changedFiles)f", "\(.reviewThreads.totalCount)thr",
        "\($hum | length)hum",
        "\(if .reviewThreads.totalCount > 0 then (($bot | length) * 100 / .reviewThreads.totalCount | floor) else 0 end)%bot",
        "\($reviewers | length)rev",
        (.title|.[0:70]) ] | @tsv'
done <<< "$candidates"
