---
# dcc-lw9s
version: 1
title: Choose the model tier on every build-loop dispatch via --models (set model, never name)
status: completed
type: task
priority: normal
estimate: m
created_at: 2026-09-24T17:02:59Z
updated_at: 2026-09-24T18:23:56Z
parent: dcc-fq6j
order: aw
---

## Context

Only code-review's reviewers pick their model on purpose (its `models` axis, Step 2d). Every other dispatch in the build loops omits `model` and inherits the session model: auto-dev / auto-tdd Step 2 (implementer); batch-dev Phase 2 (Explore fan-out) and Phases 6a–6d (implementers, lanes, workflow agents, team members); auto-code-review Step 2 (the code-review orchestrator subagent) and Step 4 (fresh fixer); auto-deliver VERIFY (focused fixes). The one exception is `fix-verifier` (#dcc-di3q), dispatched on the mid tier like code-review's verification agents. superpowers requires every dispatch to state its model, and warns that "turn count beats token price": the cheapest models often take two to three times the turns on multi-step work.

**Related: #dcc-5dw3.** It corrects a session report that told agents to give orchestrators a `name`. That parameter changes how a report is delivered (task vs teammate mode, `conventions/subagent-briefs.md` rules 1–2), and the idea has already been re-derived once. Tiering is the `model` parameter only; this item must never add a `name`, and its wording avoids "name the dispatch" for that reason.

## Decisions (refine, 2026-09-24)

- **A `--models low|norm|high` flag** on auto-deliver, batch-dev, auto-dev, auto-tdd and auto-code-review, governing their own dispatches and forwarded down the chain (auto-deliver → batch-dev → auto-code-review; auto-dev / auto-tdd → auto-code-review). It is separate from the `models=` axis inside `--review`, which keeps governing only the reviewers. Default `high`: today's behavior, so nothing changes unless a caller asks.
- **Tiers:** *no override* and the *mid tier*. No override means the dispatch passes no `model`, so Claude Code resolves it exactly as today: the agent definition's `model`, then `CLAUDE_CODE_SUBAGENT_MODEL`, then the main conversation's model (the built-in `Explore` type inherits the main model capped at Opus). The mid tier passes `model: sonnet`. Never tier up: when the main model is already at or below Sonnet, pass no override. When the Agent tool offers no `model` parameter, dispatch without one.
- **What `high` runs today (checked 2026-09-24):** this setup sets no `CLAUDE_CODE_SUBAGENT_MODEL` and the main model is `opus`, so every build dispatch runs on the main conversation's Opus, except `fix-verifier` (Sonnet, set at dispatch).
- **Role table:**

  | `--models` | Mid tier (`model: sonnet`) | No override (today's resolution) |
  |---|---|---|
  | `high` (default) | fix-verifier | everything else, as today |
  | `norm` | fix-verifier, batch-dev's read-only explorers | implementers, review orchestrator, fresh fixer, focused fixes |
  | `low` | fix-verifier, explorers, fresh fixer, auto-deliver's focused fixes | implementers and the review orchestrator |

  fix-verifier stays mid tier under every value, matching code-review's verification agents. A resumed implementer keeps whatever model it was dispatched on. The per-dispatch `model` parameter outranks `CLAUDE_CODE_SUBAGENT_MODEL` (unless `CLAUDE_CODE_SUBAGENT_MODEL_FORCE=1`), so mid-tier roles get Sonnet even when that variable names another model.
- **One canonical home:** a new rule 6 in `conventions/subagent-briefs.md` holds the tiers, the tier-to-model mapping and the table, and says tiering sets `model`, never `name`. code-review Step 2d points there for the tier-to-model mapping instead of naming `sonnet` itself; its own role mapping for reviewers is unchanged.
- **Accounting:** under `--report`, build dispatches fill the existing Model tier column of the session report's agent inventory.

## Acceptance

- [x] [run] `grep -n -i 'tier' conventions/subagent-briefs.md` — expect: a rule 6 defining the tiers, the tier-to-model mapping, and the per-value role table
- [x] [run] `grep -c 'never `name`' conventions/subagent-briefs.md` — expect: at least 1 (tiering sets `model` only)
- [x] [run] `for f in auto-deliver batch-dev auto-dev auto-tdd; do grep -c -- '--models' decaf-build/skills/$f/SKILL.md; done` — expect: four counts, none of them 0
- [x] [run] `grep -n -- '--models' decaf-quality/skills/auto-code-review/SKILL.md` — expect: matches in the argument-hint, the argument list, Step 2 (orchestrator) and Step 4 (fresh fixer)
- [x] [run] `grep -n -i 'rule 6' decaf-quality/skills/code-review/SKILL.md` — expect: Step 2d points at the convention for the tier-to-model mapping
- [x] [manual] A fresh agent walking auto-deliver → batch-dev → auto-code-review states the model for every dispatch under the default and under `--models low`, and no dispatch sets `name` outside batch-dev's agent-team mechanism. Reason: the skills are prose an agent executes; no command can run them, so the check is an agent walkthrough.

## Notes
- Rule 6 in `conventions/subagent-briefs.md` is the one home for the tiers, the tier-to-model mapping and the per-value table; code-review Step 2d now points there instead of naming `sonnet`, by plain path because code-review did not load the dispatch convention and an `@` reference would pull the whole file into it.
- auto-deliver's `state.json` gains an optional `models` field, so a resumed run keeps its tier setting the way `review_spec` keeps the review rung.
- The baseline walkthrough found that auto-code-review Step 4's fresh fixer was the one dispatch not stated as unnamed; it now is, matching rule 6's "never `name`".
- Tested with fresh agents. Old text: auto-deliver did not recognize `--models`, and five of six dispatches stated no model. New text: `--models low` travels auto-deliver → batch-dev → auto-code-review unchanged; under `low` the explorers, fresh fixer, fix-verifier and focused fix pass `model: sonnet` and the rest pass none; under the default everything resolves to the main model (Opus in the scenario) except fix-verifier on Sonnet; no dispatch sets `name` outside batch-dev's agent-team mechanism.

## Summary

**Completed 2026-09-24** — New rule 6 in subagent-briefs.md: two tiers (no override, resolved as today; mid tier, `model: sonnet`), never tier up, set `model` never `name`, and a per-value table for `--models low|norm|high` (default `high`, today's behavior). auto-deliver, batch-dev, auto-dev, auto-tdd and auto-code-review take `--models` and forward it down the chain; each dispatch states its tier; fix-verifier stays mid tier under every value; `--report` records each build dispatch's tier. code-review Step 2d points at rule 6 for the model name. Verified by five acceptance greps and before/after agent walkthroughs.
