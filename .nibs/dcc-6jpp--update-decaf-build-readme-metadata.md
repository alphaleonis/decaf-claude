---
# dcc-6jpp
version: 1
title: Update decaf-build README + metadata
status: completed
type: task
priority: normal
created_at: 2026-06-20T18:27:56Z
updated_at: 2026-06-20T20:33:49Z
parent: dcc-s8di
blocked_by:
    - dcc-pa27
order: ay
---

## Description
Document decaf-build's skills and its dependency on decaf-quality in the README and plugin metadata.

## Verification
- [x] README lists skills + the decaf-quality dependency
- [x] marketplace description accurate

## Summary of Changes
- Created `decaf-build/README.md`: documents the 4 skills (tdd, auto-tdd, auto-dev, batch-dev), the **dependency on decaf-quality** (auto-installed; the auto-* loops + batch-dev call `/decaf-quality:auto-code-review`), and a "Coming in vNext" note for `auto-deliver`.
- Confirmed the marketplace `decaf-build` description is accurate (set during the scaffold).
