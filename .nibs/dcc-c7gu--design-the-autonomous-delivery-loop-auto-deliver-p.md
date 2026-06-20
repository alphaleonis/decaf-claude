---
# dcc-c7gu
version: 1
title: Design the autonomous delivery loop (auto-deliver + plan-side machinery)
status: todo
type: research
created_at: 2026-06-20T18:33:58Z
updated_at: 2026-06-20T18:33:58Z
parent: dcc-33j0
order: as
---

## Question
How should the autonomous plan→execute→reflect loop (`auto-deliver`) work end-to-end, and what plan-side machinery does it need? Resolve the open design questions BEFORE implementing Face 2 of decaf-plan or the `auto-deliver` driver (#dcc-1wuy). Context: `vnext.md`, the layout research in #dcc-kk29.

## Findings
_TBD._

## Decision
Open questions to resolve (the executable-acceptance one is the keystone):
1. **Executable acceptance criteria** — convention embedded in nib bodies, a separate criteria file, or a verify subagent that interprets narrative criteria? Nothing downstream is trustworthy without this.
2. **verify-and-fix** — a sub-routine of `auto-deliver` vs. a standalone skill; fix-now vs. defer posture (inverts today's `close-plan`).
3. **learn step** — write to CLAUDE.md/docs vs. erinra (decaf-memory, deferred); per-phase or per-plan?
4. **replan** — extend `close-plan` vs. fold into `auto-deliver`.
5. **unattended modes** — flags on `breakdown-phase` / `batch-dev` vs. separate skill variants.

Cross-plugin shape: `auto-deliver` (build) orchestrates → `breakdown-phase` / `close-plan` (plan) + `code-review` (quality) + learn (memory).

## Follow-ups
_TBD — Face 2 implementation tasks and un-drafting `auto-deliver` (#dcc-1wuy) come out of this design._
