---
# dcc-y2e6
version: 1
title: Wire v2 into the extraction, clustering and grading pipeline
status: todo
type: feature
priority: critical
created_at: 2026-08-10T17:42:29Z
updated_at: 2026-08-10T19:59:48Z
parent: dcc-ho2w
blocked_by:
    - dcc-595v
order: "4"
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


## Re-scoped by the instrument decision (2026-08-10)

[[dcc-595v]] chose pooled adjudication as the ranking instrument — and **v1's pipeline already is
pooled adjudication minus the key**. Extract per cell, cluster into distinct claims, blind-grade with
a verdict vocabulary: that is what produced subject 9's 98 clusters and its
`TP-primary`/`valid-other`/`nitpick`/`false-positive` distribution.

So this is mostly *removing* the key dependency, not building something new:

- Make the key optional rather than required — pooled cells have none
- Replace `TP-primary` with verdicts that do not presuppose a key, keeping `valid-other`, `nitpick`
  and `false-positive`, which already carry the signal
- **Keep a human-thread match verdict** (v1 called it `TP-human`). Human review threads are now a
  scored target in their own right — the miss detector — so the pipeline must compute recall against
  the admitted threads per subject and report it as a SEPARATE axis. Never merge it into one "recall"
  number with the anchor: agreement with expert review is related to, but not the same as, finding
  real bugs, and OSS reviewers skew toward API design and convention over correctness
- Add severity weighting (v1's precision was unweighted, so four minor findings outscored one
  revert-forcing defect)
- Require a code citation per verdict, and support adversarial re-judging, per the judge-contamination
  mitigations in METHODOLOGY-v2 section 3
- Keep the key path alive for the anchor subjects ([[dcc-9ncz]])
