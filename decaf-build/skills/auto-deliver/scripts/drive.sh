#!/usr/bin/env bash
# Headless driver for /decaf-build:auto-deliver: one lap per fresh `claude -p`
# process, continuing or stopping on the `exit` field auto-deliver writes to
# .decaf/auto-deliver/state.json. Run from the target project's root.
set -euo pipefail

STATE=".decaf/auto-deliver/state.json"
LOG=".decaf/auto-deliver/drive.log"

usage() {
  cat <<'EOF'
Usage: bash drive.sh <plan-id> [options] [-- extra claude args]

Forwarded to auto-deliver:
  --tracker T        nibs | ado | github | markdown
  --models M         low | norm | high
  --review SPEC      review preset plus axis overrides (quote it)
  --base-branch B    integration branch

Caps (none by default, so a run is unlimited):
  --lap-budget USD   per-lap spend cap, passed to claude --max-budget-usd
  --max-turns N      per-lap turn cap, passed to claude --max-turns
  --max-laps N       stop after N laps

Exit codes: 0 plan complete, 2 escalated, 3 no progress, 4 --max-laps reached,
5 claude exited non-zero (a hit cap included), 1 usage or environment error.
Headless runs deny anything that would prompt, so the project's permission
rules must allow what the loop runs (git, build, test, the tracker CLI).
EOF
}

die() { echo "drive.sh: $2" >&2; exit "$1"; }

log() {
  local line
  line="$(date -u +%Y-%m-%dT%H:%M:%SZ) $*"
  echo "$line" >&2
  echo "$line" >>"$LOG"
}

# updated_at changes whenever auto-deliver rewrites its state, so an unchanged
# value after a run means the run did nothing the next run could build on.
stamp() {
  if [[ -r $STATE ]]; then
    jq -r '.updated_at // empty' "$STATE" 2>/dev/null || true
  fi
}

need_value() { [[ $# -ge 2 && -n $2 ]] || die 1 "$1 needs a value"; }

plan="" tracker="" models="" review="" base_branch=""
lap_budget="" max_turns="" max_laps=""
extra=()
while (($#)); do
  case "$1" in
    --tracker)     need_value "$@"; tracker=$2; shift 2 ;;
    --models)      need_value "$@"; models=$2; shift 2 ;;
    --review)      need_value "$@"; review=$2; shift 2 ;;
    --base-branch) need_value "$@"; base_branch=$2; shift 2 ;;
    --lap-budget)  need_value "$@"; lap_budget=$2; shift 2 ;;
    --max-turns)   need_value "$@"; max_turns=$2; shift 2 ;;
    --max-laps)    need_value "$@"; max_laps=$2; shift 2 ;;
    -h | --help)   usage; exit 0 ;;
    --)            shift; extra=("$@"); break ;;
    -*)            die 1 "unknown option: $1 (see --help)" ;;
    *)
      if [[ -n $plan ]]; then die 1 "unexpected argument: $1"; fi
      plan=$1; shift ;;
  esac
done

if [[ -z $plan ]]; then usage >&2; exit 1; fi
if [[ -n $max_laps && ! $max_laps =~ ^[1-9][0-9]*$ ]]; then die 1 "--max-laps must be a positive integer"; fi
command -v claude >/dev/null || die 1 "claude not found on PATH"
command -v jq >/dev/null || die 1 "jq not found on PATH"

prompt="/decaf-build:auto-deliver $plan --laps 1"
if [[ -n $tracker ]]; then prompt+=" --tracker $tracker"; fi
if [[ -n $models ]]; then prompt+=" --models $models"; fi
if [[ -n $base_branch ]]; then prompt+=" --base-branch $base_branch"; fi
if [[ -n $review ]]; then prompt+=" --review \"$review\""; fi

# No --bare: it skips plugins, skills and subagents, which auto-deliver is made of.
args=(-p "$prompt" --permission-prompts none --output-format json)
if [[ -n $lap_budget ]]; then args+=(--max-budget-usd "$lap_budget"); fi
if [[ -n $max_turns ]]; then args+=(--max-turns "$max_turns"); fi
args+=(${extra[@]+"${extra[@]}"})

mkdir -p "$(dirname "$LOG")"
log "start: plan=$plan max_laps=${max_laps:-unlimited} lap_budget=${lap_budget:-unlimited} max_turns=${max_turns:-unlimited}"

lap=0
while :; do
  if [[ -n $max_laps ]] && ((lap >= max_laps)); then
    log "stop: --max-laps $max_laps reached"
    exit 4
  fi
  lap=$((lap + 1))
  before=$(stamp)

  set +e
  out=$(claude "${args[@]}")
  rc=$?
  set -e
  cost=$(jq -r '.total_cost_usd // empty' <<<"$out" 2>/dev/null || true)
  log "lap $lap: claude exit $rc, cost ${cost:-unknown}"

  if ((rc != 0)); then
    log "stop: claude exited $rc; state.json is resumable, rerun to continue"
    exit 5
  fi
  after=$(stamp)
  if [[ -z $after || $after == "$before" ]]; then
    log "stop: no progress (state.json missing or unchanged)"
    exit 3
  fi

  outcome=$(jq -r '.exit // empty' "$STATE" 2>/dev/null || true)
  case $outcome in
    complete)  log "stop: plan complete"; exit 0 ;;
    escalated) log "stop: escalated; see the run report"; exit 2 ;;
    lap-limit) log "lap $lap: phase done, continuing" ;;
    *)         log "stop: no exit recorded in state.json"; exit 3 ;;
  esac
done
