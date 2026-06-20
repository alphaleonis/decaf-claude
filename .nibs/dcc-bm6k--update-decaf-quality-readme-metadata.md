---
# dcc-bm6k
version: 1
title: Update decaf-quality README + metadata
status: completed
type: task
priority: normal
created_at: 2026-06-20T18:27:56Z
updated_at: 2026-06-20T20:22:04Z
parent: dcc-2ia9
blocked_by:
    - dcc-74g6
order: as
---

## Description
Document the full decaf-quality skill set and update plugin metadata + marketplace; confirm it declares no outward dependencies (standalone install).

## Verification
- [x] README lists all skills + agents
- [x] plugin.json declares no dependencies
- [x] marketplace description accurate

## Summary of Changes
- Rewrote README: broadened from "code review" to the full **code-quality** plugin (three capabilities — review, coverage, refactoring). Grouped Skills by capability with usage; added a standalone **Analysis agents** section (coverage-reviewer, structural-analyst, coherence-analyst) distinct from the code-review roster; added a "how the three capabilities score" note (review+coverage = severity×anchors+gate; refactor = impact×effort stars); Output now lists `.code-reviews/` + `.refactoring-plans/`.
- plugin.json: broadened description, added `coverage`/`refactoring` keywords; confirmed no `dependencies` key (standalone).
- marketplace.json: broadened the decaf-quality description + keywords/tags.
