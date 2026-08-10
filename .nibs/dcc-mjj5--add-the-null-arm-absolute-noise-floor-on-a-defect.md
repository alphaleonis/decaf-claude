---
# dcc-mjj5
version: 1
title: 'Add the null arm: absolute noise floor on a defect-free change'
status: todo
type: task
priority: high
created_at: 2026-08-10T19:20:06Z
updated_at: 2026-08-10T19:20:28Z
parent: dcc-ho2w
blocked_by:
    - dcc-595v
order: GV
---

The third instrument from [[dcc-595v]]. Pooled adjudication measures precision **relative to the
pool**, not to truth — every tool is scored against what the tools collectively found. That gives no
absolute scale, and no way to answer "how much of this output is noise in the first place?"

The null arm supplies it: run the roster on a **substantive change with no known defect**, where
approximately every finding is a false positive by construction. It needs no answer key and no
ground truth of any kind.

This matters because of what the v1 verdict distribution showed — of 98 distinct clusters on one
subject, only 6 were *wrong* while 58 were *trivial*. Tools fail by immateriality, not error, and
that is exactly what a null arm quantifies: given nothing to find, how much does each tool still say?

## Selecting a null subject

The hard part is establishing "no known defect" without it being a claim we cannot support:

- A substantive merged PR from a review-disciplined repo, old enough that a regression would have
  surfaced, with **no revert, no linked regression issue, and no follow-up fix** touching the same
  lines. Verify the last of these against the file's later history rather than assuming it.
- "No *known* defect" is the honest framing — findings are only *approximately* false positives.
  Where the judge rates a null-arm finding as genuinely valid, that is a real result worth keeping,
  not an error to suppress: it means the tool found something the project missed.
- Match size and application type to a scored subject so the noise floor is comparable rather than
  measured on a trivially different change.

## Acceptance

- [ ] Null-subject selection criteria written into METHODOLOGY-v2 section 3
- [ ] At least one null subject per size bucket (S/M/L), so the floor can be compared against cost
- [ ] Roster run against it and findings-per-cell reported per tool
- [ ] Genuinely-valid null findings reported separately rather than folded into the noise count
