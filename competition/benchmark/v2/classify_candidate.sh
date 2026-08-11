#!/usr/bin/env bash
# Classify a candidate PR by application type from its changed paths (nib dcc-ixyy).
#
# Usage: classify_candidate.sh <owner/repo> <pr>
# Emits: repo#pr <TAB> type <TAB> frontend-files/backend-files <TAB> top dirs
#
# Types follow the METHODOLOGY-v2 corpus axis:
#   app-ui        frontend/client only
#   contract      BOTH client and server — the highest-value row; the defect lives in the mismatch
#   backend       server/API only, in an application repo
#   library       framework or library internals (whole-repo property)
#
# AUDITOR tool: uses the real `gh` deliberately. Never run inside a review cell.
set -euo pipefail

REPO="${1:?usage: classify_candidate.sh <owner/repo> <pr>}"
PR="${2:?usage: classify_candidate.sh <owner/repo> <pr>}"

# Repos whose entire content is library/framework internals — no client/server split to detect.
case "$REPO" in
  dotnet/aspnetcore|dotnet/efcore|prometheus/prometheus|sveltejs/kit|rust-lang/rust|tokio-rs/tokio)
    LIBRARY=1 ;;
  *) LIBRARY=0 ;;
esac

# Suppression justified: the very next line turns an empty result into a hard error, so a failed
# query cannot pass as "this PR has no files".
files="$(gh api "repos/$REPO/pulls/$PR/files" --paginate --jq '.[].filename' 2>/dev/null || true)"
if [ -z "$files" ]; then echo "ERROR: no files for $REPO#$PR" >&2; exit 4; fi

# Exclude generated/vendored noise from the signal, not from the diff itself.
# Suppression justified: `grep -v` exits 1 when it filters everything out, which is a legitimate
# result (an all-generated PR) and is handled by the fallback on the next line.
sig="$(printf '%s\n' "$files" | grep -vE '(^|/)(node_modules|vendor|dist|build)/|\.(lock|snap|min\.js)$|package-lock\.json|yarn\.lock|go\.sum' || true)"
[ -z "$sig" ] && sig="$files"

fe=$(printf '%s\n' "$sig" | grep -cE '(^|/)(webapp|frontend|web|client|ui|public/app|src/components|mobile)/|\.(tsx|jsx|svelte|vue|scss|css)$' || true)
be=$(printf '%s\n' "$sig" | grep -cE '(^|/)(server|backend|api|pkg|cmd|internal|posthog|ee)/|\.(go|py|cs|rb|java)$' || true)

if [ "$LIBRARY" = "1" ]; then
  type="library"
elif [ "$fe" -gt 0 ] && [ "$be" -gt 0 ]; then
  type="contract"
elif [ "$fe" -gt 0 ]; then
  type="app-ui"
elif [ "$be" -gt 0 ]; then
  type="backend"
else
  type="unclear"
fi

dirs="$(printf '%s\n' "$sig" | awk -F/ 'NF>1{print $1"/"$2} NF==1{print $1}' | sort | uniq -c | sort -rn | head -3 \
        | awk '{printf "%s(%s) ", $2, $1}')"
printf '%s#%s\t%s\tfe=%s/be=%s\t%s\n' "$REPO" "$PR" "$type" "$fe" "$be" "$dirs"
