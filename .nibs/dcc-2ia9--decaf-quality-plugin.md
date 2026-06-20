---
# dcc-2ia9
version: 1
title: decaf-quality plugin
status: todo
type: epic
created_at: 2026-06-20T18:27:55Z
updated_at: 2026-06-20T18:27:55Z
parent: dcc-33j0
order: a0
---

## Objective
Rename the current decaf-review (ex decaf-exp) to **decaf-quality** and absorb the coverage and refactor quality pairs, aligned to the plugin's consolidation / severity / persona conventions.

## Acceptance Criteria
- [ ] Plugin renamed decaf-review → decaf-quality (identity, internal refs, marketplace)
- [ ] coverage-review + resolve-coverage-review present, aligned to conventions
- [ ] refactor + resolve-refactor present (with structural-analyst, coherence-analyst agents)
- [ ] README + metadata updated; no outward dependencies (standalone)
- [ ] All skills invoke as /decaf-quality:*

## Scope Boundaries
Touches: decaf-quality/ (current decaf-review/), marketplace.json. Source material: old/decaf-review/. Off limits: build plugin, plan/core/memory/protection.
