---
# dcc-7zyf
version: 1
title: 'Thread axis: distinguish an EMPTY axis (no tool matched anything) from tools performing badly'
status: completed
type: bug
priority: normal
created_at: 2026-08-19T17:11:29Z
updated_at: 2026-08-19T17:19:43Z
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

- [x] `human_axis_empty` emitted by score_pooled.py and tested (`t_empty_human_axis_is_distinct_from_thin`). Fires on grafana-117615 only; immich-28886 is thin-but-not-empty (1 of 2 hit), so the two flags discriminate.
- [x] `thread_band.py` suppresses the per-tool table for an empty axis and prints n/a plus the recorded reason instead of a column of 0.00s.
- [x] `pooled/grafana-grafana-117615/THREAD-AXIS-NOTE.md`, with both thread bodies verbatim and a machine-readable `REASON:` line the view reads.
- [x] DECIDED: **no.** Requiring human threads that state a defect would select FOR matchability and inflate thread recall corpus-wide — a worse validity problem than an occasional empty axis, and it would quietly convert the miss detector into a measure of how findable the corpus was chosen to be. The real defect here is different: grafana-117615 has 3 human threads in total and 2 admitted, so it never met a >=5 HUMAN bar. It passed on a count that included bots — the [[dcc-qwt3]] problem. Fix the screen to count ADMITTED HUMAN threads, which METHODOLOGY-v2 already states as the criterion, and accept that some subjects will still land empty; flag them rather than select against them.

## Summary

**Completed 2026-08-19** — An empty thread axis is now distinguishable from tools performing badly.

`score_pooled.py` emits `threads.human_axis_empty` when no tool matched ANY human thread, separate
from `human_axis_thin`. It fires on grafana-117615 alone; immich-28886 is thin but not empty (1 of 2
hit), so the flags discriminate. Tested.

`thread_band.py` renders an empty axis as n/a with the recorded reason and suppresses the per-tool
table entirely, rather than printing a column of 0.00s that cannot separate arms.
`pooled/grafana-grafana-117615/THREAD-AXIS-NOTE.md` carries both thread bodies verbatim so a reader
can see why: one is a reviewer saying they are unfamiliar with the area, the other a naming request
about fixture data. Neither states a defect, so there was nothing for a tool to miss.

Decided against requiring defect-stating human threads at screen time: that selects FOR matchability
and would inflate thread recall corpus-wide, converting the miss detector into a measure of how
findable the corpus was chosen to be. The actual defect is that grafana-117615 has 3 human threads
total and 2 admitted, so it never met a >=5 HUMAN bar — it passed on a count that included bots,
which is dcc-qwt3. The screen should count admitted HUMAN threads; empty axes that still occur get
flagged, not selected against.
