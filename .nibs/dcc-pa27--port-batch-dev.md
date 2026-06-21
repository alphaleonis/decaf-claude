---
# dcc-pa27
version: 1
title: Port batch-dev
status: completed
type: task
priority: normal
created_at: 2026-06-20T18:27:56Z
updated_at: 2026-06-20T20:32:52Z
parent: dcc-s8di
blocked_by:
    - dcc-d61y
order: aw
---

## Description
Port `batch-dev`; repoint review calls to /decaf-quality:. Leave the future unattended / gate-suppressed mode (for auto-deliver) as a documented stub — do NOT implement it here.

## Verification
- [ ] batch-dev present; review calls → /decaf-quality:
- [ ] unattended mode noted as future, not implemented


## Summary of Changes
Copied batch-dev from old/decaf-dev. Repointed review calls `/decaf-review:auto-review` → `/decaf-quality:auto-code-review`; namespaced sibling refs (`/auto-dev`, `/auto-tdd`, `/batch-dev`) → `/decaf-build:`. **Generalized 4 NZBrowse-specific spots** (build/test commands, fresh-worktree dependency provisioning, worktree-mechanics note, final build/app-lock check) so the skill is project-agnostic. Added a **Face-2 `--unattended` stub note** near the Phase 5 gate — documented as future, NOT implemented (that's dcc-o89j).
