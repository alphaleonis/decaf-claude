---
# dcc-nh1y
version: 1
title: Grow work-items.md into the tracker-adapter contract
status: completed
type: task
priority: normal
created_at: 2026-06-20T19:42:51Z
updated_at: 2026-06-20T22:21:03Z
parent: dcc-e4ry
order: a0
---

## Description
Extend `conventions/work-items.md` from create-only into the full tracker-adapter contract the loop calls: `create`, `next-ready` (phase in dependency order), `read` (spec + acceptance), `set-status`, `close`+summary, `create-followup`. Define each op per backend (ado / github / nibs / markdown), designing to the WEAKEST backend — `next-ready` must be satisfiable by convention where native deps are absent (GitHub: sub-issues / parent ordering / labels). See #dcc-c7gu.

## Verification
- [ ] each contract op documented with a per-backend implementation (ado / github / nibs / markdown)
- [ ] next-ready has a documented convention fallback for trackers without native deps
- [ ] no loop logic assumes a specific backend

## Summary

Grew conventions/work-items.md into the 6-op tracker-adapter contract (create / next-ready / read / set-status / close+summary / create-followup), implemented per backend (nibs / ado / github / markdown). next-ready is native in nibs (--ready) and ado (WIQL), and satisfied by convention on GitHub (phase:N labels + sub-issues + 'Blocked by #m') and Markdown — designed to the weakest backend. No loop logic assumes a backend.
