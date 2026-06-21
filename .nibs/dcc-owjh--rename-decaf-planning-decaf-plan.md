---
# dcc-owjh
version: 1
title: Rename decaf-planning → decaf-plan
status: completed
type: task
priority: normal
created_at: 2026-06-20T18:33:58Z
updated_at: 2026-06-20T21:46:16Z
parent: dcc-9olo
order: a0
---

## Description
Create decaf-plan from old/decaf-planning: directory, plugin.json `name`, internal `/decaf-planning:` refs → `/decaf-plan:`, README title, and the marketplace.json entry (source path + name).

## Verification
- [ ] `grep -r 'decaf-planning' decaf-plan/` returns nothing
- [ ] plugin.json name = decaf-plan
- [ ] marketplace.json entry points at ./decaf-plan

## Summary

Scaffolded decaf-plan from old/decaf-planning: plugin.json name=decaf-plan, all /decaf-planning: -> /decaf-plan: refs, README, marketplace.json entry. work-items.md is referenced via a plugin-local symlink into repo-root conventions/ (not a copy), per the conventions-symlink decision.
