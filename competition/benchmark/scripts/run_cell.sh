#!/usr/bin/env bash
# Run ONE benchmark cell in an isolated `claude -p` session and capture all metrics.
# Usage: run_cell.sh <run_id>            e.g. run_cell.sh 1__ours__r1
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

RID="${1:?usage: run_cell.sh <run_id>}"
subject_id="${RID%%__*}"; rest="${RID#*__}"; tool_id="${rest%%__*}"; repeat="${rest##*r}"

# already done? (idempotent resume)
if [ "$(manifest_get "$RID" status)" = "done" ]; then
  echo "[$RID] already done — skipping"; exit 0
fi

subj_file="$(ls "$SUBJECTS_DIR"/"$(printf '%02d' "$subject_id")"-*.json 2>/dev/null | head -1)"
[ -f "$subj_file" ] || { echo "[$RID] no subject fixture for id=$subject_id"; exit 1; }
S="$(cat "$subj_file")"
repo="$(jq -r .repo <<<"$S")"; pr="$(jq -r .pr <<<"$S")"; merge="$(jq -r .merge_sha <<<"$S")"
lang="$(jq -r .lang <<<"$S")"; size="$(jq -r .size <<<"$S")"
base="${merge}^1"; head="$merge"

T="$(jq -c --arg t "$tool_id" '.[] | select(.id==$t)' "$TOOLS")"
[ -n "$T" ] || { echo "[$RID] unknown tool: $tool_id"; exit 1; }
invocation_tmpl="$(jq -r .invocation <<<"$T")"
findings_glob="$(jq -r '.findings_file // ""' <<<"$T")"

outdir="$RUNS_DIR/$RID"; mkdir -p "$outdir/findings"
repo_dir="$REPOS_DIR/$subject_id"

ensure_repo() {
  if [ -d "$repo_dir/.git" ] && git -C "$repo_dir" cat-file -e "$merge^{commit}" 2>/dev/null; then return; fi
  mkdir -p "$repo_dir"
  git -C "$repo_dir" init -q 2>/dev/null || true
  git -C "$repo_dir" remote add origin "https://github.com/$repo" 2>/dev/null || true
  echo "[$RID] fetching $repo @ ${merge:0:12} (depth 2)…"
  git -C "$repo_dir" fetch -q --depth 2 origin "$merge"
  git -C "$repo_dir" checkout -q -f "$merge"
}
ensure_repo

# build the prompt
prompt="$invocation_tmpl"
for kv in "REPO=$repo" "PR=$pr" "BASE=$base" "HEAD=$head" "MERGE=$merge" "REPO_DIR=$repo_dir"; do
  k="${kv%%=*}"; v="${kv#*=}"; prompt="${prompt//\{$k\}/$v}"
done
printf '%s\n' "$prompt" > "$outdir/prompt.txt"

manifest_start "$RID"
echo "[$RID] $tool_id on $repo#$pr ($lang/$size)  model=$BENCH_MODEL"
t0="$(epoch)"
set +e
( cd "$repo_dir" && $CLAUDE_BIN -p "$prompt" --model "$BENCH_MODEL" $PERM_FLAGS --output-format json ) \
  > "$outdir/meter.json" 2> "$outdir/stderr.log"
rc=$?
set -e
t1="$(epoch)"; wall=$((t1 - t0))

M="$outdir/meter.json"
jm() { jq -r "$1 // empty" "$M" 2>/dev/null; }
# NB: jq `//` collapses boolean false, so read is_error explicitly, not via jm().
is_error="$(jq -r 'if has("is_error") then (.is_error|tostring) else "unknown" end' "$M" 2>/dev/null)"; [ -z "$is_error" ] && is_error="unknown"
subtype="$(jm '.subtype')"
cost="$(jm '.total_cost_usd')"
in_tok="$(jm '.usage.input_tokens')"; out_tok="$(jm '.usage.output_tokens')"
cc_tok="$(jm '.usage.cache_creation_input_tokens')"; cr_tok="$(jm '.usage.cache_read_input_tokens')"
num_turns="$(jm '.num_turns')"; dur_ms="$(jm '.duration_ms')"; dur_api="$(jm '.duration_api_ms')"
sid="$(jm '.session_id')"

# Subscription usage/session limit hit: this is not a real result. Don't record a partial cell —
# drop its artifacts, reset it to pending, and signal the driver (exit 75) to stop the batch so we
# don't churn the remaining queue against a limit. Resume after the limit resets.
if [ "$is_error" = "true" ] && jq -r '.result // ""' "$M" | grep -qiE 'session limit|usage limit|hit your (session|usage|weekly) limit|reached your .* limit'; then
  echo "[$RID] SESSION/USAGE LIMIT reached ($(jq -r '.result // ""' "$M" | head -1)) — not recording; reset to pending."
  rm -rf "$outdir"
  manifest_pending "$RID"
  exit 75
fi

