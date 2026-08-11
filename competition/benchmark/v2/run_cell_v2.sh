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

# Any subject kind — pooled, null or anchor. Hard-coding the anchor layout here meant the runner
# could not address a single one of the 12 pooled subjects the pilot is for (dcc-3cm6).
source "$V2/fixture_lib.sh"
resolve_subject "$SID"
FIX="$FIXTURE"; REPO="$REPO_DIR"; CP="$SUBJ_CP"; BASE="$SUBJ_BASE"; DATE="$SUBJ_DATE"

SHIM="${BENCH_SHIM:-on}"; REP="${BENCH_REPEAT:-1}"
OUT="$V2/runs/${SUBJ_ID}__${TOOL}__shim-${SHIM}__r${REP}"; rm -rf "$OUT"; mkdir -p "$OUT"

# Return the fixture checkout to the checkpoint before every cell. Review tools write artifacts into
# the working tree — decaf's skills drop reports in `.decaf/code-reviews/`, and their
# recurring-findings cross-check reads that directory back — so a cell that inherits the previous
# cell's tree can harvest its findings. This is the v1 failure (dcc-2cxq) and it must not recur here.
# The fixture has no remote by construction, so the checkpoint must already be a local object.
reset_repo() {
  if ! git -C "$REPO" cat-file -e "${CP}^{commit}" 2>/dev/null; then
    echo "[$SUBJ_ID/$TOOL] REFUSING: checkpoint $CP absent from $REPO — rebuild the fixture" >&2; exit 78
  fi
  git -C "$REPO" checkout -q -f "$CP"
  git -C "$REPO" clean -qxfd

  # Review tools create git worktrees OUTSIDE the checkout, and nothing above can see them. The
  # superpowers probe built the base commit in `/tmp/review-base` to diff behavior against HEAD and
  # left it registered in `.git/worktrees` and live on disk — `status` does not report it, `clean
  # -xfd` cannot reach it, and the filesystem hook guards `competition/benchmark/` only. That is
  # cross-cell state in a channel no control covered: the next cell inherits whatever the last one
  # left, which is the dcc-2cxq failure arriving through a new door. Remove them, loudly.
  local main_wt wt strays=0
  main_wt="$(cd "$REPO" && pwd -P)"
  git -C "$REPO" worktree prune 2>/dev/null || true
  while read -r wt; do
    [ -z "$wt" ] && continue
    [ "$wt" = "$main_wt" ] && continue
    echo "[$SUBJ_ID/$TOOL] removing worktree left by an earlier cell: $wt" >&2
    git -C "$REPO" worktree remove --force "$wt" 2>/dev/null || rm -rf "$wt"
    strays=$((strays + 1))
  done < <(git -C "$REPO" worktree list --porcelain 2>/dev/null | awk '/^worktree /{print $2}')
  git -C "$REPO" worktree prune 2>/dev/null || true
  local left; left="$(git -C "$REPO" worktree list --porcelain 2>/dev/null | grep -c '^worktree ' || true)"
  if [ "${left:-1}" != "1" ]; then
    echo "[$SUBJ_ID/$TOOL] REFUSING: $((left - 1)) worktree(s) still registered after cleanup" >&2
    git -C "$REPO" worktree list >&2; exit 79
  fi
  [ "$strays" -gt 0 ] && echo "[$SUBJ_ID/$TOOL] cleaned $strays stray worktree(s) before this cell" >&2

  local dirty; dirty="$(git -C "$REPO" status --porcelain | wc -l | tr -d ' ')"
  if [ "$dirty" != "0" ]; then
    echo "[$SUBJ_ID/$TOOL] REFUSING: $REPO still dirty ($dirty entries) after reset — contamination risk" >&2
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
export BENCH_REAL_CURL="$(command -v curl)"
export BENCH_REAL_WGET="$(command -v wget)"

# Build toolchains. Sourced BEFORE the shim dir is prepended, so the time-boxed `gh` still wins.
# Without this a cell inherits a non-interactive PATH where go and dotnet are absent even though both
# are installed, and every cell silently degrades to static-analysis-only review (dcc-fhp1).
. "$V2/toolchain.sh"

if [ "$SHIM" = "on" ]; then export PATH="$V2/shim:$PATH"; else export PATH="$V2/shim-log:$PATH"; fi

# Filesystem isolation. The shims cover the NETWORK; this covers the local tree, where this subject's
# threads.json (the thread axis's answer key), the anchor keys and every earlier cell's output sit a
# few relative paths from the checkout. A PreToolUse hook still fires under
# --dangerously-skip-permissions and exit 2 blocks the call — verified on Claude Code 2.1.226 against
# both the Read tool and a `cat ../threads.json` Bash fallback (dcc-suz4).
#
# The settings file is generated per cell because the hook command needs an absolute path, which
# depends on where this repo is cloned.
export BENCH_CELL_REPO="$REPO"
HOOK_SETTINGS="$OUT/isolation-settings.json"
jq -n --arg cmd "node $V2/hooks/block-answer-access.js" \
  '{hooks:{PreToolUse:[{matcher:"Read|Edit|Write|Bash|Grep|Glob|NotebookRead|NotebookEdit",
                        hooks:[{type:"command", command:$cmd}]}]}}' > "$HOOK_SETTINGS"

