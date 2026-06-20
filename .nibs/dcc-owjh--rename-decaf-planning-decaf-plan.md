---
# dcc-owjh
version: 1
title: Rename decaf-planning → decaf-plan
status: todo
type: task
created_at: 2026-06-20T18:33:58Z
updated_at: 2026-06-20T18:33:58Z
parent: dcc-9olo
order: a0
---

## Description
Create decaf-plan from old/decaf-planning: directory, plugin.json `name`, internal `/decaf-planning:` refs → `/decaf-plan:`, README title, and the marketplace.json entry (source path + name).

## Verification
- [ ] `grep -r 'decaf-planning' decaf-plan/` returns nothing
- [ ] plugin.json name = decaf-plan
- [ ] marketplace.json entry points at ./decaf-plan
