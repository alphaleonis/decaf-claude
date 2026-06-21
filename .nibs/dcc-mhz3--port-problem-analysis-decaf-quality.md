---
# dcc-mhz3
version: 1
title: Port problem-analysis → diagnose (decaf-quality)
status: todo
type: task
priority: normal
created_at: 2026-06-21T09:09:39Z
updated_at: 2026-06-21T09:48:23Z
parent: dcc-f5dj
order: ak
---

## Description

Move old/decaf/skills/problem-analysis into decaf-quality, **renamed `diagnose`** (invokes as /decaf-quality:diagnose). Structured root-cause investigation (gate → hypothesize → investigate → formulate → output); it diagnoses only and never proposes fixes. Name rationale: the skill's own verb ("you diagnose root causes"), single-word like refactor / research.

Split roles with the debugger agent: the skill is you-drive interactive diagnosis; the agent is a delegated deep dive. Note the split in the skill body. (Debugger agent placement is handled in the core-agents triage task.)

On port: update frontmatter `name`, H1, and self-references to diagnose; rewrite the description in plain language; conventions-symlink if needed.

## Verification

[ ] decaf-quality/skills/diagnose/SKILL.md present; name=diagnose, H1 updated
[ ] no `problem-analysis` references remain
[ ] role split vs the debugger agent noted
[ ] listed in docs
