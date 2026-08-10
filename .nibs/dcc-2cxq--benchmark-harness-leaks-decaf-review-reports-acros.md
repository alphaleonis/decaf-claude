---
# dcc-2cxq
version: 1
title: Benchmark harness leaks .decaf review reports across cells
status: in-progress
type: bug
priority: critical
created_at: 2026-08-06T14:58:35Z
updated_at: 2026-08-10T12:34:05Z
blocked_by:
    - dcc-ho2w
order: zzzy
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
- [ ] 27 cells re-run
- [ ] 9 subjects re-analyzed and synthesis regenerated

## Paused 2026-08-10
The harness fix, the cleanup, and the subject-9 re-grade are DONE. The remaining re-runs (12 cells
on subjects 1 and 5) are PAUSED pending the [[dcc-ho2w]] v2 decision.

Reason: v2 denies reviewers post-hoc PR context, which invalidates every cell again — including
subject 9's fresh runs. Spending ~$100 on subjects 1 and 5 now would buy numbers v2 supersedes.
Resume only if a contamination-only comparison is wanted for its own sake.
