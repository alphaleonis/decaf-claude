#!/usr/bin/env bash
# Run one benchmark v2 review cell under time-boxed tool access.
#
# Usage: run_cell_v2.sh <subject_id> <tool_id>
#
# Differences from v1 run_cell.sh:
#   - reviews a CHECKPOINT diff range from the local fixture, never a PR number
#   - `gh` is shimmed to refuse anything created after the checkpoint (v2/shim/gh)
#   - WebFetch/WebSearch are disallowed; `docs-at` gives date-pinned documentation instead
#   - every external access is logged for the post-run leak audit
set -euo pipefail

SID="${1:?usage: run_cell_v2.sh <subject_id> <tool_id>}"
TOOL="${2:?usage: run_cell_v2.sh <subject_id> <tool_id>}"
V2="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BENCH="$(dirname "$V2")"
source "$BENCH/config.env"

FIX="$(ls "$V2"/subjects/$(printf %02d "$SID")-*.json)"
REPO="$V2/repos/$SID"
CP="$(jq -r '.checkpoint.sha'  "$FIX")"
BASE="$(jq -r '.checkpoint.base' "$FIX")"
DATE="$(jq -r '.checkpoint.date' "$FIX" | cut -c1-10)"

SHIM="${BENCH_SHIM:-on}"; REP="${BENCH_REPEAT:-1}"
OUT="$V2/runs/${SID}__${TOOL}__shim-${SHIM}__r${REP}"; rm -rf "$OUT"; mkdir -p "$OUT"

# Return the fixture checkout to the checkpoint before every cell. Review tools write artifacts into
# the working tree — decaf's skills drop reports in `.decaf/code-reviews/`, and their
# recurring-findings cross-check reads that directory back — so a cell that inherits the previous
# cell's tree can harvest its findings. This is the v1 failure (dcc-2cxq) and it must not recur here.
# The fixture has no remote by construction, so the checkpoint must already be a local object.
reset_repo() {
  if ! git -C "$REPO" cat-file -e "${CP}^{commit}" 2>/dev/null; then
    echo "[$SID/$TOOL] REFUSING: checkpoint $CP absent from $REPO — rebuild the fixture" >&2; exit 78
  fi
  git -C "$REPO" checkout -q -f "$CP"
  git -C "$REPO" clean -qxfd
  local dirty; dirty="$(git -C "$REPO" status --porcelain | wc -l | tr -d ' ')"
  if [ "$dirty" != "0" ]; then
    echo "[$SID/$TOOL] REFUSING: $REPO still dirty ($dirty entries) after reset — contamination risk" >&2
    git -C "$REPO" status --porcelain >&2; exit 77
  fi
}
reset_repo

export BENCH_CHECKPOINT_DATE="$DATE"
export BENCH_REAL_GH="$(command -v gh)"
export BENCH_ACCESS_LOG="$OUT/access.log"
: > "$BENCH_ACCESS_LOG"
# BENCH_SHIM=off runs the SAME prompt with unrestricted gh — the control arm. It still goes through
# a pass-through LOGGER, so the control arm is measurable; without it the arm produces no access log
# at all and "0 accesses" is an artifact rather than a measurement.
export BENCH_ENFORCING_SHIM="$V2/shim/gh"

# Build toolchains. Sourced BEFORE the shim dir is prepended, so the time-boxed `gh` still wins.
# Without this a cell inherits a non-interactive PATH where go and dotnet are absent even though both
# are installed, and every cell silently degrades to static-analysis-only review (dcc-fhp1).
. "$V2/toolchain.sh"

if [ "$SHIM" = "on" ]; then export PATH="$V2/shim:$PATH"; else export PATH="$V2/shim-log:$PATH"; fi

# Record what the cell could actually do, so a run without a toolchain is identifiable rather than
# quietly weaker evidence than one with.
bash "$V2/detect_build.sh" "$(dirname "$REPO")" > "$OUT/build-capability.json" 2>/dev/null ||   echo '{"error":"detection failed"}' > "$OUT/build-capability.json"

