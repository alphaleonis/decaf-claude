---
# dcc-09q5
version: 1
title: Port coverage-review + add resolve-coverage-review
status: todo
type: task
priority: normal
created_at: 2026-06-20T18:27:56Z
updated_at: 2026-06-20T18:27:57Z
parent: dcc-2ia9
blocked_by:
    - dcc-wx8i
order: aV
---

## Description
Bring `coverage-review` and the `coverage-reviewer` agent from old/decaf-review into decaf-quality. Rename `handle-coverage` → `resolve-coverage-review`. Align both skills and the agent to the new plugin's consolidation, severity, and persona-authoring conventions.

## Verification
- [ ] coverage-review + resolve-coverage-review skills present
- [ ] coverage-reviewer agent present, persona aligned
- [ ] skills follow the consolidation / severity conventions
- [ ] invocations namespaced /decaf-quality:
