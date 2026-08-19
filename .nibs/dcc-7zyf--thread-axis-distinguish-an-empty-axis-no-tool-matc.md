---
# dcc-7zyf
version: 1
title: 'Thread axis: distinguish an EMPTY axis (no tool matched anything) from tools performing badly'
status: todo
type: bug
priority: normal
created_at: 2026-08-19T17:11:29Z
updated_at: 2026-08-19T17:12:00Z
parent: dcc-ho2w
order: zzV
---

`grafana-grafana-117615` scores **0.00 thread recall for every arm**, under both grading passes. That
is not a measurement of the tools. It is an axis with nothing in it, and it currently looks identical
to "every tool did badly".

## The subject

7 admitted threads, of which **2 are human** (the other 5 are Copilot; bot threads score the separate
`incumbent_agreement` axis). Corpus coverage is **0 of 2** — no tool matched either thread in any
cell, under either pass (`scoring/thread_band.py`).

Both human threads, verbatim:

> **idx 4**, `sqlCompletionProvider.ts:27` — "I don't think wrapping this in both
> `quoteIdentifierIfNecessary` and `unquoteIdentifier` is the right way to go here but I'm not super
> familiar with this area of the code. I thought when I reviewed this before that you hadn't done
> this so I'm wondering about the change here."

> **idx 5**, `SqlExpr.tsx:81` — "`table` is a reserved keyword, let's use something else
> (`default_table`? or similar?) to avoid an error when the expression runs."

**Neither is a defect report.** The first is a reviewer thinking out loud and saying so; the second
is a naming request about fixture data. No review tool will produce either, and not because it missed
something — there was no finding in them to miss.

METHODOLOGY-v2 already half-states this: the axis is defensible as "what expert reviewers chose to
say", never as "what unaided humans found". Reviewers say plenty that is not a defect. On a subject
with 10 threads that averages out. On one with 2, it can empty the axis completely.

## Why it matters

- **It cannot discriminate.** Every arm scores identically, so the number carries no information
  about any tool.
- **It still moves averages.** Pooled across subjects it contributes 0.00 for everyone, lowering
  every average by the same amount and making the corpus look as though tools match human review
  worse than the evidence supports. The cause is subject composition, not tool quality.
- `threads.human_axis_thin` fires at n<=2 and correctly marks this subject, but "thin" and "empty"
  are different failures and currently read the same.

## What to change

- `score_pooled.py`: emit `threads.human_axis_empty` when corpus coverage is 0 — no tool matched any
  human thread — separately from `human_axis_thin`. An empty axis is not a score of zero.
- Any view (`compare_arms.py`, [[dcc-p3wg]]) must render an empty axis as **n/a with the reason**,
  never as 0.00, and must exclude it from a pooled figure rather than averaging it in.
- Record per subject WHY the axis is empty. Here: both human threads are non-defect comments. That
  is a property of the subject, and a reader needs it to interpret the 0.00 they will otherwise see
  in the raw data.
- Consider for subject selection ([[dcc-ryo4]]): screening counts human threads but not whether they
  contain defect statements. A subject can pass the density bar on two comments that no tool could
  ever match.

## Acceptance

- [ ] `human_axis_empty` emitted and tested, distinct from `human_axis_thin`
- [ ] Views render it as n/a-with-reason and exclude it from pooled thread figures
- [ ] grafana-117615's reason recorded beside the subject
- [ ] Decide whether the screen should require human threads that state a defect, not merely exist
