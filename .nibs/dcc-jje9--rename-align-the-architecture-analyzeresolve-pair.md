---
# dcc-jje9
version: 1
title: Rename + align the architecture analyze/resolve pair
status: todo
type: task
priority: normal
created_at: 2026-06-20T18:33:58Z
updated_at: 2026-06-20T18:33:59Z
parent: dcc-9olo
blocked_by:
    - dcc-owjh
order: aV
---

## Description
Rename `improve-codebase-architecture` → `architecture-review` and `handle-architecture-improvements` → `resolve-architecture-review`. Align to the analyze/resolve convention (analysis produces RFCs/decisions; resolve walks candidates → creates RFCs). Update all cross-references.

## Verification
- [ ] architecture-review + resolve-architecture-review skills present
- [ ] no improve-codebase-architecture / handle-architecture-improvements names remain
- [ ] resolve mirrors the analysis name per convention
