---
# dcc-hv1y
version: 1
title: reach=narrow should treat deleted lines as in-scope changes
status: todo
type: bug
priority: high
created_at: 2026-08-10T12:15:14Z
updated_at: 2026-08-10T17:55:47Z
order: zzzz
---

`reach=narrow` is described as "high-confidence defects **introduced by the changed lines**". That
wording reads as pointing at added code, and a regression-by-omission — where the defect is what the
diff REMOVED — sits awkwardly against it.

Subject 9 (kubernetes/kubernetes#130837) is exactly that shape: the escaped bug is that
`NewNodeManager` made NodeIP acquisition fatal, removing the deleted `getNodeIPs` backoff and its
localhost fallback. You find it by reasoning about behavior that is no longer there.

`ours-bugs` (the only `reach=narrow` preset) missed it in both clean repeats. It is NOT established
that narrow reach caused the miss — the finding never appeared even in "Considered But Not Flagged",
so nothing recorded tiering it down, and the reviewers ran on haiku which is a competing explanation
(see [[dcc-2cxq]] analysis). But the r1 report does show narrow reach discarding an adjacent finding
with the note "pre-existing, out of reach under `reach=narrow`", so the axis is demonstrably shedding
work in this region.

## Acceptance

- [ ] The `reach` axis definition states explicitly that deleted lines are changed lines, and that
      behavior removed by the diff is in scope at every reach level
- [ ] Reviewer briefs at `narrow` ask what the change removed, not only what it added
- [ ] The distinction is drawn between "pre-existing defect the diff did not touch" (out of scope at
      narrow, correctly) and "behavior the diff deleted" (in scope at every level)
- [ ] Re-check `ours-bugs` on a v2 subject once [[dcc-vkeh]] lands, and record the result either way —
      a continued miss points at the model tier instead. (Was: re-run on subject 9 under v1. Subject
      9's v1 cells are invalidated, and its v2 checkpoint at push #2 carries only 2 key entries.)
