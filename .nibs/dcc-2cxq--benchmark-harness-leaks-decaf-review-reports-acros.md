---
# dcc-2cxq
version: 1
title: Benchmark harness leaks .decaf review reports across cells
status: completed
type: bug
priority: critical
created_at: 2026-08-06T14:58:35Z
updated_at: 2026-08-10T17:49:56Z
parent: dcc-ho2w
blocked_by:
    - dcc-ho2w
order: Zz
---

The per-subject checkout `repos/<subject_id>` is shared by all 16 cells of a subject.
`run_cell.sh`'s `ensure_repo()` returns early when the commit is already present, so the
`git checkout -q -f "$merge"` runs ONLY on first clone. Every later cell inherits the tree
as the previous cell left it, including the untracked `.decaf/code-reviews/` directory.

The decaf code-review skills have a recurring-findings cross-check (Step 7) that reads
`.decaf/code-reviews/`, so decaf-family cells read prior cells' review reports and use them
as corroboration — or as the sole source of a finding.

Evidence: `9__ours-bugs__r1`'s own report, on its High #1:
"Found by | orchestrator — surfaced via recurring-findings cross-check (Step 7) ...
Not surfaced by this wave's reviewers (a gap for bugs/models=low)."

Competitor tools write no such artifacts (0 CODE_REVIEW files in their bundles), so the
advantage is asymmetric and inflates decaf-family recall specifically.

Leak surface is exactly `.decaf/` — every `repos/*` checkout has exactly 1 dirty entry.

Contaminated: 18 new-variant cells (2-3 prior reports visible) + 9 `ours__r2` cells
(1 prior report). All `*__ours__r1` cells are clean. All 9 subject analyses and the
cross-subject synthesis are graded on contaminated data.

## Acceptance

- [x] `run_cell.sh` resets the tree per cell (checkout -f + clean -xfd), outside the early return
- [x] 27 contaminated cells invalidated back to `pending`, run dirs quarantined, metrics rows dropped
- [x] 9 contaminated subject analyses quarantined (answer keys preserved — they are tool-independent)
- [x] `repos/*` checkouts cleaned so the next run starts from a clean tree
- [x] ~~27 cells re-run~~ — SCRAPPED, superseded by [[dcc-ho2w]]
- [x] ~~9 subjects re-analyzed and synthesis regenerated~~ — SCRAPPED, superseded by [[dcc-5xad]]

## Paused 2026-08-10
The harness fix, the cleanup, and the subject-9 re-grade are DONE. The remaining re-runs (12 cells
on subjects 1 and 5) are PAUSED pending the [[dcc-ho2w]] v2 decision.

Reason: v2 denies reviewers post-hoc PR context, which invalidates every cell again — including
subject 9's fresh runs. Spending ~$100 on subjects 1 and 5 now would buy numbers v2 supersedes.
Resume only if a contamination-only comparison is wanted for its own sake.

## Superseded by benchmark v2
The harness fix, cleanup, quarantine, and the subject-9 re-grade are DONE and stand.

The two remaining acceptance items — "27 cells re-run" and "9 subjects re-analyzed" — are **superseded
by [[dcc-ho2w]]**. Those were v1 re-runs against v1 ground truth, and two of the first three subjects
audited under v2 turned out to have invalid ground truth. Re-running v1 cells would spend ~$390 to
produce numbers graded against defects that may not be in the reviewed diff.

Recommend scrapping both items rather than completing them. The v1 artifacts they would have produced
are covered by [[dcc-8tjr]] (archive) instead.

## Summary

**Completed 2026-08-10** — Closed with the two re-run items scrapped rather than completed.

**Delivered.** Root cause found and fixed: `run_cell.sh`'s `ensure_repo()` returned early once the
commit was present, so its `checkout -f` ran only on first clone and every later cell inherited the
previous cell's working tree — including the untracked `.decaf/code-reviews/` that the decaf skills
write to and read back via their recurring-findings cross-check. Competitor tools write nothing into
the tree, so the leak asymmetrically inflated decaf-family recall. Now reset per cell (`checkout -f`
+ `clean -xfd`), refusing to run (exit 77, cell left pending) if the tree is still dirty. Verified by
planting a report and watching it removed, then on a real cell whose bundle held only its own report.

Also: 27 contaminated cells invalidated and quarantined with evidence, 9 subject analyses quarantined
(frozen answer keys and review diffs preserved — they derive from the PR, not from tool output),
reasoning effort pinned and recorded per cell, and subject 9 re-graded clean.

**Scrapped.** The 27 v1 re-runs and 9 re-analyses. Under [[dcc-ho2w]] two of the first three subjects
audited had invalid ground truth — subject 11 indicts a defect that was fixed during review and is
absent from the merged code, and subject 2's fixture miscounts its own review threads. Re-running v1
cells would have spent ~$390 producing confident numbers graded against defects that may not be in
the reviewed diff. Superseded by the v2 milestone; the artifacts are covered by [[dcc-8tjr]].
