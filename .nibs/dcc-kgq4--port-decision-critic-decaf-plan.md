---
# dcc-kgq4
version: 1
title: Port decision-critic → challenge-decision (decaf-plan)
status: todo
type: task
priority: normal
created_at: 2026-06-21T09:09:39Z
updated_at: 2026-06-21T09:43:49Z
parent: dcc-f5dj
order: a0
---

## Description

Move old/decaf/skills/decision-critic into decaf-plan, **renamed `challenge-decision`** (invokes as /decaf-plan:challenge-decision). Adversarial stress-test of a decision = decide what/how, so it belongs with grill-me / explore-designs. Name rationale: it's an imperative action (verb + object), distinct from grill-me (interviews you about a plan) — this one analytically dissects a stated decision (decompose → verify → steel-man-against → verdict).

On port: update the frontmatter `name`, the H1, and the self-referential `/decaf-plan:decision-critic` usage to `challenge-decision`; rewrite the description in plain language consistent with the other plan skills; apply the conventions-symlink pattern if it references any shared convention.

## Verification

[ ] decaf-plan/skills/challenge-decision/SKILL.md present; frontmatter name=challenge-decision, H1 updated
[ ] no `decision-critic` references remain in the ported skill
[ ] any convention reference is plugin-local (symlinked), not an escaping path
[ ] listed in decaf-plan/README.md and the top-level docs
