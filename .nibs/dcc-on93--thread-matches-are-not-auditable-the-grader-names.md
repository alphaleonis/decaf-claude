---
# dcc-on93
version: 1
title: 'Thread matches are not auditable: the grader names an index but never quotes what it matched'
status: todo
type: bug
created_at: 2026-08-20T18:42:58Z
updated_at: 2026-08-20T18:43:54Z
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

## Acceptance

- [ ] The grader prompt requires a quote from the matched thread
- [ ] `score_pooled.py` refuses a `matches-thread` verdict with no `matched_thread_quote`
- [ ] The quote is checked to actually appear in that thread's body — a fabricated quote must fail
- [ ] Existing `matches-thread` verdicts on the six scored subjects are backfilled or re-graded
