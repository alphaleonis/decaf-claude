---
# dcc-hv1y
version: 1
title: reach=narrow should treat deleted lines as in-scope changes
status: completed
type: bug
priority: high
created_at: 2026-08-10T12:15:14Z
updated_at: 2026-08-20T19:48:36Z
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

## Summary

**Completed 2026-08-20** — "Introduced by the changed lines" now says added AND deleted lines, in all three places that carry
the rule: the `reach` axis table, the reviewer-brief blocks for `narrow` and `norm`, and
`solo-reviewer`'s scope rule (the `bugs` preset's only seat, and the only `reach=narrow` preset).

The distinction the nib asked for is stated explicitly: behavior the diff DELETED is in scope at
every reach level, because the change is what put the code in its current state; a pre-existing
defect the diff did not touch is out of scope at `narrow`, correctly. "No absences" means do not
survey the surrounding code — not ignore what the diff took away. The briefs now direct reviewers to
read the `-` side and ask what the old code did that the new code no longer does.

The kubernetes#130837 shape is recorded as the motivating case, with its caveat intact: it is
[Unverified] that narrow reach caused that miss, since the finding never appeared even under
Considered But Not Flagged and the model tier is a competing explanation.

Not done: the re-check acceptance item. `ours-bugs` on a v2 subject under the corrected wording needs
a cell run, which belongs with the full run (dcc-plsq), and the result must be recorded either way.
