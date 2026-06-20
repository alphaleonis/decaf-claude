---
# dcc-33j0
version: 1
title: 'vnext: decaf plugin rewrite'
status: in-progress
type: milestone
created_at: 2026-06-20T18:27:55Z
updated_at: 2026-06-20T18:27:55Z
order: aV
---

## Goal
Rewrite the decaf plugin suite for vnext: consistent naming and clearer boundaries — build = create new behavior, quality = improve existing code (behavior-preserving), plan = decide what/how. This milestone covers the **build** and **quality** plugins; plan, core, memory, and protection are deferred. Full decisions in #dcc-kk29.

## Current Focus
decaf-quality first (build depends on it), then decaf-build.

## Key Decisions
- Renames: decaf-dev→decaf-build, decaf-review→decaf-quality, decaf-planning→decaf-plan (deferred). Keep the `decaf-` prefix.
- Boundary: build adds new behavior; quality improves existing code; plan decides what/how.
- Naming: analysis = `<domain>-review`; resolve = `resolve-<analysis-name>` (replaces every `handle-*`); loop = `auto-<x>`; driver = `auto-deliver`.
- coverage and refactor move into quality. `auto-deliver` lives in build (drafted; blocked on plan).
- build depends on quality; quality is standalone.
