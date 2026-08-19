---
# dcc-p3wg
version: 1
title: 'Interactive cross-arm report: filterable view over the emitted fact tables'
status: todo
type: feature
priority: normal
created_at: 2026-08-19T15:44:59Z
updated_at: 2026-08-19T15:45:58Z
parent: dcc-ho2w
blocked_by:
    - dcc-t83x
order: zz
---

A published comparison the operator can pivot and filter, built on the tidy fact tables from
[[dcc-t83x]] (`clusters.jsonl`, `observations.jsonl`, `cells.jsonl`). Blocked on those existing —
the point of the split is that the facts are a data problem and the report is a design problem, and
mixing them is how definitions got baked into four divergent ad-hoc scripts on 2026-08-19.

## What it is for

Selecting axes and filters rather than reading a fixed table:
- axes: arm, subject, `finding_class`, `judged_severity`, verdict, disposition, repeat
- measures: shown, found, reported, noise%, recall against the selected pool, cost per finding
- **the denominator recomputes as arms/subjects are included or excluded**, and the pool size is
  shown changing as it does. That is the property the operator asked for: adding a tool changes the
  total and therefore every fraction ([[dcc-dirp]]).

## Constraints the view must carry, not bury

- Refuse to rank arms across different subject-coverage groups; show coverage as a chip on every arm.
- Withhold ratios below n=10 reported clusters, showing raw counts and the reason.
- Show `valid-minor` as its own band, never merged into either "real" or "noise" — reversal 4 in
  [[dcc-t83x]] came from a metric that folded a correct finding into the miss column.
- State the judge model and the grading-day calibration beside any verdict-derived figure
  ([[dcc-n4nf]]).
- Thread recall as a band, not a point ([[dcc-di47]]).

## Shape

Self-contained artifact page: the three fact tables inlined as JSON, grouping done client-side, no
external calls. Load `artifact-design` first and `dataviz` before any chart code.

## Acceptance

- [ ] Page renders from the committed fact tables with no hand-entered numbers
- [ ] Every guard above is enforced in the view, not just documented
- [ ] A figure picked at random is re-derivable by hand from the fact tables
