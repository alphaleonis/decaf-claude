# Human thread axis: EMPTY (nibs dcc-7zyf, dcc-hw48)

REASON: both admitted human threads target code that does not exist at the checkpoint, so the human
denominator is **0** — there was never a question for a review tool to answer.

7 admitted threads, of which **2 are human** (the other 5 are Copilot, scoring the separate
`incumbent_agreement` axis). Both human threads are now stamped
`matchable_at_checkpoint: false`, so `score_pooled.py` emits `denominator_human: 0` and
`thread_recall: null`.

Both human threads, verbatim:

- `sqlCompletionProvider.ts:27` — "I don't think wrapping this in both `quoteIdentifierIfNecessary`
  and `unquoteIdentifier` is the right way to go here but I'm not super familiar with this area of
  the code. I thought when I reviewed this before that you hadn't done this so I'm wondering about
  the change here."
- `SqlExpr.tsx:81` — "`table` is a reserved keyword, let's use something else (`default_table`? or
  similar?) to avoid an error when the expression runs."

## Why the reason changed on 2026-08-20

This note previously said the axis is empty because neither thread states a defect — one is a
reviewer thinking out loud and saying so, the other a naming request. Both descriptions are still
accurate, but they are not the operative reason, and the difference matters.

Verified against the checkpoint checkout:

- `unquoteIdentifier` occurs **0 times** under `public/app/features/expressions/`. The double-wrapping
  the first thread objects to does not exist; the line reads
  `completion: quoteIdentifierIfNecessary(refId.label || refId.value || '')`.
- `default_table` occurs **0 times** there, and `SqlExpr.tsx:81` is a bare
  `${quoteIdentifierIfNecessary(vars[0])}` with no fallback literal to rename.

Both threads were written against `913e505e`, after the checkpoint. The reviewer is reviewing changes
made *since* the snapshot the tools were shown — the first thread says so outright ("I thought when I
reviewed this before that you hadn't done this").

**So the old framing put the emptiness in the numerator and the new one puts it in the denominator.**
Under the old reading, four arms each scored 0.00 on a real question; a naive pool therefore dragged
every average down as though four arms had failed. Under the corrected reading there is no question:
`n = 0`, recall is `null`, and the subject contributes nothing to the axis in either direction.

## Consequence for any figure

`score_pooled.py` emits `threads.human_axis_empty: true` and `denominator_human: 0`; every arm's
`thread_recall` on this subject is `null`, not `0.000`. A view must render n/a with this reason.
Never substitute 0 for null here — that is the error this note exists to prevent, and it is the
second time the same subject has produced it.

This subject remains fully valid on the pooled and defect axes, and its **bot** axis is intact: all
5 Copilot threads are matchable, so `incumbent_agreement` is a real measurement here.
