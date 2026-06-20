---
# dcc-s8di
version: 1
title: decaf-build plugin
status: todo
type: epic
priority: normal
created_at: 2026-06-20T18:27:55Z
updated_at: 2026-06-20T18:27:57Z
parent: dcc-33j0
blocked_by:
    - dcc-2ia9
order: aV
---

## Objective
Rebuild decaf-dev as **decaf-build** (create new behavior): repoint its review calls at decaf-quality and declare a dependency on it. Port tdd, auto-tdd, auto-dev, batch-dev. `auto-deliver` is drafted but deferred (needs plan).

## Acceptance Criteria
- [ ] decaf-build scaffolded from old/decaf-dev; declares dependency on decaf-quality
- [ ] tdd, auto-tdd, auto-dev, batch-dev ported; review calls → /decaf-quality:
- [ ] README + metadata updated; marketplace entry added

## Scope Boundaries
Touches: decaf-build/ (new), marketplace.json. Source: old/decaf-dev/. Off limits: quality internals, plan/core/memory/protection. auto-deliver implementation deferred (see its draft feature).
