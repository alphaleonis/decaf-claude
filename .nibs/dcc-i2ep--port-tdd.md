---
# dcc-i2ep
version: 1
title: Port tdd
status: completed
type: task
priority: normal
created_at: 2026-06-20T18:27:56Z
updated_at: 2026-06-20T20:27:27Z
parent: dcc-s8di
blocked_by:
    - dcc-d61y
order: aV
---

## Description
Port the `tdd` skill from old/decaf-dev into decaf-build; light cleanup to current conventions.

## Verification
- [x] /decaf-build:tdd present and consistent with conventions

## Summary of Changes
- Copied the `tdd` skill (SKILL.md + supporting docs: deep-modules, interface-design, mocking, refactoring, tests) from old/decaf-dev into `decaf-build/skills/tdd/`.
- No edits needed: tdd is fully self-contained — no cross-plugin references, no namespaced invocations; relative markdown links point to its own sibling docs (intact after the copy). Content already consistent with current conventions (tracer bullets, deep modules, vertical slices).
- Removed the `skills/.gitkeep` scaffold placeholder (a real skill is now present).
