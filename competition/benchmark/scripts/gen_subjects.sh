#!/usr/bin/env bash
# Generate the 12 subject fixtures by merging fetched PR metadata (.pr-meta.jsonl)
# with the curated ground truth (subjects.annotations.json).
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

META="$BENCH_DIR/.pr-meta.jsonl"
ANN="$BENCH_DIR/subjects.annotations.json"
[ -f "$META" ] || { echo "missing $META — re-run the PR-metadata fetch"; exit 1; }
[ -f "$ANN" ]  || { echo "missing $ANN"; exit 1; }

count=0
while IFS= read -r row; do
  id="$(jq -r .id <<<"$row")"
  ann="$(jq -c --argjson id "$id" '.[] | select(.id==$id)' "$ANN")"
  [ -n "$ann" ] || { echo "no annotation for subject $id"; exit 1; }
  lang="$(jq -r .lang <<<"$ann")"; size="$(jq -r .size <<<"$ann")"
  out="$SUBJECTS_DIR/$(printf '%02d' "$id")-${lang}-${size}.json"
  jq -n --argjson m "$row" --argjson a "$ann" '
    {
      id: $m.id, lang: $a.lang, size: $a.size,
      repo: $m.repo, pr: $m.pr, url: $m.url,
      base_ref: $m.base_ref, head_sha: $m.head_sha, merge_sha: $m.merge_sha,
      review: {
        repo: $m.repo, pr_number: $m.pr,
        base: ($m.merge_sha + "^1"), head: $m.merge_sha,
        diff_cmd: ("git diff " + $m.merge_sha + "^1 " + $m.merge_sha)
      },
      size_stats: { additions: $m.additions, deletions: $m.deletions, files: $m.files },
      ground_truth: $a.ground_truth
    }' > "$out"
  echo "  wrote $(basename "$out")"
  count=$((count+1))
done < "$META"
echo "generated $count subject fixtures"