REPO_SLUG="$(jq -r '.repo' "$FIX")"; PRNUM="$(jq -r '.pr' "$FIX")"

case "$TOOL" in
  ours-review) INVOKE="Use the Skill tool to run /decaf-quality-dev:code-review with arguments: review --report" ;;
  ours-bugs)   INVOKE="Use the Skill tool to run /decaf-quality-dev:code-review with arguments: bugs --report" ;;
  ours-audit)  INVOKE="Use the Skill tool to run /decaf-quality-dev:code-review with arguments: audit --report" ;;
  anthropic-code-review)
    INVOKE="Use the Skill tool to run \`code-review:code-review\` — the plugin-qualified command from code-review@claude-plugins-official. It is NOT \`decaf-quality:code-review\`: a different tool ships a skill of the same bare name, so never invoke a bare /code-review, and abort rather than substituting anything else if the qualified skill does not resolve.

Review pull request #$PRNUM of the GitHub repository $REPO_SLUG. Do NOT pass --comment and do NOT post anything to GitHub — output the review to the terminal only. Fetch the PR with gh. Print every finding you would post, with file:line references." ;;
  *) echo "unknown tool: $TOOL" >&2; exit 2 ;;
esac

PROMPT="$INVOKE

Review the code changes in this repository from commit $BASE to commit $CP (i.e. \`git diff $BASE $CP\`). This is a proposed change under review; it has NOT been merged.

REVIEW-ONLY: do not post anything anywhere, and do not attempt to modify the code.

Environment notes:
- The repository is checked out locally at the change under review. Full git history is available — use \`git log\`, \`git blame\`, and \`git show\` freely to understand prior work.
- Network documentation lookup is available through \`docs-at <url>\`, which returns the page as it existed at the time of this change. Use it for library and framework API reference. WebFetch and WebSearch are unavailable.
- \`gh\` is restricted to information that existed at the time of this change.
- A build toolchain IS available (node, go, dotnet, python, cargo as the project requires). You may
  build the project and run its tests to confirm or refute a finding. Restore dependencies with the
  project's frozen/locked command (\`pnpm install --frozen-lockfile\`, \`go mod download\` under
  \`GOFLAGS=-mod=readonly\`, \`dotnet restore\`, \`uv sync --frozen\`) so no dependency resolves to a
  version published after this change. Note that full test suites can take many minutes; prefer the
  tests covering the changed code.

Report every finding with a file:line reference and a clear statement of what is wrong."

echo "[$SID/$TOOL shim=$SHIM r$REP] checkpoint ${CP:0:12}, date $DATE, model $BENCH_MODEL effort $BENCH_EFFORT"
t0=$(date +%s)
set +e
( cd "$REPO" && claude -p "$PROMPT" \
    --model "$BENCH_MODEL" --effort "$BENCH_EFFORT" \
    --disallowedTools WebFetch WebSearch \
    $PERM_FLAGS --output-format json ) > "$OUT/meter.json" 2> "$OUT/stderr.log"
rc=$?
set -e
t1=$(date +%s)

jq -r '.result // empty' "$OUT/meter.json" > "$OUT/final-output.md" 2>/dev/null || true
cost=$(jq -r '.total_cost_usd // "?"' "$OUT/meter.json" 2>/dev/null)
echo "[$SID/$TOOL] rc=$rc wall=$((t1-t0))s cost=\$$cost -> $OUT"
if [ "$SHIM" = "on" ]; then
  echo "[$SID/$TOOL] external accesses: $(wc -l < "$BENCH_ACCESS_LOG") ($(grep -c 'DENY' "$BENCH_ACCESS_LOG" || true) denied)"
else
  echo "[$SID/$TOOL] external accesses: $(wc -l < "$BENCH_ACCESS_LOG") (unrestricted; $(grep -c 'would=\[DENY' "$BENCH_ACCESS_LOG" || true) would have been DENIED by the shim)"
fi
