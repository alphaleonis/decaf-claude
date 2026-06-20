---
# dcc-1wuy
version: 1
title: 'auto-deliver: autonomous whole-plan delivery driver'
status: todo
type: feature
priority: normal
created_at: 2026-06-20T18:27:56Z
updated_at: 2026-06-20T19:42:52Z
parent: dcc-e4ry
blocked_by:
    - dcc-c7gu
    - dcc-nh1y
    - dcc-cwjz
    - dcc-o89j
    - dcc-s4zu
order: aw
---

The autonomous plan→execute→reflect loop driver (see #dcc-kk29 "Future" section and vnext.md). Lives in **decaf-build**.

**DRAFT — blocked on the plan plugin.** It needs unattended `breakdown-phase` and `close-plan`, executable acceptance criteria, and a verify / learn / replan step. Do not implement until the plan-plugin work lands.

## Scope sketch
1. select next ready phase (nibs `--ready` + topo order)
2. `breakdown-phase` (unattended) → feature nibs
3. `batch-dev` (unattended, scoped to the phase)
4. reflect = verify-and-fix + `close-plan` (reconcile) + learn + replan
5. merge phase; loop until the plan is complete

## Dependencies
- decaf-quality (inherited via build)
- decaf-plan (unattended breakdown-phase / close-plan) — not yet started
