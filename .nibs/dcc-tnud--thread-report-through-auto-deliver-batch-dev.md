---
# dcc-tnud
version: 1
title: Thread --report through auto-deliver + batch-dev
status: completed
type: task
priority: normal
created_at: 2026-07-04T18:40:42Z
updated_at: 2026-07-04T18:44:46Z
order: z
---

## Description

`--report` (added in #dcc-gdof to `code-review` / `auto-code-review` / `auto-dev` / `auto-tdd`) was
never threaded through the `auto-deliver` → `batch-dev` chain. `auto-deliver` forwards only `--review`
and `--base-branch` to `batch-dev`; `batch-dev` does not parse `--report` at all and its Phase 6a call
to `/decaf-quality:auto-code-review` omits it. Both links must change — adding it to `auto-deliver`
alone is a silent no-op.

Chain: auto-deliver EXECUTE → `batch-dev --unattended` → Phase 6a → `/decaf-quality:auto-code-review`
→ `/code-review`.

Decision (operator): full richness — batch-dev also captures each series nib's implementation Agent
usage as the implementation-phase record, matching auto-dev/auto-tdd report completeness.

Coverage limitation (inherent, documented not fixed): only batch-dev **series** clusters (Phase 6a)
call auto-code-review; fan-out / workflow / team clusters self-review inline in worktrees and cannot
emit a standard session report.

## Verification

- [x] batch-dev: `--report` in argument-hint + argument parsing
- [x] batch-dev Phase 6a: forward `--report` to auto-code-review + record impl Agent usage as impl-phase record
- [x] batch-dev: document the series-only coverage limitation
- [x] auto-deliver: `--report` in argument-hint
- [x] auto-deliver EXECUTE: forward `--report` to batch-dev
- [x] Reports land in `.decaf/session-reports/` (consistent with the other skills), one per series nib
- [x] Commit code + nib on main and push

## Summary of Changes

Threaded `--report` through the auto-deliver → batch-dev → auto-code-review chain (previously the
flag stopped at auto-dev/auto-tdd; batch-dev and auto-deliver both lacked it).

- **batch-dev/SKILL.md**: `--report` in argument-hint + argument parsing (item 5); Phase 6a forwards
  it to the series `auto-code-review` call AND records each series nib's implementation Agent usage
  as the implementation-phase record (full build-side accounting, matching auto-dev/auto-tdd); a
  series-only caveat after Phase 6a; a Phase 8 line listing reports written + uncovered clusters.
- **auto-deliver/SKILL.md**: `--report` in argument-hint; EXECUTE forwards it to batch-dev; STOP
  report lists session reports written + uncovered clusters.

Reports land in `.decaf/session-reports/` (consistent with the other skills). Inherent limitation
(documented, not fixed): only **series** clusters emit reports — fan-out/workflow/team clusters
self-review inline in worktrees and cannot call the main-context auto-code-review.
