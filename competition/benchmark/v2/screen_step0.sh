#!/usr/bin/env bash
# Step 0 feasibility screen (nib dcc-595v): does the "revert names a mechanism" pattern exist
# outside infrastructure projects?
#
# Usage: screen_step0.sh <owner/repo> [limit]
#
# Emits one TSV row per merged revert PR: number, mergedAt, body-length-after-boilerplate,
# whether it links an issue, whether it contains causal language, and the first line of the body.
# Classification is NOT automated — the signals narrow what has to be read by hand.
#
# AUDITOR tool: uses the real `gh` deliberately. Never run inside a review cell.
set -euo pipefail

REPO="${1:?usage: screen_step0.sh <owner/repo> [limit]}"
LIMIT="${2:-25}"

# Fail loudly on a TRANSPORT failure, like find_candidates.sh: `2>/dev/null` here turned an auth or
# network error into zero rows, which reads as "this repo has no reverts" — the conclusion the screen
# exists to reach.
#
# LIMIT OF THIS GUARD, stated rather than implied: `gh pr list --search` returns `[]` with exit 0 for
# a repository that does not exist, so a typo'd or renamed repo is genuinely indistinguishable from
# one with no reverts. The zero-row notice below is the only signal available; check the slug.
if ! resp="$(gh pr list -R "$REPO" --search 'revert in:title' --state merged --limit "$LIMIT" \
              --json number,title,body,mergedAt 2>&1)" || ! printf '%s' "$resp" | jq -e 'type=="array"' >/dev/null 2>&1; then
  echo "ERROR: $REPO returned no usable PR list — not an empty result:" >&2
  printf '%s\n' "$resp" | head -c 400 >&2; echo >&2
  exit 4
fi

if [ "$(printf '%s' "$resp" | jq 'length')" = "0" ]; then
  echo "NOTE: $REPO matched no merged 'revert in:title' PRs. Confirm the slug is right — a repo that" >&2
  echo "      does not exist returns the same empty list as one with no reverts." >&2
fi

printf '%s' "$resp" \
| jq -r --arg repo "$REPO" '
  .[] |
  # Strip the HTML-comment PR templates that dominate some repos, and the boilerplate
  # "This reverts commit <sha>." line, which carries no mechanism by itself.
  (.body // ""
    | gsub("<!--[\\s\\S]*?-->"; "")
    | gsub("This reverts commit [0-9a-f]{7,40}\\.?"; "")
    | gsub("Reverts [^\\n]*"; "")
    | gsub("^\\s+|\\s+$"; "")) as $b |
  ($b | gsub("\\s+"; " ") | length) as $len |
  (if ($b | test("#[0-9]+|https://github.com/[^ ]+/(issues|pull)/[0-9]+")) then "link" else "-" end) as $link |
  (if ($b | test("(?i)because|caused by|causes|due to|root cause|regress|breaks|fails when|results in|leads to")) then "causal" else "-" end) as $why |
  [$repo, (.number|tostring), (.mergedAt|.[0:10]), ($len|tostring), $link, $why,
   ($b | gsub("\\s+"; " ") | .[0:150])] | @tsv'
