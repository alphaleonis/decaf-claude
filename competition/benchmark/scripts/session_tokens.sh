#!/usr/bin/env bash
# Emit WHOLE-SESSION tokens AND timing for a claude session: the orchestrator transcript PLUS every
# subagent transcript (<project>/<session_id>/subagents/agent-*.jsonl).
# Usage: session_tokens.sh <session_id>   -> prints a JSON object (or {"error":...})
#
# Notes baked into the numbers:
#  - Token sums are deduped by message id. `total` is prompt-cache-inflated (cache_read re-counted
#    per turn); `output` is the clean, cache-independent work signal.
#  - TIME: the authoritative TOTAL review time is the harness `wall_clock_s` (measured around the whole
#    run), NOT the sum of subagent durations — subagents run in PARALLEL. `per_subagent[].duration_s`
#    (first->last message in that subagent's transcript) is diagnostic; `max_subagent_duration_s` is
#    the longest single agent. `orchestrator.duration_s` ~ wall_clock.
set -euo pipefail
sid="${1:?usage: session_tokens.sh <session_id>}"
proj="$HOME/.claude/projects"

orch="$(find "$proj" -maxdepth 2 -name "${sid}.jsonl" 2>/dev/null | head -1)"
if [ -z "$orch" ]; then
  printf '{"error":"transcript not found","session_id":"%s","subagents":0}\n' "$sid"
  exit 0
fi
subdir="$(dirname "$orch")/${sid}/subagents"

# per-file stats: deduped token sums + duration from first/last timestamp
file_stats() {
  jq -s '
    ( [ .[] | select(.type=="assistant" and .message.usage!=null) | {id:.message.id, u:.message.usage} ]
      | group_by(.id) | map(.[0].u) ) as $u
    | ( [ .[] | .timestamp // empty | sub("\\.[0-9]+Z$";"Z") | (fromdateiso8601? // empty) ] ) as $ts
    | { output:         (($u|map(.output_tokens//0)|add)//0),
        input:          (($u|map(.input_tokens//0)|add)//0),
        cache_creation: (($u|map(.cache_creation_input_tokens//0)|add)//0),
        cache_read:     (($u|map(.cache_read_input_tokens//0)|add)//0),
        total:          (($u|map((.input_tokens//0)+(.output_tokens//0)+(.cache_creation_input_tokens//0)+(.cache_read_input_tokens//0))|add)//0),
        duration_s:     (if ($ts|length)>0 then (($ts|max)-($ts|min)) else 0 end) }' "$1"
}

orch_stats="$(file_stats "$orch")"

per_sub='[]'; nsub=0
if [ -d "$subdir" ]; then
  while IFS= read -r f; do
    nsub=$((nsub+1))
    st="$(file_stats "$f")"
    per_sub="$(jq -c --arg a "$(basename "$f" .jsonl)" --argjson st "$st" '. + [$st + {agent:$a}]' <<<"$per_sub")"
  done < <(find "$subdir" -name '*.jsonl' | sort)
fi

# whole-session sums = orchestrator + subagents
jq -n --argjson orch "$orch_stats" --argjson subs "$per_sub" --argjson nsub "$nsub" '
  ($subs | map(.output)|add // 0)         as $so |
  ($subs | map(.input)|add // 0)          as $si |
  ($subs | map(.cache_creation)|add // 0) as $scc |
  ($subs | map(.cache_read)|add // 0)     as $scr |
  ($subs | map(.total)|add // 0)          as $st |
  ($subs | map(.duration_s))              as $sd |
  { subagents: $nsub,
    input:          ($orch.input + $si),
    output:         ($orch.output + $so),
    cache_creation: ($orch.cache_creation + $scc),
    cache_read:     ($orch.cache_read + $scr),
    total:          ($orch.total + $st),
    orchestrator:   {output:$orch.output, total:$orch.total, duration_s:$orch.duration_s},
    per_subagent:   $subs,
    max_subagent_duration_s: (($sd|max) // 0),
    sum_subagent_duration_s: (($sd|add) // 0) }'
