---
# dcc-mhz3
version: 1
title: Port problem-analysis -> decaf-quality
status: todo
type: task
created_at: 2026-06-21T09:09:39Z
updated_at: 2026-06-21T09:09:39Z
parent: dcc-f5dj
order: ak
---

## Description

Move old/decaf/skills/problem-analysis into decaf-quality (invokes as /decaf-quality:problem-analysis). Root-cause investigation before fixes — diagnosing existing code. Split roles with the debugger agent: the skill is you-drive interactive investigation; the agent is a delegated deep dive. Note the split in the skill body. (Debugger agent placement is handled in the core-agents triage task.) Plain-language description; conventions-symlink if needed.

## Verification

[ ] decaf-quality/skills/problem-analysis/SKILL.md present
[ ] role split vs the debugger agent noted
[ ] listed in docs
