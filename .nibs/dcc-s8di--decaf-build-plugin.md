---
# dcc-s8di
version: 1
title: decaf-build plugin
status: completed
type: epic
priority: normal
created_at: 2026-06-20T18:27:55Z
updated_at: 2026-06-20T20:33:49Z
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

## Summary

decaf-build complete: scaffolded from decaf-dev with a dependency on decaf-quality; ported tdd (clean), auto-tdd + auto-dev (review calls repointed to /decaf-quality:auto-code-review), and batch-dev (repointed + generalized off NZBrowse specifics + a Face-2 --unattended stub); README added. The auto-deliver loop driver lives under the Face-2 epic, not here.
