---
# dcc-kgq4
version: 1
title: Port decision-critic -> decaf-plan
status: todo
type: task
created_at: 2026-06-21T09:09:39Z
updated_at: 2026-06-21T09:09:39Z
parent: dcc-f5dj
order: a0
---

## Description

Move old/decaf/skills/decision-critic into decaf-plan (invokes as /decaf-plan:decision-critic). Adversarial stress-test of a decision = decide what/how, so it belongs with grill-me / explore-designs. Rewrite the description in plain language consistent with the other plan skills. Apply the conventions-symlink pattern if it references any shared convention.

## Verification

[ ] decaf-plan/skills/decision-critic/SKILL.md present; name=decision-critic
[ ] any convention reference is plugin-local (symlinked), not an escaping path
[ ] listed in decaf-plan/README.md and the top-level docs