# Record what the cell could actually do, so a run without a toolchain is identifiable rather than
# quietly weaker evidence than one with (dcc-fhp1).
#
# detect_build.sh takes the SUBJECT directory and appends /repo itself. This used to pass
# `dirname "$REPO"`, so detection looked for `v2/repos/repo` and every cell recorded
# `{"error":"detection failed"}` — and because stderr went to /dev/null and the `||` branch
# overwrote the output, detect_build's own `{"error":"no checkout at ..."}` never survived to say
# why. Keep its diagnostic; only synthesize one if it produced nothing at all (dcc-3cm6).
BC="$OUT/build-capability.json"
bash "$V2/detect_build.sh" "$REPO" > "$BC" 2> "$OUT/detect_build.stderr"
if ! jq -e . "$BC" >/dev/null 2>&1; then
  jq -n --arg e "$(head -c 400 "$OUT/detect_build.stderr")" \
    '{error:"build detection produced no JSON", stderr:$e}' > "$BC"
fi
if jq -e '.error' "$BC" >/dev/null 2>&1; then
  echo "[$SUBJ_ID/$TOOL] WARNING: build capability unknown — $(jq -r '.error' "$BC")" >&2
fi


# No tool's prompt names the PR or tells it to fetch one. The v1-faithful wording pointed
# `anthropic-code-review` at "pull request #N of <repo>" and told it to "fetch the PR with gh" —
# written when the answer key was the metric and the PR page was merely a leak to be blocked. Under
# pooled adjudication the review threads on that page are a SCORED TARGET, so the prompt was steering
# one tool at the answer while the others got the local diff. It also made that tool's result depend
# on the shim's field filter, which turned out to be leaking anyway (dcc-3cm6). Every tool now
# reviews the same thing by the same route: the checked-out diff.
case "$TOOL" in
  ours-review) INVOKE="Use the Skill tool to run /decaf-quality-dev:code-review with arguments: review --report" ;;
  ours-bugs)   INVOKE="Use the Skill tool to run /decaf-quality-dev:code-review with arguments: bugs --report" ;;
  ours-audit)  INVOKE="Use the Skill tool to run /decaf-quality-dev:code-review with arguments: audit --report" ;;
  anthropic-code-review)
    INVOKE="Use the Skill tool to run \`code-review:code-review\` — the plugin-qualified command from code-review@claude-plugins-official. It is NOT \`decaf-quality:code-review\`: a different tool ships a skill of the same bare name, so never invoke a bare /code-review, and abort rather than substituting anything else if the qualified skill does not resolve.

Review the proposed change checked out in this repository. Do NOT pass --comment and do NOT post anything to GitHub — output the review to the terminal only. Print every finding you would post, with file:line references." ;;
  # The three below were absent until the pilot (dcc-vkeh). Each needs the diff range named
  # explicitly, because all three default to the WORKING TREE and a v2 fixture is clean at the
  # checkpoint — a tool that reads `git status` alone sees an empty change and reviews nothing.
  superpowers)
    INVOKE="Use the Skill tool to run \`superpowers:requesting-code-review\`, then follow it: dispatch ONE general-purpose subagent filling that skill's code-reviewer.md prompt template, with {BASE_SHA} and {HEAD_SHA} set to the diff range given below. Return the reviewer subagent's report verbatim (Strengths / Critical / Important / Minor / Assessment)." ;;
  pr-review-toolkit)
    INVOKE="Use the Skill tool to run \`pr-review-toolkit:review-pr\` with arguments: all. Dispatch the review agents in parallel. Do NOT post anything to GitHub and do NOT run \`gh pr view\` to look the change up — the change under review is the local diff range given below, not a pull request, and the working tree is clean at its head, so use \`git diff <base> <head>\` wherever the workflow says to inspect changed files. Print every finding with file:line references." ;;
  comprehensive-review)
    INVOKE="Use the Skill tool to run \`comprehensive-review:comprehensive-review\` with arguments: --local --base $BASE. This repository is a detached checkout with NO git remote and NO branches; the change under review is the diff range given below. Treat provider operations as unavailable and run the review locally — do not stop on provider detection, and do not post anything anywhere. Print every finding with file:line references." ;;
  *) echo "unknown tool: $TOOL (known: ours-bugs ours-review ours-audit anthropic-code-review superpowers pr-review-toolkit comprehensive-review)" >&2; exit 2 ;;
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

