#!/usr/bin/env bash
# Generate the 12 subject fixtures by merging fetched PR metadata (.pr-meta.jsonl)
# with the curated ground truth (subjects.annotations.json).
# The v1 dataset is void on four independent counts (see v1-archive/README.md) and has been archived.
# Every v1 entry point refuses by default: a banner on a command is not a control, and 11 of these 12
# scripts had none until dcc-j21q. v2 runs through v2/run_cell_v2.sh and the bench-* commands.
if [ "${BENCH_V1_ALLOW:-0}" != "1" ]; then
  cat >&2 <<'EOF'
REFUSING: the v1 benchmark is retired and its data is archived under v1-archive/.

  Its results are void (contamination, GitHub leak, unaudited ground truth, unpinned effort) and
  the two leaks point in opposite directions, so no v1 number is citable in any form.

  For v2:      /bench-status, /bench-run, /bench-analyze, /bench-synthesize
  Background:  competition/benchmark/v2/README.md, METHODOLOGY-v2.md, milestone dcc-ho2w

  To run v1 anyway (reproducing a leak, regenerating evidence): BENCH_V1_ALLOW=1
EOF
  exit 3
fi

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
