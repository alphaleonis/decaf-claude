---
# dcc-d61y
version: 1
title: Scaffold decaf-build from old/decaf-dev
status: todo
type: task
priority: normal
created_at: 2026-06-20T18:27:56Z
updated_at: 2026-06-20T18:28:36Z
parent: dcc-s8di
blocked_by:
    - dcc-2ia9
order: a0
---

## Description
Create decaf-build from old/decaf-dev: plugin.json `name` → decaf-build, declare a `dependencies` entry on decaf-quality, and add the marketplace.json entry. No skill porting yet.

## Verification
- [ ] decaf-build/ exists, plugin.json name = decaf-build
- [ ] dependencies includes decaf-quality
- [ ] marketplace.json has a decaf-build entry
