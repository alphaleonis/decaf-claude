---
# dcc-y2e6
version: 1
title: Wire v2 into the extraction, clustering and grading pipeline
status: todo
type: feature
priority: critical
created_at: 2026-08-10T17:42:29Z
updated_at: 2026-08-10T18:42:12Z
parent: dcc-ho2w
blocked_by:
    - dcc-595v
order: H
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
- [ ] **Extraction fails loudly on a silently-empty field.** If a field it is supposed to capture
      comes back empty for an entire tool/subject, that is an extraction defect, not data — it must
      error rather than emit a null metric. Carried from scrapped [[dcc-3v3m]]: subject 10's harvest
      captured severities on 2 of 78 entries, every consolidated entry blank, and under the
      then-current macro-average a single stray sub-agent `critical` handed one tool a free 1.00 on
      n=1 that carried a full one-ninth weight in its published figure.
- [ ] **Artifacts are checked for mutual consistency.** Re-extraction must not leave `extract/`,
      `findings.json` and `analysis.json` describing different finding sets. Carried from scrapped
      [[dcc-z13k]]: subject 6's anthropic r2 had 20 findings in the extract and 33 in findings.json
      with 1 pair in common, while analysis.json clustered the stale set — so a published number
      rested on findings the pipeline no longer contained. A consistency assertion must fail the run.
