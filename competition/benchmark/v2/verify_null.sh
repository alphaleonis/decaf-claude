#!/usr/bin/env bash
# Verify a candidate NULL subject: a substantive change with no KNOWN defect (nib dcc-mjj5).
#
# Usage: verify_null.sh <owner/repo> <pr> [as_of_date]
#
# The null arm gives pooled precision an absolute scale. Pooled adjudication scores a tool against
# what the tools collectively found, so it cannot say how much of that output is noise in the first
# place. Running the roster on a change with nothing to find answers exactly that.
#
# "No KNOWN defect" is the honest framing — never "no defect". These checks bound the claim:
#   1. no revert PR cross-referenced from it
#   2. no regression issue cross-referenced from it
#   3. no later commit touching the SAME FILES with a fix-shaped message  <- the substantive one
#   4. soak time recorded, because a defect needs time to surface
#
# Check 3 is verified against the files' later history rather than assumed, because a change can ship
# a defect that nobody ever linked back to the PR that caused it.
#
# AUDITOR tool: uses the real `gh` deliberately. Never run inside a review cell.
set -uo pipefail

REPO="${1:?usage: verify_null.sh <owner/repo> <pr> [as_of]}"
PR="${2:?usage: verify_null.sh <owner/repo> <pr> [as_of]}"
AS_OF="${3:-$(date -u +%F)}"
OWNER="${REPO%%/*}"; NAME="${REPO##*/}"

J="$(gh api graphql -f query="
{ repository(owner:\"$OWNER\", name:\"$NAME\") { pullRequest(number:$PR) {
  title mergedAt additions deletions changedFiles mergeCommit{oid}
  timelineItems(first:100, itemTypes:[CROSS_REFERENCED_EVENT]) {
    nodes { ... on CrossReferencedEvent { source {
      ... on PullRequest { number title state } ... on Issue { number title state } } } } }
  files(first:100){nodes{path}} } } }" 2>&1)"

# Print the payload rather than discarding it, the way find_candidates.sh already does: a transient
# GraphQL error swallowed by `2>/dev/null` is indistinguishable from a PR that does not exist.
if ! printf '%s' "$J" | jq -e '.data.repository.pullRequest' >/dev/null 2>&1; then
  echo "ERROR: could not fetch $REPO#$PR — this is a FAILED QUERY, not a verdict:" >&2
  printf '%s\n' "$J" | head -c 400 >&2; echo >&2
  exit 4
fi

merged="$(printf '%s' "$J" | jq -r '.data.repository.pullRequest.mergedAt // empty')"
title="$(printf '%s' "$J" | jq -r '.data.repository.pullRequest.title')"
add="$(printf '%s' "$J" | jq -r '.data.repository.pullRequest.additions')"
del="$(printf '%s' "$J" | jq -r '.data.repository.pullRequest.deletions')"
sha="$(printf '%s' "$J" | jq -r '.data.repository.pullRequest.mergeCommit.oid // empty')"
mapfile -t files < <(printf '%s' "$J" | jq -r '.data.repository.pullRequest.files.nodes[].path')

soak=$(( ( $(date -u -d "$AS_OF" +%s) - $(date -u -d "${merged:0:10}" +%s) ) / 86400 ))

# 1 + 2: revert / regression cross-references.
# NOT suppressed: an empty result here means "no revert links this PR", which is a NULL-OK vote. If
# the filter itself errors, the same emptiness votes the same way — so a jq failure would silently
# admit a subject that should have been rejected. Fail the run instead.
if ! suspicious="$(printf '%s' "$J" | jq -r '
  [.data.repository.pullRequest.timelineItems.nodes[] | select(.source != null) | .source
   | select(.title | test("(?i)revert|regress|hotfix|breaks|broken|bug from|caused by"))
   | "#\(.number) \(.title)"] | .[]')"; then
  echo "ERROR: cross-reference filter failed on $REPO#$PR — cannot conclude nullness" >&2; exit 4
fi

