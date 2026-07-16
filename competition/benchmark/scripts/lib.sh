#!/usr/bin/env bash
# Shared helpers for the review-tool benchmark. Source this from every script.
set -euo pipefail

BENCH_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd "$BENCH_DIR/../.." && pwd)"
SUBJECTS_DIR="$BENCH_DIR/subjects"
RUNS_DIR="$BENCH_DIR/runs"
REPOS_DIR="$BENCH_DIR/repos"
RESULTS_DIR="$BENCH_DIR/results"
MANIFEST="$BENCH_DIR/manifest.jsonl"
TOOLS="$BENCH_DIR/tools.json"
METRICS_CSV="$RESULTS_DIR/metrics.csv"
LOCK="$BENCH_DIR/.manifest.lock"

# Defaults; config.env overrides.
BENCH_MODEL="claude-opus-4-8"
CLAUDE_BIN="claude"
PERM_FLAGS="--dangerously-skip-permissions"
REPEATS=2
# shellcheck disable=SC1091
[ -f "$BENCH_DIR/config.env" ] && source "$BENCH_DIR/config.env"

mkdir -p "$SUBJECTS_DIR" "$RUNS_DIR" "$REPOS_DIR" "$RESULTS_DIR"

now_iso() { date -u +%Y-%m-%dT%H:%M:%SZ; }
epoch()   { date +%s; }

# manifest_get <run_id> <field>
manifest_get() { jq -r --arg r "$1" 'select(.run_id==$r) | .'"$2" "$MANIFEST" 2>/dev/null | head -1; }

# manifest_start <run_id>
manifest_start() {
  local rid="$1"
  ( flock 9
    local t; t="$(mktemp)"
    jq -c --arg r "$rid" --arg ts "$(now_iso)" \
      'if .run_id==$r then .status="running" | .started_at=$ts else . end' "$MANIFEST" > "$t"
    mv "$t" "$MANIFEST"
  ) 9>"$LOCK"
}

# manifest_pending <run_id> — reset a cell to pending (for a clean retry, e.g. after a usage limit)
manifest_pending() {
  local rid="$1"
  ( flock 9
    local t; t="$(mktemp)"
    jq -c --arg r "$rid" \
      'if .run_id==$r then .status="pending" | .started_at=null | .finished_at=null | .out_dir=null | .cost_usd=null | .wall_clock_s=null else . end' \
      "$MANIFEST" > "$t"
    mv "$t" "$MANIFEST"
  ) 9>"$LOCK"
}

# manifest_finish <run_id> <status> <cost_usd> <wall_s> <out_dir>
manifest_finish() {
  local rid="$1" st="$2" cost="$3" wall="$4" od="$5"
  ( flock 9
    local t; t="$(mktemp)"
    jq -c --arg r "$rid" --arg s "$st" --arg ts "$(now_iso)" --arg c "$cost" \
          --argjson w "${wall:-0}" --arg od "$od" \
      'if .run_id==$r then .status=$s | .finished_at=$ts | .cost_usd=$c | .wall_clock_s=$w | .out_dir=$od else . end' \
      "$MANIFEST" > "$t"
    mv "$t" "$MANIFEST"
  ) 9>"$LOCK"
}
