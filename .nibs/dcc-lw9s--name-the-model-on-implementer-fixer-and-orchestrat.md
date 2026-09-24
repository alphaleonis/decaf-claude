---
# dcc-lw9s
version: 1
title: Name the model on implementer, fixer and orchestrator dispatches
status: draft
type: task
priority: normal
estimate: m
created_at: 2026-09-24T17:02:59Z
updated_at: 2026-09-24T17:03:11Z
parent: dcc-fq6j
order: aw
---

## Description

Only code-review's reviewers pick their model on purpose (the `models` axis). Every other dispatch in the build loops omits `model` and silently inherits the session model, usually the most capable and most expensive one:

- auto-dev / auto-tdd Step 2 (implementer)
- batch-dev Phase 2 (Explore fan-out) and Phases 6a–6d (implementers, lanes, workflow agents, team members)
- auto-code-review Step 2 (the code-review orchestrator subagent) and Step 4 (fixer)
- auto-deliver VERIFY (focused fixes)

superpowers requires every dispatch to state its model, with a per-role policy: the cheapest tier when the plan text holds the complete code, a mid-tier floor for implementers working from prose and for reviewers, and the most capable model for design work and the final whole-branch review. It also warns that "turn count beats token price": the cheapest models often take two to three times the turns on multi-step work.

## Open questions

- A fixed per-role policy, or a `models` axis on the build skills mirroring code-review's?
- Should the code-review orchestrator subagent be tiered separately from the reviewers it dispatches?
- How does the policy interact with `--report` cost accounting, so the effect can be measured?
