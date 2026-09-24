---
# dcc-ig50
version: 1
title: 'auto-code-review: resume the implementer for repair rounds instead of a fresh fixer'
status: completed
type: task
priority: normal
estimate: m
created_at: 2026-09-24T17:02:59Z
updated_at: 2026-09-24T18:09:07Z
parent: dcc-fq6j
order: as
---

## Context

auto-code-review Step 4 dispatches a fresh fixer subagent every round, which re-reads code it has never seen and pays the full orientation cost each time. superpowers `subagent-driven-development` resumes the original implementer for repair rounds 1–3, because its context already holds the task, the code and its own choices. The research behind the epic cites one project measuring roughly half the orientation cost saved by resuming instead of re-dispatching. Related: #dcc-di3q (fix-verifier), whose NOT ADDRESSED verdict is one of the signals below.

## Evidence (refine, 2026-09-24)

- **Resume works on a finished, unnamed agent.** Experiment: an unnamed agent was told two values and finished; `SendMessage` to its raw agent ID returned "Resuming agent", and the resumed agent recalled both values. Its reply arrived as a separate hand-back message, not as the send's tool result, so the caller waits for it exactly as it waits for a fresh background dispatch. The SendMessage tool documents the same: a send resumes a completed agent from its transcript, addressed by raw ID when it has no name.
- **The ID is already in the right context.** auto-dev and auto-tdd (Step 2) and batch-dev (Phase 6a) dispatch the implementer in the main context and then run auto-code-review via the Skill tool in that same context, so the implementer's agent ID can be passed as an explicit argument.
- **Tokens are not the saving.** A resumed agent re-processes its whole context, and after a review wave longer than the subagent cache's five-minute default that context is uncached. The expected saving is re-orientation time and turns, which is why the change is measured.

## Decisions

- **Callers pass `--implementer <agent-id>`** to auto-code-review: auto-dev, auto-tdd, and batch-dev's series lane. Parallel lanes self-review and are unaffected.
- **Step 4 resumes the implementer for every repair round** by sending it the same repair brief a fresh fixer gets (verify-first rule, per-fix snapshots, TDD for behavioral findings, boundary self-check, one-line-per-finding report).
- **A finding the implementer already failed to fix goes to a fresh fixer instead**: one fix-verifier marked NOT ADDRESSED, or one a re-review found again. Fresh eyes are spent where the author is stuck, keyed to an observable signal rather than a round count.
- **Disputed findings get an independent check.** When the resumed implementer reports a finding as `not-addressing`, a fresh fixer re-runs verify-first on just those findings in the same round; its verdict stands. The fresh fixer runs after the resumed implementer finishes, never alongside it, because both edit one working tree.
- **Fallback:** no `--implementer`, or a resume that errors, dispatches a fresh fixer as today.
- **On by default, measured:** the `--report` ledger records, per repair round, which route ran (resumed implementer, fresh fixer, or both) with usage, so session reports show whether resuming saves anything.
- **Convention:** `conventions/subagent-briefs.md` gains a rule for resuming a finished unnamed agent by ID, with the reply arriving as a hand-back.

## Acceptance

- [x] [run] `grep -n -- '--implementer' decaf-quality/skills/auto-code-review/SKILL.md` — expect: matches in the argument-hint, the argument list, and Step 4
- [x] [run] `for f in auto-dev auto-tdd batch-dev; do grep -c -- '--implementer' decaf-build/skills/$f/SKILL.md; done` — expect: three counts, none of them 0 (each caller passes the implementer's ID)
- [x] [run] `grep -c -i 'resum' conventions/subagent-briefs.md` — expect: at least 1 (the resume rule exists)
- [x] [run] `grep -n -i -E 'resumed implementer|fresh fixer' decaf-quality/skills/auto-code-review/SKILL.md` — expect: matches in Step 1's `--report` ledger list and in Step 4's routing
- [x] [manual] A fresh agent walking auto-code-review routes correctly in four cases: an implementer ID on round 1 (resume via SendMessage and wait for the hand-back); a finding fix-verifier marked NOT ADDRESSED (fresh fixer); a resumed implementer reporting `not-addressing` (fresh fixer re-checks it after the implementer finishes); no ID given (fresh fixer). Reason: the skill is prose an agent executes; no command can run it, so the check is an agent walkthrough.

## Notes
- Callers record the implementer's agent ID from the dispatch result and pass `--implementer`; auto-code-review Step 4 routes each round between the resumed implementer (reached by `SendMessage`, reply awaited as a hand-back) and at most one fresh fixer, run in that order so they never edit the working tree at once.
- Tested with fresh agents. Old text: no ID passed anywhere, a fresh fixer every round, and a `not-addressing` claim stood on the fixer's own word with no independent check. New text: the implementer is resumed for round 1; a disputed finding goes to a fresh fixer after the implementer finishes and counts as dismissed only when that fixer agrees; a fix-verifier NOT ADDRESSED finding goes fresh; with no ID everything goes fresh; the ledger records each round's route.
- Whether resuming saves anything is still unmeasured: a resumed agent re-reads its whole context, likely uncached after a review wave. The `--report` ledger now records route and usage per round, so session reports can settle it.

## Summary

**Completed 2026-09-24** — auto-code-review takes `--implementer <agent-id>`, passed by auto-dev, auto-tdd and batch-dev's series lane. Step 4 resumes that implementer with the repair prompt every round; findings it already failed to fix (fix-verifier NOT ADDRESSED, or re-found by a re-review) and findings it disputes as `not-addressing` go to one fresh fixer run after it, whose verdicts stand. No ID, or a failed send, falls back to a fresh fixer. The `--report` ledger records each round's route with usage. subagent-briefs.md gains rule 5 on resuming a finished agent, from a 2026-09-24 experiment. Verified by four acceptance greps and before/after agent walkthroughs.
