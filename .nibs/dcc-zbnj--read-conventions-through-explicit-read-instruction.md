---
# dcc-zbnj
version: 1
title: Read conventions through explicit read instructions in skills and agents
status: completed
type: task
created_at: 2026-10-27T17:29:46Z
updated_at: 2026-10-27T17:33:33Z
order: zzzzzzzV
---

## Description

[Describe what needs to be done]

## Verification

- [ ] [How to verify the work is complete]

## Summary

**Completed 2026-10-27** — Every @path.md line in 24 skills/agents is now an explicit read instruction on ${CLAUDE_PLUGIN_ROOT}/${CLAUDE_SKILL_DIR}, tied to the step that needs it. Verified on 2.1.311 that @ lines attach nothing (write-comments loaded without its rules) and that both variables substitute in skills and agents. Added scripts/check-skill-references.sh (flags 116 hits at the old HEAD, clean now). Kept the god-function exception in structural-analyst's table after dropping its structural.md read; security-reviewer drops security.md. CLAUDE.md, README, artifacts.md and decaf-plan/README describe the new pattern.
