---
# dcc-33j0
version: 1
title: 'vnext: decaf plugin rewrite'
status: completed
type: milestone
priority: normal
created_at: 2026-06-20T18:27:55Z
updated_at: 2026-06-20T22:21:32Z
order: aV
---

## Goal
Rewrite the decaf plugin suite for vnext: consistent naming and clearer boundaries — build = create new behavior, quality = improve existing code (behavior-preserving), plan = decide what/how. This milestone covers the **build** and **quality** plugins; plan, core, memory, and protection are deferred. Full decisions in #dcc-kk29.

## Current Focus

Completed dcc-e4ry: Autonomous delivery loop (Face 2) delivered per dcc-c7gu. Enablement: work-items.md grown into the 6-op tracker-adapter contract (nh1y); ## Acceptance A+C hybrid convention emitted by the plan skills (cwjz); --unattended on breakdown-phase/batch-dev/close-out (o89j); .auto-deliver/ layout spec (s4zu). Driver: decaf-build:auto-deliver, no-stop loop composing those primitives, scope-immutable, tracker-agnostic (1wuy). Shipped on vnext in a4f47c9 (Phase A) + 7336757 (driver). Runs end-to-end against any supported tracker via the adapter; nibs verified as the reference backend.

## Key Decisions
- Renames: decaf-dev→decaf-build, decaf-review→decaf-quality, decaf-planning→decaf-plan (deferred). Keep the `decaf-` prefix.
- Boundary: build adds new behavior; quality improves existing code; plan decides what/how.
- Naming: analysis = `<domain>-review`; resolve = `resolve-<analysis-name>` (replaces every `handle-*`); loop = `auto-<x>`; driver = `auto-deliver`.
- coverage and refactor move into quality. `auto-deliver` lives in build (drafted; blocked on plan).
- build depends on quality; quality is standalone.
- Conventions are shared via symlinks: one canonical copy at repo-root `conventions/`, each plugin symlinks it in (installed plugins can't read files outside their own dir). Documented in README.md + CLAUDE.md.

## Summary

vnext decaf plugin rewrite complete (within scope). Delivered: decaf-quality (review/coverage/refactor), decaf-build (tdd/auto-tdd/auto-dev/batch-dev/auto-deliver), decaf-plan (research/draft-spec/grill-me/draft-plan/breakdown-phase/close-out/explore-designs/architecture-review/resolve-architecture-review); consistent analyze/resolve + auto-* naming; conventions shared via symlinks (canonical at repo root); top-level docs rewritten; and the autonomous auto-deliver loop with its tracker-adapter contract, executable acceptance criteria, --unattended skills, and .auto-deliver/ state. Out of scope / still deferred: core (decaf), decaf-memory, decaf-protection (still under old/, keep their names). Branch vnext; not yet merged to main.
