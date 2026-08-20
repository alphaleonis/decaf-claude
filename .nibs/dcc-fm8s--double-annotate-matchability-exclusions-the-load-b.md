---
# dcc-fm8s
version: 1
title: Double-annotate matchability exclusions — the load-bearing calls have no second opinion
status: todo
type: task
created_at: 2026-08-20T18:42:58Z
updated_at: 2026-08-20T18:43:55Z
parent: dcc-ho2w
order: zzzy
---

Every `matchable_at_checkpoint` verdict was produced by ONE pass, and the exclusions are the
load-bearing half: each one changes a denominator, and on a small axis by a lot.

## The measured error rate

From [[dcc-hw48]]'s annotation of six subjects on 2026-08-20:

- **efcore: 1 of 3 exclusions was wrong.** T2's quoted suggestion restructures a block absent at the
  checkpoint, but its closing sentence — "move `nullPropagatedOperands` below" — describes an ordering
  present at `SqlNullabilityProcessor.cs:580-583` that **seven arms** reported. Caught only by the
  `credited_to_unmatchable_thread` cross-check; without it, seven arms silently lost a legitimate hit
  and efcore was the one subject where arms moved *down*.
- **PostHog: 9 of 10 agreement between two independent readings.** The blind grader had flagged 10
  unmatchable threads unprompted; the annotation pass flagged 10; they agreed on 9, differing on T0 vs
  T15 with a specific checkable reason each way. That second opinion existed only by accident — the
  grader was not asked for it.
- Two subjects' agents disclosed verdicts resting on **inference** rather than observation
  (prometheus T7 from reconstructed subquery arithmetic; efcore T7 from line-offset arithmetic), since
  post-checkpoint commits are absent from the fixture and forward diffs are impossible.

**Sensitivity:** one verdict moves recall by 1/n. mattermost is n=3, so a single bad call is 33%.
grafana-117615 went to n=0 on two verdicts.

## Fix — cheap, because it is targeted

Do NOT double-annotate everything. `matchable = true` is the safe default direction and the bulk of the
work; the exclusions are the small, dangerous set (13 across six subjects).

- Second independent pass over the **exclusions only**, blind to the first pass's reasoning.
- Disagreement resolves toward `matchable` — including an unmatchable thread costs every arm equally
  and visibly, while excluding a matchable one silently inflates every arm.
- Record both verdicts, as the standing calibration sample does for the pilot's two passes.
- Compound threads get the rule stated explicitly: **matchable if ANY claim targets present code.**
  That is what the efcore error was.

## Acceptance

- [ ] Every `matchable_at_checkpoint: false` verdict on a scored subject carries two independent readings
- [ ] Disagreements are recorded, not silently resolved, and default toward matchable
- [ ] The compound-thread rule is in the annotator prompt and in `METRICS.md`
- [ ] `credited_to_unmatchable_thread` is empty on every scored subject
