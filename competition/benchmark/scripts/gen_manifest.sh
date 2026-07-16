#!/usr/bin/env bash
# Generate manifest.jsonl = one row per (subject x tool x repeat). Refuses to clobber
# an existing manifest (which holds run state) unless --force is given.
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

if [ -f "$MANIFEST" ] && [ "${1:-}" != "--force" ]; then
  echo "manifest already exists ($(wc -l < "$MANIFEST") cells); pass --force to regenerate (loses run state)."
  exit 0
fi

tmp="$(mktemp)"
tools="$(jq -r '.[].id' "$TOOLS")"
shopt -s nullglob
for sf in "$SUBJECTS_DIR"/*.json; do
  sid="$(jq -r .id "$sf")"; lang="$(jq -r .lang "$sf")"; size="$(jq -r .size "$sf")"
  for tool in $tools; do
    for r in $(seq 1 "$REPEATS"); do
      rid="${sid}__${tool}__r${r}"
      jq -nc --arg rid "$rid" --argjson sid "$sid" --arg lang "$lang" --arg size "$size" \
             --arg tool "$tool" --argjson r "$r" \
        '{run_id:$rid, subject_id:$sid, lang:$lang, size:$size, tool:$tool, repeat:$r,
          status:"pending", started_at:null, finished_at:null, out_dir:null,
          cost_usd:null, wall_clock_s:null}' >> "$tmp"
    done
  done
done
mv "$tmp" "$MANIFEST"
echo "manifest: $(wc -l < "$MANIFEST") cells -> $MANIFEST"
