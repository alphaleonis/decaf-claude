---
# dcc-fm8s
version: 1
title: Double-annotate matchability exclusions — the load-bearing calls have no second opinion
status: completed
type: task
created_at: 2026-08-20T18:42:58Z
updated_at: 2026-08-20T19:26:10Z
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

## Done 2026-08-20

17 exclusions across the six scored subjects (not 13 — the count in this nib predated efcore's and
PostHog's later annotation). All 17 second-read, blind to the first pass's reasoning.

**2 of 17 flipped, both the compound-thread shape, both having cost arms a legitimate hit:**

- **efcore T1.** Its quoted suggestion (`elseResult == null` -> `is null`) has no target — the
  checkpoint condition is `IsNull(elseResult)`. Its closing parenthetical is a separate general
  claim, *"I actually use `is` for any constant/literal check at this point"*, and that has two
  targets in the added code, including `func.InstancePropagatesNullability == true` at :633, one
  line below an `is`-pattern doing the same job.
- **mattermost T6.** Sentence 1 asks for a request logger and no logging exists at the checkpoint.
  Sentence 2 is a different claim: *"Let's move this call into the two placed where
  `CommandResponseFromHTTPBody` is called (commandWebhook, DoCommandRequest)."* Every element is
  present — the `o.IsValid()` call inside `CommandResponseFromJSON` at :72-74, and exactly those two
  callers at `web/webhook.go:114` and `app/command.go:595`.

With the previously-found efcore T2, that is **three compound-thread errors out of the twenty
exclusion verdicts this corpus has ever made** — the measured error rate this nib argued from,
confirmed and slightly worse than the 1-of-3 figure it opened with.

The fifteen that stand were re-confirmed by **enumeration rather than argument**: grep counts for the
construct each thread discusses (`unquoteIdentifier` 0, `lower_bound` 0, `Invalid timestamp` 0,
`not detailed_conditions` 0, `properties_matched` as a field 0, `net/url` absent from a 100-line
file). Prometheus T7 — flagged here as resting on inference — now rests on the observation that
`261000` occurs exactly twice in the checkpoint test file, both inside a case the thread is not
describing.

Machinery: `annotate_thread_matchability.py --second-pass-worksheet` / `--second-pass` (worksheet is
blind to pass 1's reasoning by construction), `matchability_readings` on the thread records both
verdicts plus `matchability_resolution`, and `score_pooled.py` refuses a subject whose exclusions
carry only one reading. Verdict files committed as
`grading/matchability-second-pass-2026-08-20.json` per subject.

Write-up: `v2/analysis/GRADING-INTEGRITY-2026-08-20.md` §3.

## Acceptance

- [x] Every `matchable_at_checkpoint: false` verdict on a scored subject carries two independent readings
- [x] Disagreements are recorded, not silently resolved, and default toward matchable
- [x] The compound-thread rule is in the annotator prompt and in `METRICS.md`
- [x] `credited_to_unmatchable_thread` is empty on every scored subject

## Summary

**Completed 2026-08-20** — All 17 exclusions across the six scored subjects second-read, blind to the first pass's reasoning,
under two rules stated in advance: matchable if ANY claim targets present code, and disagreement
resolves toward matchable.

2 of 17 flipped — efcore T1 and mattermost T6 — both the compound-thread shape, both having silently
cost arms a legitimate hit. With the previously-found efcore T2 that is three such errors out of the
twenty exclusion verdicts this corpus has ever made, confirming the nib's argument and slightly
worsening its measured rate.

The fifteen that stand were re-confirmed by enumeration rather than argument (grep counts for the
construct each thread discusses). Prometheus T7, flagged in the nib as resting on inference, now
rests on an observation.

`annotate_thread_matchability.py --second-pass` records both readings on the thread, and
`score_pooled.py` refuses a subject whose exclusions carry only one.
