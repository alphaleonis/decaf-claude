# Human thread axis: EMPTY (nib dcc-7zyf)

REASON: both admitted human threads are non-defect comments, so no review tool could match either — 0.00 is the correct answer to a question that cannot separate tools.

7 admitted threads, of which **2 are human** (the other 5 are Copilot, scoring the separate
`incumbent_agreement` axis). **Corpus coverage is 0 of 2** — no tool matched either thread, in any
cell, under either grading pass.

Both human threads, verbatim:

- `sqlCompletionProvider.ts:27` — "I don't think wrapping this in both `quoteIdentifierIfNecessary`
  and `unquoteIdentifier` is the right way to go here but I'm not super familiar with this area of
  the code. I thought when I reviewed this before that you hadn't done this so I'm wondering about
  the change here."
- `SqlExpr.tsx:81` — "`table` is a reserved keyword, let's use something else (`default_table`? or
  similar?) to avoid an error when the expression runs."

The first is a reviewer thinking out loud and saying so; the second is a naming request about
fixture data. Neither states a defect, so there is nothing in them for a review tool to have missed.

**Consequence for any figure.** Every arm scores 0.00 here, so the axis carries no information about
any tool — but pooled naively it still lowers every average by the same amount, making the corpus
look worse at matching human review than the evidence supports. `score_pooled.py` emits
`threads.human_axis_empty: true`; views must render n/a with this reason and exclude the subject
from pooled thread figures.

This subject remains fully valid on the pooled and defect axes. Only its human thread axis is empty.
