---
# dcc-ig50
version: 1
title: Resume the implementer for early repair rounds instead of a fresh fixer
status: draft
type: task
priority: normal
estimate: m
created_at: 2026-09-24T17:02:59Z
updated_at: 2026-09-24T17:03:11Z
parent: dcc-fq6j
order: as
---

## Description

auto-code-review Step 4 dispatches a fresh fixer subagent every round. That agent re-reads the code it has never seen and pays the full orientation cost each time. superpowers `subagent-driven-development` resumes the original implementer for repair rounds 1–3, because its context already holds the task, the code and its own choices, and only switches to a fresh implementer on a stronger model for rounds 4–5. The research behind this epic cites one project measuring roughly half the orientation cost saved by resuming instead of re-dispatching.

In decaf the implementer and the fixer are dispatched by different skills: the implementer by the caller (auto-dev / auto-tdd Step 2, batch-dev Phase 6a), the fixer by auto-code-review Step 4. Resuming needs the caller to hand the implementer's agent ID to auto-code-review.

Related: #dcc-di3q (the cheap fix-verification re-review step, also taken from superpowers SDD).

## Open questions

- Does `SendMessage` to a finished, unnamed agent's ID resume it and return its reply as the tool result, consistent with the task-mode rules in `conventions/subagent-briefs.md` (#dcc-8yio)? In the 2026-09-24 session, unnamed `Agent` results advertised "SendMessage with to: <id> … to continue this agent", but resuming a finished agent has not been tested against decaf's dispatch rules. Settle this first.
- How many rounds resume before switching to a fresh fixer, and does the fresh one move up a model tier as in superpowers?
- Does a resumed implementer still apply Step 4's "verify the finding first" rule with enough distance from its own code? The review itself stays independent either way.
- How does the agent ID travel: a new auto-code-review argument, or the `--report` implementation-phase record?