# findings: the final result text, always
jq -r '.result // ""' "$M" > "$outdir/raw_output.md" 2>/dev/null || : > "$outdir/raw_output.md"
# plus any tool-written report file inside the subject repo
if [ -n "$findings_glob" ]; then
  # shellcheck disable=SC2086
  ( cd "$repo_dir" && ls -t $findings_glob 2>/dev/null | head -3 ) | while IFS= read -r f; do
    [ -n "$f" ] && cp "$repo_dir/$f" "$outdir/findings/" 2>/dev/null || true
  done
fi
# complete findings bundle: orchestrator final output + every subagent's full text (grading-proof)
bash "$BENCH_DIR/scripts/archive_findings.sh" "${sid:-}" "$outdir/findings" "$outdir/raw_output.md" >/dev/null 2>&1 || true

findings_lines="$(wc -l < "$outdir/raw_output.md" | tr -d ' ')"
total_tok=0; for v in "$in_tok" "$out_tok" "$cc_tok" "$cr_tok"; do [ -n "$v" ] && total_tok=$((total_tok + v)); done

# WHOLE-SESSION tokens: the -p .usage above is ORCHESTRATOR-ONLY (misses subagent tokens).
# Sum the orchestrator transcript + its subagents/ dir, deduped by message id. Capture now,
# while the transcripts are fresh on disk.
ws_json='{}'
if [ -n "${sid:-}" ]; then ws_json="$(bash "$BENCH_DIR/scripts/session_tokens.sh" "$sid" 2>/dev/null || echo '{}')"; fi
wsj() { jq -r "$1 // \"\"" <<<"$ws_json" 2>/dev/null; }
ws_sub="$(wsj '.subagents')"; ws_in="$(wsj '.input')"; ws_out="$(wsj '.output')"
ws_cc="$(wsj '.cache_creation')"; ws_cr="$(wsj '.cache_read')"; ws_total="$(wsj '.total')"
ws_maxsub="$(wsj '.max_subagent_duration_s')"
sub_rows="$(jq -r '.per_subagent[]? | "| \(.agent) | \(.output) | \(.total) | \(.duration_s) |"' <<<"$ws_json" 2>/dev/null || true)"

final="done"; { [ "$rc" -ne 0 ] || [ "$is_error" = "true" ]; } && final="failed"

jq -n --arg rid "$RID" --argjson sid_ "$subject_id" --arg lang "$lang" --arg size "$size" \
  --arg tool "$tool_id" --argjson repeat "$repeat" --arg model "$BENCH_MODEL" \
  --arg repo "$repo" --argjson pr "$pr" --arg merge "$merge" --arg base "$base" --arg head "$head" \
  --argjson wall "$wall" --argjson rc "$rc" --arg status "$final" --arg cmd "$prompt" \
  --arg cost "${cost:-}" --arg intok "${in_tok:-}" --arg outtok "${out_tok:-}" \
  --arg cctok "${cc_tok:-}" --arg crtok "${cr_tok:-}" --argjson total "$total_tok" \
  --arg turns "${num_turns:-}" --arg durms "${dur_ms:-}" --arg durapi "${dur_api:-}" \
  --arg sid "${sid:-}" --arg iserr "$is_error" --arg subtype "${subtype:-}" \
  --argjson ws "${ws_json:-null}" \
  '{run_id:$rid, subject_id:$sid_, lang:$lang, size:$size, tool:$tool, repeat:$repeat, model:$model,
    repo:$repo, pr:$pr, merge_sha:$merge, review_base:$base, review_head:$head,
    status:$status, exit_code:$rc, is_error:$iserr, subtype:$subtype,
    wall_clock_s:$wall, duration_ms:$durms, duration_api_ms:$durapi, num_turns:$turns,
    cost_usd:$cost,
    orch_usage:{input_tokens:$intok, output_tokens:$outtok, cache_creation_tokens:$cctok, cache_read_tokens:$crtok, total_tokens:$total},
    session_tokens:$ws,
    input_tokens:$intok, output_tokens:$outtok, cache_creation_tokens:$cctok, cache_read_tokens:$crtok, total_tokens:$total,
    session_id:$sid, findings_lines:'"$findings_lines"', invocation:$cmd, finished_at:"'"$(now_iso)"'"}' \
  > "$outdir/meta.json"

# run.md is rendered from meta.json (+ raw_output.md) so it can be regenerated without re-running.
bash "$BENCH_DIR/scripts/render_run.sh" "$RID" >/dev/null

# metrics.csv is derived from every runs/*/meta.json (source of truth) — rebuild it now.
bash "$BENCH_DIR/scripts/rebuild_metrics.sh" >/dev/null

manifest_finish "$RID" "$final" "${cost:-}" "$wall" "runs/$RID"
echo "[$RID] $final — wall ${wall}s, cost \$${cost:-?}, tokens(sum) $total_tok, findings ${findings_lines} lines -> runs/$RID/run.md"
