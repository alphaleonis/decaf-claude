---
# dcc-hw48
version: 1
title: 'Thread admission has no temporal check: post-checkpoint threads inflate every subject''s recall denominator'
status: completed
type: bug
priority: high
created_at: 2026-08-20T16:45:21Z
updated_at: 2026-08-20T19:49:01Z
parent: dcc-ho2w
order: zzw
---

Thread admission tests only **line position**: `admission_reason` is one of "line inside a changed
hunk at the checkpoint" / "line outside every changed hunk" / "file absent from the checkpoint diff".
Nothing checks that the code a thread *discusses* exists at the checkpoint. So a thread written weeks
later, against a commit the reviewer under test never saw, is admitted whenever its line happens to
land inside a changed hunk.

## Measured on PostHog-posthog-55149 ([[dcc-fm7x]])

- checkpoint `9b0f84471e9d`, dated 2026-04-17. PR merged 2026-05-06.
- **34 of 35 admitted threads were created after the checkpoint.** Exactly **1** has
  `against_commit == checkpoint`. The admitted set spans **12 distinct `against_commit` values**.
- The blind grader (pass 2), unprompted, reported 10 admitted threads as structurally unmatchable
  because they discuss code introduced later. Verified by reading them:

| thread | origin | why unmatchable at the checkpoint |
|---|---|---|
| T59 | human | "The lower_bound clamp regressed in 6effa89f" — a later commit |
| T69 | human | "The clamp is back" — the reintroduction is later still |
| T64 | human | reviews a CodeQL fix applied after the checkpoint |
| T34 | human | cites `test_test_evaluation_with_timestamp`, added later |
| T65 | human | `properties_matched` "was added" — after the checkpoint |
| T53 | human | a comment the grader judged absent at the checkpoint |
| T0, T55, T56, T57 | bot | CodeQL/scanner findings on later revisions |

- **Effective human denominator: 14, not 20 — a 30% inflation.** Every arm's `thread_recall` on this
  subject is deflated by the same factor, so the comparison between arms survives, but the absolute
  recall figure does not.

Note the converse is NOT true: post-checkpoint creation alone does not make a thread unmatchable.
T43 (2026-04-28) describes the five-field reconstruction copy, which exists at the checkpoint and was
found by 6 of 7 cells. The test is whether the discussed code is present, not when the comment was
written.

## Why this is corpus-wide, not a PostHog quirk

The admission rule is shared. Any subject whose PR received review over several pushes will admit
threads about code the checkpoint predates — and the checkpoint is deliberately chosen as "the commit
the earliest review comment was written against", which maximizes the number of later pushes. Every
`thread_recall` and `incumbent_agreement` figure already computed for the five scored subjects rests
on a denominator built this way and needs re-deriving.

This is also the harness's recurring shape once more: an inflated denominator is indistinguishable
from a tool that missed more, and it silently penalizes every arm equally, so nothing looks wrong.

## Fix

- Admission needs a **presence test**, not only a position test: does the hunk/line the thread
  addresses exist at the checkpoint, and does the thread's substance reference constructs present
  there? The cheap mechanical half is `against_commit` — a thread whose `against_commit` is not an
  ancestor-or-equal of the checkpoint should be flagged for review rather than silently admitted.
- Emit an `unmatchable_at_checkpoint` flag per thread and exclude those from the recall denominator
  while still reporting them, so the exclusion is visible rather than assumed.
- Re-derive the thread axis for all five previously scored subjects and restate any published figure.

## Acceptance

- [ ] `threads.json` carries a per-thread presence/temporal verdict, not only `admission`
- [ ] `score_pooled.py` excludes unmatchable threads from the denominator and reports the count it dropped
- [ ] PostHog-posthog-55149 reported with n=14 human, and the 6 exclusions named
- [ ] The five previously scored subjects re-derived; any moved figure restated in its write-up
- [ ] [[dcc-fm7x]]'s "20 human threads" claim corrected to the effective denominator

## Summary

**Completed 2026-08-20** — Reconciled — the machinery had landed and the nib's figures were the stale part.

Verified against the code and today's re-score:
- `threads.json` carries `matchable_at_checkpoint` per admitted thread, plus `matchable_reason` and
  (since dcc-fm8s) `matchability_readings` with both independent readings on every exclusion.
- `score_pooled.py` excludes them from the denominator and reports `excluded_unmatchable`,
  `excluded_unmatchable_human`, `denominator_human` and `denominator_bot`.
- PostHog-55149: the nib predicted n=14 with 6 exclusions. The completed annotation gives **n=13
  with 10 exclusions, 7 of them human** — of 20 admitted human threads. dcc-fm7x's write-up already
  carries "n=13" and "7 of 20 human threads excluded", so its claim is current, not stale.
- All six scored subjects re-derived today; every movement is named in
  `analysis/GRADING-INTEGRITY-2026-08-20.md`.

The cross-check this nib added, `credited_to_unmatchable_thread`, is empty on all six — and two of
the three contradictions it found turned out to be annotation errors of the compound-thread kind
rather than loose grading, which is the strongest evidence the check was worth building.
