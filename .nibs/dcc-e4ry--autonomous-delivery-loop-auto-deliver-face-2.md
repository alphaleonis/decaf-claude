---
# dcc-e4ry
version: 1
title: Autonomous delivery loop (auto-deliver) — Face 2
status: completed
type: epic
priority: normal
created_at: 2026-06-20T19:42:51Z
updated_at: 2026-06-20T22:21:14Z
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

## Current Focus

Completed dcc-1wuy: Implemented decaf-build:auto-deliver — the autonomous SELECT→BREAKDOWN→EXECUTE→VERIFY→RECONCILE→LEARN→REPLAN→MERGE loop, per dcc-c7gu exactly. No gate-stops (only plan-complete or escalation exits); tracker-agnostic via the adapter contract; composes breakdown-phase/batch-dev/close-out under --unattended; verify-and-fix/learn/replan as in-skill sub-routines; scope immutable (human-only cuts); driver owns tracker status in the main context. Build now depends on decaf-plan. Shipped in commit 7336757.

## Summary

Autonomous delivery loop (Face 2) delivered per dcc-c7gu. Enablement: work-items.md grown into the 6-op tracker-adapter contract (nh1y); ## Acceptance A+C hybrid convention emitted by the plan skills (cwjz); --unattended on breakdown-phase/batch-dev/close-out (o89j); .auto-deliver/ layout spec (s4zu). Driver: decaf-build:auto-deliver, no-stop loop composing those primitives, scope-immutable, tracker-agnostic (1wuy). Shipped on vnext in a4f47c9 (Phase A) + 7336757 (driver). Runs end-to-end against any supported tracker via the adapter; nibs verified as the reference backend.
