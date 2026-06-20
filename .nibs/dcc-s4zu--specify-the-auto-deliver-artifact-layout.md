---
# dcc-s4zu
version: 1
title: Specify the .auto-deliver/ artifact layout
status: completed
type: task
priority: normal
created_at: 2026-06-20T19:42:51Z
updated_at: 2026-06-20T22:21:03Z
parent: dcc-e4ry
order: as
---

## Description
Specify the on-disk `.auto-deliver/` layout (git-tracked) for loop state/artifacts: run state ("current phase"), per-phase reflection reports, `lessons.md`, context logs, verify output. Define file/dir naming and what each holds; note gitignore considerations. See #dcc-c7gu.

## Verification
- [ ] .auto-deliver/ layout documented (run state, reflection, lessons.md, context logs, verify output)
- [ ] git-tracking / gitignore decision noted

## Summary

Specified the .auto-deliver/ artifact layout (decaf-build/skills/auto-deliver/artifact-layout.md): state.json resume breadcrumb (not a mirror), lessons.md, per-phase reflection.md + raw verify/context logs. Git-tracks the durable artifacts, gitignores the regenerable logs.
