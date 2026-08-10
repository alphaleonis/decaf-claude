---
# dcc-y2e6
version: 1
title: Wire v2 into the extraction, clustering and grading pipeline
status: todo
type: feature
priority: critical
created_at: 2026-08-10T17:42:29Z
updated_at: 2026-08-10T17:44:03Z
parent: dcc-ho2w
blocked_by:
    - dcc-595v
order: X
---

There is currently NO v2 scoring pipeline. Zero references to `analysis/scripts/*.py` anywhere under
`v2/`. The four cells run so far were graded by hand, by reading them.

v1 has the machinery already: per-cell findings extraction, cross-tool clustering (800 findings ->
98 clusters on subject 9), blind verdict assignment, and deterministic metrics in
`compute_metrics.py` / `rebuild_metrics.py`. The work is adapting it, not rebuilding it.

## Scope

- Point extraction at `v2/runs/<cell>/final-output.md` and the tool's own report file
- Cluster across tools as v1 does — this is what makes thin keys survivable, since it surfaces
  findings outside the key for the judge to classify
- Grade against `v2/analysis/subject-NN/answer-key.json` (new shape: `entries[]` with `must_flag`,
  `must_not_require`, provenance) rather than v1's `primary_bug`/`human_issues` shape
- Emit metrics with the v2 verdict vocabulary from the scoring-model decision
- Record `access.log` counts per cell, including `would=[DENY]` for control-arm cells

Depends on the scoring-model decision. Do not build against the current key-only framing.

## Acceptance

- [ ] A v2 cell can be scored end to end with no hand-grading
- [ ] Subject 2's four existing cells reproduce the hand-graded result
- [ ] Metrics computed deterministically, not by the LLM
