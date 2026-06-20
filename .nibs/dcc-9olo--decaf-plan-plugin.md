---
# dcc-9olo
version: 1
title: decaf-plan plugin
status: todo
type: epic
created_at: 2026-06-20T18:33:58Z
updated_at: 2026-06-20T18:33:58Z
parent: dcc-33j0
order: aw
---

## Objective
Bring the planning plugin to parity with build/quality: rename decaf-planning → **decaf-plan**, apply the architecture analyze/resolve renames, and port/align the existing planning skills. **Face 1 only** — the autonomous-loop enablement (unattended modes, executable acceptance, verify/learn/replan) is owned by the loop design nib #dcc-c7gu, NOT here.

## Acceptance Criteria
- [ ] Plugin renamed decaf-planning → decaf-plan (identity, internal refs, marketplace)
- [ ] architecture-review + resolve-architecture-review in place (← improve-codebase-architecture / handle-architecture-improvements), aligned to the analyze/resolve convention
- [ ] research, write-a-prd, grill-me, prd-to-plan, breakdown-phase, close-plan, design-an-interface ported + aligned (as-is behavior; NO loop/unattended changes)
- [ ] README + metadata updated; all skills invoke as /decaf-plan:*

## Scope Boundaries
Touches: decaf-plan/ (new, from old/decaf-planning), marketplace.json. Off limits: loop enablement / unattended modes / auto-deliver (owned by #dcc-c7gu), build/quality internals, core/memory/protection.
