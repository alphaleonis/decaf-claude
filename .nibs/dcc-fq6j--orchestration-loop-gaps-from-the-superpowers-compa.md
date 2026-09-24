---
# dcc-fq6j
version: 1
title: Orchestration-loop gaps from the superpowers comparison
status: todo
type: epic
priority: normal
created_at: 2026-09-24T17:02:53Z
updated_at: 2026-09-24T17:25:54Z
order: zzzzzy
---

## Objective

Close the gaps found on 2026-09-24 when decaf's orchestration loops were compared with superpowers 6.4.1 (`subagent-driven-development` and `executing-plans`), measured against the late-2026 research on Ralph loops versus subagent skills. The research report lives outside this repo at `~/reports/Ralph Wiggum loop vs subagent skills.md`.

decaf already leads on the outer loop (auto-deliver), executable phase acceptance checks, tracker-backed resume, and careful parallel mechanisms in batch-dev. superpowers leads on dispatch economy, resuming the implementer for repair rounds, naming a model on every dispatch, and reviewing every task against its spec. The children bring decaf's weaker points up without giving up those strengths.

## Acceptance Criteria
- [ ] #dcc-bb1s — each series nib is reviewed against its own nib as an explicit spec
- [ ] #dcc-u73a — batch-dev works from any tracker through the adapter contract, not only nibs
- [ ] #dcc-qdxo — auto-code-review runs unattended without ever asking the user
- [ ] #dcc-di3q — a cheap fix-verification re-review step exists below the current re-review presets
- [ ] #dcc-ig50 — early repair rounds resume the implementer instead of paying for a fresh fixer
- [ ] #dcc-lw9s — every implementer, fixer and orchestrator dispatch names its model under a stated policy
- [ ] #dcc-vi86 — auto-deliver can stop after N laps so an outer loop restarts it in a fresh process
- [ ] #dcc-s2a6 — merged parallel clusters get an independent review before the next cluster starts

## Scope Boundaries

Touches: decaf-build (`batch-dev`, `auto-deliver`, `auto-dev`, `auto-tdd`) and decaf-quality `auto-code-review`; possibly `conventions/subagent-briefs.md` and `conventions/work-items.md` (the adapter contract may need new operations).

Out of scope: moving code-review's reviewer fan-out into a `Workflow` script. code-review runs inside auto-code-review's Step 2 subagent, and subagents cannot call the Workflow tool. Revisit only if the review ever moves to the main context.
