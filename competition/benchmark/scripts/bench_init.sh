#!/usr/bin/env bash
# One-time benchmark setup: generate subjects + manifest, check deps + tool availability.
# Does NOT clone subject repos (run_cell fetches each on demand) and does NOT install plugins.
# Usage: bench_init.sh [--force]   (--force regenerates the manifest, losing run state)
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

echo "== review-tool benchmark: init =="
echo "bench dir : $BENCH_DIR"
echo "model     : $BENCH_MODEL   repeats: $REPEATS   perm: $PERM_FLAGS"
echo
echo "-- dependency check --"
for c in jq gh git; do
  command -v "$c" >/dev/null 2>&1 && echo "  ok   $c" || echo "  MISS $c (required)"
done
command -v "$CLAUDE_BIN" >/dev/null 2>&1 && echo "  ok   $CLAUDE_BIN" || echo "  MISS $CLAUDE_BIN (required to run cells)"
echo

echo "-- generate subjects --"
bash "$BENCH_DIR/scripts/gen_subjects.sh"
echo
echo "-- generate manifest --"
bash "$BENCH_DIR/scripts/gen_manifest.sh" "${1:-}"
echo

echo "-- tool availability (claude plugins) --"
plugins="$($CLAUDE_BIN plugin list 2>/dev/null || true)"
if [ -z "$plugins" ]; then
  echo "  (could not read 'claude plugin list' — check each tool manually)"
fi
while IFS= read -r line; do
  tid="$(jq -r .id <<<"$line")"; need="$(jq -r '.requires_plugin // ""' <<<"$line")"
  hint="$(jq -r '.install_hint // "?"' <<<"$line")"
  if [ -z "$need" ]; then
    echo "  n/a  $tid (prompt-based, no plugin)"
  elif printf '%s' "$plugins" | grep -qi "$need"; then
    echo "  ok   $tid  ($need installed)"
  else
    echo "  MISS $tid  — install: $hint"
  fi
done < <(jq -c '.[]' "$TOOLS")
echo
echo "Init complete."
echo "  /bench-status         — progress"
echo "  /bench-run            — run the next pending cell"
echo "  /bench-run --count 2  — run two"
echo "  /bench-run 1__ours__r1 — run a specific cell"
echo
echo "PILOT FIRST: run one cheap cell (e.g. 10__superpowers__r1) and confirm meter.json"
echo "captures subagent tokens before trusting the full matrix (see README)."
