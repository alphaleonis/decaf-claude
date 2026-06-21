---
# dcc-ts2r
version: 1
title: Triage core agents (defer those not skill-dispatched)
status: draft
type: task
priority: deferred
created_at: 2026-06-21T09:09:40Z
updated_at: 2026-06-21T09:09:40Z
parent: dcc-f5dj
order: ay
---

## Description

LATER per decision: skip any agent not directly dispatched by a skill for now. Currently NONE of the core agents are dispatched by a new-plugin skill. Known intents to revisit: architect (plan — the review stack defers pre-implementation design to it), csharp-developer + go-developer (build implementers), technical-writer (build, post-feature docs), debugger (decaf-quality, pairs with problem-analysis). DROP planner (decided: redundant with draft-plan + breakdown-phase). Revisit once we decide whether/which skills dispatch each agent.

## Verification

[ ] each core agent placed or dropped
[ ] planner dropped
[ ] any agent that lands is dispatched by a skill (or kept as an explicitly-available specialist)
