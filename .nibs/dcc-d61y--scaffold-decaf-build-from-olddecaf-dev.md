---
# dcc-d61y
version: 1
title: Scaffold decaf-build from old/decaf-dev
status: completed
type: task
priority: normal
created_at: 2026-06-20T18:27:56Z
updated_at: 2026-06-20T20:25:59Z
parent: dcc-s8di
blocked_by:
    - dcc-2ia9
order: a0
---

## Description
Create decaf-build from old/decaf-dev: plugin.json `name` → decaf-build, declare a `dependencies` entry on decaf-quality, and add the marketplace.json entry. No skill porting yet.

## Verification
- [x] decaf-build/ exists, plugin.json name = decaf-build
- [x] dependencies includes decaf-quality
- [x] marketplace.json has a decaf-build entry

## Summary of Changes
- Created `decaf-build/.claude-plugin/plugin.json` — name `decaf-build`, `"dependencies": ["decaf-quality"]` (its auto-* loops and the future auto-deliver call `/decaf-quality:`), broadened "build new functionality" description, `skills: "./skills"`.
- Added a `decaf-build` entry to `.claude-plugin/marketplace.json` (source `./decaf-build`).
- `decaf-build/skills/.gitkeep` placeholder so `./skills` resolves on the scaffold — removed once the first real skill (B2 tdd) lands.
- No skills ported yet (tdd / auto-tdd / auto-dev / batch-dev are the sibling tasks).
