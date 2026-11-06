---
# dcc-7yt7
version: 1
title: 'batch-dev: no check-in pauses after approval except before parallel clusters and on merge conflicts'
status: completed
type: task
created_at: 2026-11-06T12:10:21Z
updated_at: 2026-11-06T12:10:50Z
order: zzzzzzzzz
---

## Description

In interactive mode, batch-dev told the conductor to pause "at each cluster boundary" and to plan "explicit check-in points". In a lotsen run (2026-11-06), the conductor planned a stop partway through a single series cluster and asked "Shall I continue?" at 5 of 8 nibs. The description promises ONE approval gate.

After approval, the run should stop only where a reply can change something: before launching a parallel, workflow or team cluster, and on a merge conflict. A failed nib is parked and the run continues (Failure handling), so it is not a stop.

## Verification

- [x] SKILL.md lines on check-ins (phase overview, 4c, Phase 5 template, Phase 6 Common rules, unattended list) describe the same stop points
- [x] Description and README match
- [x] `scripts/check-skill-references.sh` passes

## Summary

**Completed 2026-11-06** — Interactive batch-dev now waits after approval only before a parallel/workflow/team cluster and on a merge conflict; the description, Phase 5 template and README match.
