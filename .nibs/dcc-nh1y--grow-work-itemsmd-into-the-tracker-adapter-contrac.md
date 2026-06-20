---
# dcc-nh1y
version: 1
title: Grow work-items.md into the tracker-adapter contract
status: todo
type: task
created_at: 2026-06-20T19:42:51Z
updated_at: 2026-06-20T19:42:51Z
parent: dcc-e4ry
order: a0
---

## Description
Extend `conventions/work-items.md` from create-only into the full tracker-adapter contract the loop calls: `create`, `next-ready` (phase in dependency order), `read` (spec + acceptance), `set-status`, `close`+summary, `create-followup`. Define each op per backend (ado / github / nibs / markdown), designing to the WEAKEST backend — `next-ready` must be satisfiable by convention where native deps are absent (GitHub: sub-issues / parent ordering / labels). See #dcc-c7gu.

## Verification
- [ ] each contract op documented with a per-backend implementation (ado / github / nibs / markdown)
- [ ] next-ready has a documented convention fallback for trackers without native deps
- [ ] no loop logic assumes a specific backend
