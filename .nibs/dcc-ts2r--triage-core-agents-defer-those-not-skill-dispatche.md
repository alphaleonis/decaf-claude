---
# dcc-ts2r
version: 1
title: Place core agents (keep 5, drop planner)
status: todo
type: task
priority: deferred
created_at: 2026-06-21T09:09:40Z
updated_at: 2026-06-21T10:00:13Z
parent: dcc-f5dj
order: ay
---

## Description

Place the core agents per the triage. Agents are auto-discovered from each plugin's `agents/` dir (no plugin.json key needed — cf. decaf-quality's 21 agents) and are independently invocable via Task even where no skill dispatches them yet.

KEEP (copy the agent .md into the target plugin's agents/ dir):
- architect -> decaf-plan/agents/ (feature-architecture blueprints; decaf-quality's design-reviewer defers pre-implementation design to it)
- csharp-developer -> decaf-build/agents/ (idiomatic C# implementer)
- go-developer -> decaf-build/agents/ (idiomatic Go implementer)
- technical-writer -> decaf-build/agents/ (LLM-optimized docs, post-feature)
- debugger -> decaf-quality/agents/ (diagnosis; pairs with the diagnose skill — delegated deep dive)

DROP:
- planner (redundant with draft-plan + breakdown-phase)

On port: fix any references in the kept agents to the dropped planner or to old plugin/skill names; conventions-symlink if any agent references a shared convention (unlikely — agents are persona prompts). List the new agents in each plugin's README + the top-level docs.

## Verification

[ ] decaf-plan/agents/architect.md present
[ ] decaf-build/agents/{csharp-developer,go-developer,technical-writer}.md present
[ ] decaf-quality/agents/debugger.md present
[ ] planner.md absent from all shipping plugins
[ ] no references to planner or old plugin names remain in the ported agents
[ ] agents listed in plugin READMEs + top-level docs
