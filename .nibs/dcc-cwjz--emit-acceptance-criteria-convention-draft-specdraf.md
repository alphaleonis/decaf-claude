---
# dcc-cwjz
version: 1
title: 'Emit ## Acceptance criteria (convention + draft-spec/draft-plan/breakdown-phase)'
status: completed
type: task
priority: normal
created_at: 2026-06-20T19:42:51Z
updated_at: 2026-06-20T22:21:03Z
parent: dcc-e4ry
blocked_by:
    - dcc-9olo
order: aV
---

## Description
Define the structured `## Acceptance` convention (each item a runnable check — command/test → expected result — OR a prose criterion tagged `manual`) and update draft-spec, draft-plan, and breakdown-phase to emit it into the work-item body so it travels across trackers. See #dcc-c7gu. Requires plan Face 1 skills to exist (#dcc-9olo).

## Verification
- [ ] `## Acceptance` format documented (runnable vs `manual`-tagged)
- [ ] draft-spec / draft-plan / breakdown-phase emit it
- [ ] criteria land in the work-item body (tracker-agnostic)

## Summary

Added conventions/acceptance-criteria.md defining the A+C hybrid ## Acceptance format ([run] cmd—expect vs [manual] prose). draft-spec, draft-plan, and breakdown-phase now emit it into the work-item body so it travels across trackers; auto-deliver verify reads it.
