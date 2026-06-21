---
# dcc-ftaf
version: 1
title: Consolidate skill artifact outputs under a common .decaf/ root
status: completed
type: task
priority: normal
created_at: 2026-06-20T22:22:45Z
updated_at: 2026-06-20T23:19:21Z
order: ak
---

Move the artifact documents that skills produce under a single common root directory instead of scattered top-level dot-dirs. E.g. `.decaf/code-reviews/` instead of `.code-reviews/`, and likewise for the other generated outputs (refactoring plans, coverage reports, plans, the auto-deliver loop's `.auto-deliver/`, etc.). One predictable root makes the outputs easy to find, gitignore, and reason about as a set.

## Context

Raised during the vnext rewrite (milestone dcc-33j0, now closed). Multiple plugins write artifacts to their own top-level locations: decaf-quality (code reviews, refactoring plans, coverage), decaf-plan (./plans/), decaf-build:auto-deliver (.auto-deliver/). Proposes a unifying convention — a `.decaf/` root with per-domain subdirs — to decide, then apply across the skills. Relates to the layout RFC dcc-kk29 (could not parent: it's a research nib).

## Summary

Consolidated all skill-generated artifacts under a single .decaf/ root: .code-reviews→.decaf/code-reviews, .refactoring-plans→.decaf/refactoring-plans, .auto-review-state.json→.decaf/auto-review/state.json, .architecture-improvements→.decaf/architecture-improvements, .grill-me→.decaf/grill-me, .auto-deliver→.decaf/auto-deliver. Added conventions/artifacts.md (canonical layout) + index row. plans/ kept visible at repo root (human deliverables, not tool scratch) per decision.
