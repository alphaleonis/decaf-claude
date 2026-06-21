---
# dcc-o89j
version: 1
title: Add --unattended to breakdown-phase / batch-dev / close-out
status: completed
type: task
priority: normal
created_at: 2026-06-20T19:42:51Z
updated_at: 2026-06-20T22:21:03Z
parent: dcc-e4ry
blocked_by:
    - dcc-9olo
    - dcc-s8di
order: ak
---

## Description
Add a `--unattended` flag to `breakdown-phase`, `batch-dev`, and `close-out` that suppresses interactive gates / approval prompts / check-ins, so `auto-deliver` can call them non-interactively. One flag per existing skill — NOT separate variants. See #dcc-c7gu. Touches plan + build Face 1 skills.

## Verification
- [ ] --unattended on breakdown-phase, batch-dev, close-out
- [ ] flag suppresses all human gates; default (interactive) behavior unchanged
- [ ] no duplicate skill variants created

## Summary

Added a --unattended flag to breakdown-phase, batch-dev, and close-out (one flag per skill, no variants). Each skill documents exactly which human gates it suppresses; default interactive behavior unchanged. The auto-deliver loop passes the flag.
