---
# dcc-e4ry
version: 1
title: Autonomous delivery loop (auto-deliver) — Face 2
status: todo
type: epic
priority: normal
created_at: 2026-06-20T19:42:51Z
updated_at: 2026-06-20T19:44:47Z
parent: dcc-33j0
order: ay
---

## Objective
Build the autonomous plan→execute→reflect loop (`auto-deliver`) and the cross-cutting enablement it needs, per the design in #dcc-c7gu. The `auto-deliver` skill lands in decaf-build; the enablement touches shared conventions and the plan/build skills. Depends on Face 1 of the plan and build plugins (the skills the loop orchestrates must exist first).

## Acceptance Criteria
- [ ] work-items.md grown into the full tracker-adapter contract (create / next-ready / read / set-status / close+summary / create-followup), implementable on the weakest backend
- [ ] draft-spec / draft-plan / breakdown-phase emit `## Acceptance` criteria (runnable-where-possible, manual-tagged)
- [ ] breakdown-phase / batch-dev / close-out support `--unattended`
- [ ] `.auto-deliver/` artifact layout specified
- [ ] `auto-deliver` driver implemented (SELECT→BREAKDOWN→EXECUTE→VERIFY→RECONCILE→LEARN→REPLAN→MERGE) with verify-and-fix / learn / replan sub-routines
- [ ] runs end-to-end on at least nibs; tracker-agnostic via the adapter contract

## Scope Boundaries
Touches: conventions/work-items.md, decaf-plan + decaf-build skills (acceptance + --unattended), new decaf-build:auto-deliver, .auto-deliver/. Off limits: quality internals, core/memory/protection. Durable-lesson promotion to erinra is a deferred hook (memory plugin).
