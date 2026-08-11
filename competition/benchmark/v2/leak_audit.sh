#!/usr/bin/env bash
# Report which leak channels were instrumented for a cell, and what they saw (nib dcc-wzbe).
#
# Usage: leak_audit.sh <cell-dir>
#
# The point is coverage, not just counts. Output-grepping was shown to UNDERCOUNT leaks — a cell read
# two post-checkpoint comments and cited neither, so it scored clean — and any channel without its own
# log has the same blind spot. So this prints every channel's STATUS, including the ones that are
# unmeasured, rather than only summing the ones that happen to be logged.
set -uo pipefail

D="${1:?usage: leak_audit.sh <cell-dir>}"
LOG="$D/access.log"
[ -f "$LOG" ] || { echo "no access.log in $D" >&2; exit 2; }

# grep -c PRINTS 0 and EXITS 1 on no match, so `|| echo 0` appends a second zero and every count
# renders as "0\n0". Capture the output and default only if it is genuinely empty. This is the same
# empty-versus-failed confusion that has now bitten five times in this harness (dcc-3cm6).
n() { local c; c="$(grep -c "$1" "$LOG" 2>/dev/null)"; printf '%s' "${c:-0}"; }

echo "Leak audit: $D"
echo
printf '  %-16s %-11s %s\n' CHANNEL STATUS DETAIL
printf '  %-16s %-11s %s\n' "gh"      "shimmed"  "$(n '	gh	') calls, $(awk -F'\t' '$2=="gh" && $3=="DENY"' "$LOG" | wc -l | tr -d ' ') denied"
printf '  %-16s %-11s %s\n' "curl"    "shimmed"  "$(n '	curl	') calls, $(awk -F'\t' '$2=="curl" && $3=="DENY"' "$LOG" | wc -l | tr -d ' ') denied (GitHub hosts)"
printf '  %-16s %-11s %s\n' "wget"    "shimmed"  "$(n '	wget	') calls, $(awk -F'\t' '$2=="wget" && $3=="DENY"' "$LOG" | wc -l | tr -d ' ') denied (GitHub hosts)"
# docs-at's MISS and ERROR are different facts and are counted separately. A transport failure that
# reads as "no snapshot exists" silently tells a cell its subject has no documentation, and the cell
# is then weaker evidence than one that could look things up — the same identifiable-vs-quietly-
# degraded requirement the build toolchain has (dcc-3cm6).
printf '  %-16s %-11s %s\n' "docs-at" "shimmed"  "$(n '	docs-at	') calls, snapshot date enforced; $(n '	docs-at	MISS') no-capture, $(n '	docs-at	ERROR') TRANSPORT FAILURES (cell degraded, not refused)"
printf '  %-16s %-11s %s\n' "WebFetch" "denied"  "--disallowedTools (harness built-in; not PATH-shimmable)"
printf '  %-16s %-11s %s\n' "WebSearch" "denied" "--disallowedTools"
printf '  %-16s %-11s %s\n' "MCP" "denied"       "--strict-mcp-config with an empty config: the tools do not exist in-cell"
printf '  %-16s %-11s %s\n' "pkg registry" "logged" "via the curl/wget shims; restore is frozen so versions cannot postdate the checkpoint"
printf '  %-16s %-11s %s\n' "git remote" "UNMEASURED" "the fixture has no remote, but nothing stops a cell adding one back"
printf '  %-16s %-11s %s\n' "local fs" "hooked" "$(n '	fs	') path checks, $(awk -F'\t' '$2=="fs" && $3=="DENY"' "$LOG" | wc -l | tr -d ' ') denied — PreToolUse guard, enforced under bypassPermissions (dcc-suz4)"
printf '  %-16s %-11s %s\n' "memorization" "UNMEASURED" "unfalsifiable by construction; bounded only by subject vintage (section 5)"

echo
echo "  Channels a cell could still use that nothing here records:"
echo "    - a network client other than curl/wget (python urllib, node fetch, a language HTTP lib)"
echo "    - a package manager's own transport, which does not go through the curl shim"
echo "    - git itself: \`git remote add o https://github.com/O/R && git fetch o\` reaches the merged"
echo "      state over git's own transport, which the curl shim never sees"
echo "      (the filesystem is no longer on this list: the PreToolUse guard denies any path inside"
echo "      the benchmark tree but outside the cell's own checkout, and verify_cell_isolation.sh"
echo "      re-checks the transcript afterwards — prevention plus proof, not one or the other)"
echo "  Neither is denied, because cells need real network for restore. Both are bounded by the"
echo "  frozen-lockfile rule, and neither is a plausible path to THIS PR's review threads — but"
echo "  they are unmeasured, and that is stated rather than implied."

deny="$(awk -F'\t' '$3=="DENY"' "$LOG" | wc -l | tr -d ' ')"
if [ "$deny" != "0" ]; then
  echo
  echo "  DENIED attempts (what the cell tried to reach):"
  awk -F'\t' '$3=="DENY"' "$LOG" | sed 's/^/    /'
fi

would="$(n 'would=\[DENY')"
if [ "$would" != "0" ]; then
  echo
  echo "  CONTROL ARM — calls the enforcing shim would have denied:"
  grep 'would=\[DENY' "$LOG" | sed 's/^/    /'
fi