# 3: later commits touching the same files with a fix-shaped message. This is the check that can
# actually falsify nullness, so it queries the API rather than trusting the absence of a link.
# `since` is INCLUSIVE, so the PR's own merge commit matches and every subject flags itself —
# observed on immich#27788, whose only "later fix" was its own commit. Start one second after, and
# drop anything still naming this PR.
#
# It also FAILS CLOSED. `2>/dev/null` on the commits query turned a rate-limited or 404 response into
# an empty result, which reads as "no later fix found" and votes NULL-OK — the permissive direction,
# on the one check that can falsify the arm's premise (dcc-3cm6).
# The cap was 12, which is smaller than a size-matched null subject. On immich#28204 (33 files) it
# probed 12 and adjudicated a subset: lifting it surfaced 5 further files carrying later fix-shaped
# commits, including the one production file the PR meaningfully changes. A cap below the corpus's
# own file counts is a coverage gap dressed as a result (dcc-nvrt). It exists now only to bound a
# pathological diff, and the run still reports anything it did not reach.
FILE_CAP="${NULL_FILE_CAP:-100}"
fixes=""; probed=0; skipped=0; errors=0; excluded=0
if [ -n "$merged" ]; then
  after="$(date -u -d "$merged +1 second" +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || echo "$merged")"
  for f in "${files[@]:0:$FILE_CAP}"; do
    # Generated and shared-config files are touched by every later change, so a hit there says
    # nothing about THIS PR. They are excluded from the signal, not from the diff.
    case "$f" in
      *_gen.*|*.generated.*|*/generated/*|*defaults.ini|*/docs/*|*.md|*.csv) excluded=$((excluded+1)); continue ;;
      *.lock|*lock.json|*-lock.yaml|package.json|*/package.json) excluded=$((excluded+1)); continue ;;  # dependency churn
      */i18n/*|*/locales/*|*.toml|.github/*|*/.github/*) excluded=$((excluded+1)); continue ;;          # translations, CI, tool config
    esac
    msgs="$(gh api "repos/$REPO/commits?path=$f&since=$after&per_page=100" \
             --jq '.[] | .commit.message | split("\n")[0]' 2>&1)"; rc=$?
    if [ $rc -ne 0 ]; then
      errors=$((errors + 1))
      echo "  QUERY FAILED for $f: $(printf '%s' "$msgs" | head -c 160)" >&2
      continue
    fi
    probed=$((probed + 1))
    # grep exits 1 when nothing matches, which here is the good outcome, not an error.
    hits="$(printf '%s\n' "$msgs" \
           | grep -iE '^(fix|revert|hotfix)|regress|broken|breaks' \
           | grep -v "#$PR)" | head -2 || true)"
    [ -n "$hits" ] && fixes="$fixes\n    $f:\n$(printf '%s' "$hits" | sed 's/^/      /')"
  done
  skipped=$(( ${#files[@]} > FILE_CAP ? ${#files[@]} - FILE_CAP : 0 ))
fi

verdict="NULL-OK"
[ -n "$suspicious" ] && verdict="REJECT (revert/regression cross-reference)"
[ -n "$fixes" ] && verdict="REVIEW (later fix-shaped commits on the same files — check whether they touch the same LINES)"
# A check that could not run is not a check that passed.
[ "$errors" != "0" ] && verdict="INCONCLUSIVE ($errors file queries failed — rerun before trusting nullness)"
[ "$soak" -lt 30 ] && verdict="$verdict [soak ${soak}d — thin]"

cat <<EOF
$REPO#$PR — $title
  merged:     ${merged:0:10}   soak: ${soak}d as of $AS_OF
  size:       +$add/-$del across $(printf '%s' "$J" | jq -r '.data.repository.pullRequest.changedFiles') files
  merge sha:  ${sha:0:12}
  revert/regression cross-refs: ${suspicious:-none}
  file probe:  $probed of ${#files[@]} files queried, $excluded excluded as shared|generated$([ "$skipped" != "0" ] && printf ' (%s BEYOND THE CAP OF %s — NOT CHECKED)' "$skipped" "$FILE_CAP")$([ "$errors" != "0" ] && printf ', %s QUERIES FAILED' "$errors")
  later fix-shaped commits on the same files:$(if [ -n "$fixes" ]; then printf '%b' "$fixes"; else echo " none"; fi)
  VERDICT: $verdict
EOF