echo "[$SUBJ_ID/$TOOL shim=$SHIM r$REP] checkpoint ${CP:0:12}, date $DATE, model $BENCH_MODEL effort $BENCH_EFFORT"
t0=$(date +%s)
set +e
# MCP servers are a live, unmeasured leak channel: this machine has context7 (CURRENT library docs),
# playwright (a full browser, so any URL including the PR page), erinra (a memory store, i.e. a
# cross-cell contamination path) and others connected. A cell inherits all of them by default.
# --strict-mcp-config with an empty config file disables every one (dcc-wzbe).
( cd "$REPO" && claude -p "$PROMPT" \
    --model "$BENCH_MODEL" --effort "$BENCH_EFFORT" \
    --disallowedTools WebFetch WebSearch \
    --strict-mcp-config --mcp-config "$V2/shim/no-mcp.json" \
    --settings "$HOOK_SETTINGS" \
    $PERM_FLAGS --output-format json ) > "$OUT/meter.json" 2> "$OUT/stderr.log"
rc=$?
set -e
t1=$(date +%s)

# Suppression justified: a cell that crashed writes no JSON, so `.result` is legitimately absent and
# an empty final-output.md is the correct record of it. `rc` is reported separately on the next line,
# so the failure is visible rather than swallowed.
jq -r '.result // empty' "$OUT/meter.json" > "$OUT/final-output.md" 2>/dev/null || true
cost=$(jq -r '.total_cost_usd // "?"' "$OUT/meter.json" 2>/dev/null)
if [ ! -s "$OUT/final-output.md" ]; then
  echo "[$SUBJ_ID/$TOOL] WARNING: empty final-output.md (rc=$rc) — see stderr.log; do not score this cell" >&2
fi

# `.result` is the FINAL assistant message, which is the whole review only for a tool whose last act
# is to print it. The comprehensive-review probe printed its report and then appended an addendum, so
# final-output.md held 20% of what the tool actually said and none of its original findings. Recover
# the full main-chain output beside it; the ratio is reported per cell so a truncated one is visible
# rather than assumed away.
bash "$V2/extract_cell_report.sh" "$OUT" || \
  echo "[$SUBJ_ID/$TOOL] WARNING: could not extract cell-report.md — score from the transcript by hand" >&2
echo "[$SUBJ_ID/$TOOL] rc=$rc wall=$((t1-t0))s cost=\$$cost -> $OUT"
# Suppression justified: `grep -c` prints 0 and EXITS 1 when nothing matches, which under `set -e`
# would abort the run on the good outcome. The count is still printed, so zero is a measurement.
if [ "$SHIM" = "on" ]; then
  echo "[$SUBJ_ID/$TOOL] external accesses: $(wc -l < "$BENCH_ACCESS_LOG") ($(grep -c 'DENY' "$BENCH_ACCESS_LOG" || true) denied)"
else
  echo "[$SUBJ_ID/$TOOL] external accesses: $(wc -l < "$BENCH_ACCESS_LOG") (unrestricted; $(grep -c 'would=\[DENY' "$BENCH_ACCESS_LOG" || true) would have been DENIED by the shim)"
fi

# The access log covers the NETWORK channels. The scoring artifacts are reachable from the checkout
# by relative path, and no shim sees that — so every cell gets a transcript check too, and its result
# is recorded beside the cell rather than left to be remembered (dcc-suz4).
bash "$V2/verify_cell_isolation.sh" "$OUT" > "$OUT/isolation.txt" 2>&1; iso=$?
case $iso in
  0) echo "[$SUBJ_ID/$TOOL] isolation: CLEAN" ;;
  1) echo "[$SUBJ_ID/$TOOL] isolation: CONTAMINATED — see $OUT/isolation.txt. DO NOT SCORE THIS CELL." >&2 ;;
  *) echo "[$SUBJ_ID/$TOOL] isolation: UNVERIFIED (no transcript) — see $OUT/isolation.txt" >&2 ;;
esac
