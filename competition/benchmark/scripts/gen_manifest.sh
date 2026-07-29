#!/usr/bin/env bash
# Generate manifest.jsonl = one row per (subject x tool x repeat).
#
#   (no args)       create the manifest; refuses to clobber an existing one
#   --force         regenerate from scratch — LOSES RUN STATE
#   --add-missing   append only the cells that do not exist yet, leaving every
#                   existing row (and its state) untouched, and retire pending
#                   cells whose tool is no longer a target
#
# A tool may carry a `subjects` allowlist in tools.json; when present it runs only
# on those subject ids. Tools without one run on every subject.
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

MODE="${1:-create}"

if [ -f "$MANIFEST" ] && [ "$MODE" = "create" ]; then
  echo "manifest already exists ($(wc -l < "$MANIFEST") cells); pass --force to regenerate (loses run state) or --add-missing to append new cells."
  exit 0
fi

# The (subject,tool,repeat) triples the current tools.json + subjects imply.
wanted="$(mktemp)"
shopt -s nullglob
for sf in "$SUBJECTS_DIR"/*.json; do
  sid="$(jq -r .id "$sf")"; lang="$(jq -r .lang "$sf")"; size="$(jq -r .size "$sf")"
  while read -r tool; do
    # honour a per-tool subject allowlist when it has one
    if jq -e --arg t "$tool" '.[] | select(.id==$t) | has("subjects")' "$TOOLS" >/dev/null; then
      jq -e --arg t "$tool" --argjson s "$sid" \
        '.[] | select(.id==$t) | .subjects | index($s)' "$TOOLS" >/dev/null || continue
    fi
    for r in $(seq 1 "$REPEATS"); do
      jq -nc --arg rid "${sid}__${tool}__r${r}" --argjson sid "$sid" --arg lang "$lang" \
             --arg size "$size" --arg tool "$tool" --argjson r "$r" \
        '{run_id:$rid, subject_id:$sid, lang:$lang, size:$size, tool:$tool, repeat:$r,
          status:"pending", started_at:null, finished_at:null, out_dir:null,
          cost_usd:null, wall_clock_s:null}' >> "$wanted"
    done
  done < <(jq -r '.[].id' "$TOOLS")
done

if [ "$MODE" = "--add-missing" ]; then
  [ -f "$MANIFEST" ] || { echo "no manifest to add to; run without args first."; exit 1; }
  before="$(wc -l < "$MANIFEST")"
  existing="$(jq -r .run_id "$MANIFEST" | sort -u)"
  added=0
  while read -r row; do
    rid="$(jq -r .run_id <<<"$row")"
    grep -qxF "$rid" <<<"$existing" || { echo "$row" >> "$MANIFEST"; added=$((added+1)); }
  done < "$wanted"

  # Retire pending cells for tools that are no longer targets. Done cells are left
  # alone — they are the committed comparison and must stay readable.
  targets="$(jq -r '.[].id' "$TOOLS" | paste -sd, -)"
  tmp="$(mktemp)"
  jq -c --arg targets "$targets" '
    . as $row
    | if $row.status == "pending" and (($targets | split(",")) | index($row.tool) | not)
      then $row + {status: "obsolete"} else $row end' "$MANIFEST" > "$tmp" && mv "$tmp" "$MANIFEST"
  retired="$(jq -c 'select(.status=="obsolete")' "$MANIFEST" | wc -l)"
  rm -f "$wanted"
  echo "manifest: $before -> $(wc -l < "$MANIFEST") cells (+$added new, $retired retired as obsolete)"
  exit 0
fi

mv "$wanted" "$MANIFEST"
echo "manifest: $(wc -l < "$MANIFEST") cells -> $MANIFEST"
