#!/usr/bin/env bash
# (Re)render runs/<run_id>/run.md from its meta.json + raw_output.md. meta.json holds every field,
# so a run can be re-rendered without re-executing it. Called by run_cell.sh, and usable standalone
# to refresh run.md after display changes. Usage: render_run.sh <run_id>
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

RID="${1:?usage: render_run.sh <run_id>}"
outdir="$RUNS_DIR/$RID"; M="$outdir/meta.json"
[ -f "$M" ] || { echo "no meta.json for $RID"; exit 1; }
g() { jq -r "$1 // \"\"" "$M"; }

tool="$(g .tool)"; subject_id="$(g .subject_id)"; lang="$(g .lang)"; size="$(g .size)"
repo="$(g .repo)"; pr="$(g .pr)"; base="$(g .review_base)"; head="$(g .review_head)"; merge="$(g .merge_sha)"
model="$(g .model)"; final="$(g .status)"; rc="$(g .exit_code)"; is_error="$(g .is_error)"; subtype="$(g .subtype)"
wall="$(g .wall_clock_s)"; dur_ms="$(g .duration_ms)"; dur_api="$(g .duration_api_ms)"; num_turns="$(g .num_turns)"
cost="$(g .cost_usd)"
in_tok="$(g .orch_usage.input_tokens)"; out_tok="$(g .orch_usage.output_tokens)"
cc_tok="$(g .orch_usage.cache_creation_tokens)"; cr_tok="$(g .orch_usage.cache_read_tokens)"; total_tok="$(g .orch_usage.total_tokens)"
ws_sub="$(g .session_tokens.subagents)"; ws_in="$(g .session_tokens.input)"; ws_out="$(g .session_tokens.output)"
ws_cc="$(g .session_tokens.cache_creation)"; ws_cr="$(g .session_tokens.cache_read)"; ws_total="$(g .session_tokens.total)"
ws_maxsub="$(g .session_tokens.max_subagent_duration_s)"
sid="$(g .session_id)"; findings_lines="$(g .findings_lines)"
sub_rows="$(jq -r '.session_tokens.per_subagent[]? | "| \(.agent) | \(.output) | \(.total) | \(.duration_s) |"' "$M" 2>/dev/null || true)"

{
  echo "# Benchmark run: $RID"
  echo
  echo "| field | value |"
  echo "|---|---|"
  echo "| tool | $tool |"
  echo "| subject | $subject_id ($lang / $size) — $repo#$pr |"
  echo "| review diff | \`$base..$head\` (merge $merge) |"
  echo "| session model | $model |"
  echo "| status | $final (exit $rc, is_error=$is_error, subtype=${subtype:-n/a}) |"
  echo "| **total review time — wall (s)** | $wall |"
  echo "| longest single subagent (s) | ${ws_maxsub:-n/a} |"
  echo "| duration_ms (orchestrator self) | ${dur_ms:-n/a} |"
  echo "| duration_api_ms (summed parallel API time, not wall) | ${dur_api:-n/a} |"
  echo "| num_turns | ${num_turns:-n/a} |"
  echo "| cost_usd | ${cost:-n/a} |"
  echo "| input_tokens | ${in_tok:-n/a} |"
  echo "| output_tokens | ${out_tok:-n/a} |"
  echo "| cache_creation_tokens | ${cc_tok:-n/a} |"
  echo "| cache_read_tokens | ${cr_tok:-n/a} |"
  echo "| total_tokens (orchestrator only) | ${total_tok:-n/a} |"
  echo "| **subagents** | ${ws_sub:-n/a} |"
  echo "| **ws output_tokens** | ${ws_out:-n/a} |"
  echo "| ws input_tokens | ${ws_in:-n/a} |"
  echo "| ws cache_creation | ${ws_cc:-n/a} |"
  echo "| ws cache_read | ${ws_cr:-n/a} |"
  echo "| ws total_tokens | ${ws_total:-n/a} |"
  echo "| session_id | ${sid:-n/a} |"
  echo "| findings (raw lines) | $findings_lines |"
  echo
  echo "> **ws = whole-session** (orchestrator + every subagent transcript, deduped). The non-ws token"
  echo "> rows are the orchestrator session ONLY — they miss subagent tokens for fan-out tools."
  echo "> **\`cost_usd\` is the authoritative whole-session cost** (Claude Code sums subagents; not an estimate)."
  echo "> Caveat: \`ws total_tokens\` is inflated by prompt-cache re-reads (cache_read counted per turn);"
  echo "> \`ws output_tokens\` is the clean, cache-independent work signal. Findings files under ./findings/."
  if [ -n "${sub_rows:-}" ]; then
    echo
    echo "### Per-subagent (diagnostic)"
    echo
    echo "Subagents run in PARALLEL — the TOTAL review time is the wall clock above (${wall}s), NOT the sum of these."
    echo
    echo "| agent | output_tokens | total_tokens | duration_s |"
    echo "|---|---:|---:|---:|"
    echo "$sub_rows"
  fi
  echo
  echo "## Findings (final result text)"
  echo
  echo '```'
  [ -f "$outdir/raw_output.md" ] && cat "$outdir/raw_output.md"
  echo '```'
} > "$outdir/run.md"
echo "rendered $outdir/run.md"
