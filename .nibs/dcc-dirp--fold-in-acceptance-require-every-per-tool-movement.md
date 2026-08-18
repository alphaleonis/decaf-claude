---
# dcc-dirp
version: 1
title: 'Fold-in acceptance: require every per-tool movement explained, not zero movements'
status: todo
type: task
priority: normal
created_at: 2026-08-18T17:44:27Z
updated_at: 2026-08-18T17:45:05Z
parent: dcc-ho2w
order: zw
---

`dcc-u10u`'s acceptance said "existing per-tool figures asserted unchanged". That is not
achievable by any arm that finds something new, and as a pass/fail gate it rewards a weak arm:
an arm contributing nothing novel passes trivially, while one that finds a real defect no other
tool found necessarily fails.

Observed 2026-08-18 folding `ours-review-postdduy` into five subjects. Twelve movements, of two
kinds:

- `unique_real` fell in three places (efcore `pr-review-toolkit` 2->1, mattermost `superpowers`
  1->0, grafana `superpowers` 3->2). Benign: "unique" means only that tool reported it.
- The real-defect **pool grew** (immich 4->5, grafana 4->6) because three clusters only the new
  arm found graded `valid-other` and classed `defect`. Every pre-existing tool's recall fell
  without those tools changing: `ours-bugs` 1.000 -> 0.800 on immich, 1.000 -> 0.667 on grafana.

The second is inherent to pooled adjudication — METHODOLOGY-v2 says the pooled axis is "bounded by
the union of tool output" — so it will recur for every arm that finds something genuinely new.

## What to change

- Reword the acceptance in the fold-in docs and `/bench-analyze`: every movement must be
  **explained**, not absent. Zero movements is not the target.
- Make the check a script (`assert_foldin_movements.py`): diff per-tool fields before/after,
  classify each movement as `unique_real-lost` / `pool-grew` / `unexplained`, and exit non-zero
  only on `unexplained`.
- Wherever `defect_recall` is published, print the pool size beside it. A recall figure without
  its denominator is not comparable across fold-ins.

## Acceptance

- [ ] Acceptance wording fixed in `prompts/README.md` and `/bench-analyze`
- [ ] `assert_foldin_movements.py` + a test covering both benign classes and one unexplained case
- [ ] `BUGS-SP-RESULTS.md` carries a note that its immich/grafana defect-recall figures are
      superseded by the post-`ours-review-postdduy` pool
