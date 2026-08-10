---
# dcc-y2e6
version: 1
title: Wire v2 into the extraction, clustering and grading pipeline
status: completed
type: feature
priority: critical
created_at: 2026-08-10T17:42:29Z
updated_at: 2026-08-10T20:06:32Z
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
## Acceptance

- [x] A v2 cell can be scored end to end with no hand-grading — the deterministic chain
      (`check_artifacts.py` → `score_pooled.py` → `metrics.json`) is demonstrated end to end on a
      synthetic subject. The LLM stages are specified in `/bench-analyze-v2` and first run for real
      at [[dcc-vkeh]], which is the only place real cell output exists.
- [~] ~~Subject 2's four existing cells reproduce the hand-graded result~~ — **superseded, not done.**
      Those four cells are `anthropic-code-review` only, on the retired key-based subject 2. A
      single-tool pool is degenerate under pooled adjudication: precision is computable but every
      cross-tool metric (unique real findings, overlap, separation) is undefined on n=1 tool. They
      cannot validate this pipeline. Validation is instead the 12 self-tests plus the synthetic
      end-to-end here, with real validation at [[dcc-vkeh]].
- [x] Metrics computed deterministically, not by the LLM — all arithmetic in `score_pooled.py`;
      `/bench-analyze-v2` forbids hand-computing any number
- [x] **Extraction fails loudly on a silently-empty field** — exits 3 when a tool's severities are
      empty or present on <20% of its findings, and when a cell contributes zero clusters. Both
      shapes tested (`empty_severity_whole_tool`, `sparse_severity`, `cell_with_zero_clusters`)
- [x] **Artifacts are checked for mutual consistency** — `check_artifacts.py`, verified against a
      synthetic reproduction of the original failure (extract and findings sharing one pair in ten),
      which it rejects at 10% overlap
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

## Summary

**Completed 2026-08-10** — Deterministic v2 scoring core built and under test. `v2/scoring/score_pooled.py` computes the three
axes, `check_artifacts.py` enforces cross-layer consistency, `test_score_pooled.py` has 12 passing
self-tests, and `/bench-analyze-v2` specifies the LLM stages that feed them.

The three axes are structurally prevented from merging: there is no way to express a combined recall
number, because merging thread recall into precision would quietly turn "reviews like a human" into
"finds bugs". Precision is severity-weighted, since v1's was not — which let four minor findings
outscore one revert-forcing defect.

Both fail-loud requirements are implemented AND tested rather than asserted. Empty or sparse
severities, a cell contributing no cluster, a real verdict without a code citation, a thread verdict
without an index, a stale v1 verdict name, and a missing judge_model all exit 3 instead of emitting a
null metric. `check_artifacts.py` was verified against a synthetic reproduction of the z13k shape —
extract and findings sharing one pair in ten — which it rejects at 10% overlap.

The synthetic end-to-end run surfaced a useful property: **precision ordering and thread-recall
ordering disagree** (two tools tied at 0.667 thread recall while their precision differed by 0.5).
That is direct evidence the axes are not redundant, which was the argument for keeping them apart.

One acceptance item was superseded rather than met, and is recorded as such: subject 2's four cells
cannot validate this pipeline, because they are all one tool on the retired key-based subject and
every cross-tool metric is undefined on a single-tool pool.

Note for [[dcc-vkeh]]: `run_cell_v2.sh` still resolves subjects to `v2/repos/<id>`, while pooled
subjects live at `v2/pooled/<owner>-<repo>-<pr>/repo`. That is already its first acceptance item.
