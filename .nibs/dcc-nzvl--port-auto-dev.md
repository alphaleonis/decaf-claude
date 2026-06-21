---
# dcc-nzvl
version: 1
title: Port auto-dev
status: completed
type: task
priority: normal
created_at: 2026-06-20T18:27:56Z
updated_at: 2026-06-20T20:32:52Z
parent: dcc-s8di
blocked_by:
    - dcc-d61y
order: as
---

## Description
Port `auto-dev`; repoint review calls to /decaf-quality:; align naming.

## Verification
- [ ] auto-dev present; review calls → /decaf-quality:
- [ ] no /decaf-review: references remain


## Summary of Changes
Copied auto-dev from old/decaf-dev. Repointed `/decaf-review:auto-review` → `/decaf-quality:auto-code-review` (3×). No `/decaf-review:` refs remain.
