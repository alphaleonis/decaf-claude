---
# dcc-on93
version: 1
title: 'Thread matches are not auditable: the grader names an index but never quotes what it matched'
status: completed
type: bug
created_at: 2026-08-20T18:42:58Z
updated_at: 2026-08-20T19:26:10Z
parent: dcc-ho2w
order: zzzw
---

A `matches-thread` verdict records `matches_thread: <index>` and nothing about *why*. There is no way
to tell a substantive match from a same-line coincidence without re-reading both texts by hand.

## Why this matters now

[[dcc-hw48]] added `credited_to_unmatchable_thread`, which catches a cluster credited to a thread whose
subject does not exist at the checkpoint. That check found four contradictions on its first run and one
was a real error. But it only fires when the thread is **unmatchable**. A loose match onto a perfectly
**matchable** thread is invisible, and it inflates `thread_recall` with nothing to detect it.

The three open contradictions ([[dcc-tvk8]]) show the shape, and all three were only visible because
the thread happened to be unmatchable:

| cluster -> thread | what was credited | what the thread asked |
|---|---|---|
| `e15` -> T1 | `== true` used where an `is { }` pattern is the convention | use `is null` instead of `== null` (on a line with no `== null`) |
| `ma11` -> T6 | validation lives in the shared bidirectional decoder | use a context-carrying logger instead of the global one |
| `c108` -> T15 | Rust test edits set the new fields to inert values | no integration test covers overrides being dropped |

`ma11` is credited by four arms. Nothing about a loose match onto a matchable thread would have
surfaced at all.

Encouraging counter-evidence, which is why this is a low-cost fix rather than a redesign: the two
independent PostHog passes agreed on **24 of 24** thread matches, same index each time. The matching is
reproducible. What is missing is the ability to audit it.

## Fix

- Require a `matched_thread_quote` on every `matches-thread` verdict: the span of the thread body the
  cluster corresponds to. A grader that cannot quote the overlapping text has not matched it.
- `score_pooled.py` validates presence (it already refuses a real verdict with no `code_citation` —
  same principle, same reason: a claim that cannot point at its evidence is not evidence).
- A reviewer can then scan matches without re-reading the corpus, and the `e15`/`ma11`/`c108` class
  becomes visible whether or not the thread is matchable.

## Done 2026-08-20

All four criteria met, and the backfill found **two error classes nothing in the pipeline could see**.

**Four clusters were credited to REJECTED threads** — `e01`, `e13`, `e32` -> efcore T10 (a bot
thread about FIXME-vs-TODO naming) and `ma36` -> mattermost T3. The grader is only ever shown
admitted threads, so these indexes cannot name a legitimate match. Silent in both directions: recall
groups only admitted threads, so the credit bought the tool nothing there, while `precision` counted
the cluster as REAL on the strength of a match that did not exist. `score_pooled.py` now refuses this
as well as the missing quote. `e13`'s intended thread was recoverable (its rationale names
ExpressionType.Coalesce; exactly one thread says that — T14, a bot thread — and the quote verifies
there), so its index was corrected and its credit moved onto the incumbent axis where it belongs. The
other three had no corresponding span anywhere and lost their thread credit.

**One loose match onto a MATCHABLE thread** — `c048` -> PostHog T32, exactly the class this nib
predicted would be invisible. T32 is about `build_person_properties_at_time`; `c048` is about a
second unbounded scan in `person_existed_at_timestamp`. The shared span is a real correspondence of
defect class and remedy but not of target. Recorded rather than silently kept; it changes no number,
since T32 is already credited by `c007` and `c043`.

Scope discipline: where a thread credit was removed the cluster keeps the substance class the blind
grader gave it (all four were REAL, and became `valid-other`). Re-writing substance from the
auditor's chair is how a lenient judge is made — only the auditable defect was corrected, and each
carries a `thread_credit_note` saying so. A blind re-grade of those four is still owed.

Quote rule as implemented: non-empty, must occur in that thread's body (whitespace-collapsed,
case-folded), and >=12 characters or the whole body — real threads here go down to `Bool?` at five.

Write-up: `v2/analysis/GRADING-INTEGRITY-2026-08-20.md` §2. Edit set: `v2/analysis/quote-backfill-2026-08-20.json`.

## Acceptance

- [x] The grader prompt requires a quote from the matched thread
- [x] `score_pooled.py` refuses a `matches-thread` verdict with no `matched_thread_quote`
- [x] The quote is checked to actually appear in that thread's body — a fabricated quote must fail
- [x] Existing `matches-thread` verdicts on the six scored subjects are backfilled or re-graded
      (58 backfilled, 4 thread credits removed, 1 index corrected)

## Summary

**Completed 2026-08-20** — `matches-thread` now requires a `matched_thread_quote` that actually occurs in the named thread's
body, and `score_pooled.py` refuses the verdict without one. 58 existing matches backfilled across
the six scored subjects.

The backfill found two error classes nothing in the pipeline could see. Four clusters were credited
to REJECTED threads (efcore e01/e13/e32 -> T10, mattermost ma36 -> T3) — silent in both directions,
since recall ignored the credit while precision counted the cluster as REAL; that is now refused too.
And one loose match onto a MATCHABLE thread (PostHog c048 -> T32), exactly the class the nib
predicted would be invisible.

e13's intended thread was recoverable and its index corrected, which moved seven arms'
`incumbent_agreement` from 0.000 to 1.000 on efcore. The other three lost their thread credit but
keep the substance class the blind grader gave them — correcting substance from the auditor's chair
is how a lenient judge is made. A blind re-grade of those four is still owed.
