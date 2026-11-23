---
# dcc-tpwx
version: 1
title: Refresh the conventions indexes, ship artifacts.md in decaf-build, drop nib ids from skill prose
status: completed
type: task
created_at: 2026-11-23T21:31:30Z
updated_at: 2026-11-23T21:31:36Z
order: zzzzzzzzzV
---

The conventions indexes had gone stale, decaf-build referenced a convention it did not ship, and skill prose carried nib ids the model cannot use.

- [x] `conventions/CLAUDE.md`: drop the QR / planner / doc-sync wording, describe `severity.md` as MoSCoW plus recoverability, add rows for `code-review-consolidation.md`, `coverage-config.md`, `pr-etiquette.md` and `persona-authoring.md`
- [x] `conventions/code-quality/CLAUDE.md`: drop the QR / planner wording
- [x] Symlink `decaf-build/conventions/artifacts.md`, which `auto-deliver/artifact-layout.md` refers to
- [x] Remove nib ids and decision history from code-review, auto-code-review, artifact-layout and subagent-briefs

## Summary

**Completed 2026-11-23** — Indexes refreshed, artifacts.md linked into decaf-build, nib ids removed from skill prose. security.md is still read by no skill or agent, so it stays unindexed.
