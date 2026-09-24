---
# dcc-di3q
version: 1
title: 'auto-code-review: cheap fix-verification check for rounds that get no full re-review'
status: completed
type: task
estimate: m
created_at: 2026-08-29T18:46:50Z
updated_at: 2026-09-24T18:02:42Z
parent: dcc-fq6j
order: ak
---

## Context

Idea from superpowers subagent-driven-development (6.3.0, `re-review-prompt.md`): a re-review rung cheaper than `bugs`-scoped-to-modified-files — a single read-only agent that only (1) verdicts each fixed finding ADDRESSED / NOT ADDRESSED with file:line evidence and (2) inspects the fix diff for new breakage; forbidden to spawn subagents, runs on a cheap model. With such a rung, the Step 5 gate could afford to default toward re-reviewing marginal rounds instead of skipping them.

## Description

auto-code-review's Step 5 gate sends a round to a full re-review only on a named trigger, a Critical/High fix, two or more Medium fixes, or the overflow bound, and never at the iteration cap. Two kinds of round therefore end with fixes nobody checked: a marginal round (for example a single Medium fixed) and the last round at `--max-iterations`. superpowers closes this with one cheap scoped re-review after every repair round.

Add a new agent, `decaf-quality/agents/fix-verifier.md`, modeled on `finding-validator.md` and following `conventions/persona-authoring.md`. It is read-only, never dispatches subagents, and is dispatched on the mid tier code-review uses for verification agents. It receives the findings the round fixed (from the review file) and the round's delta (`git diff $ROUND_SNAPSHOT`), and returns, per finding, ADDRESSED or NOT ADDRESSED with file:line evidence, plus any new breakage the fix diff introduced, with severity and file:line.

## Decisions (refine, 2026-09-24)

- **When it runs:** whenever Step 5 sends the round to no full re-review and the round fixed at least one Medium-or-higher finding. That covers marginal rounds and the final round at the cap. Purely mechanical rounds (only Low and Minor–Consistency fixes) still skip, as today.
- **Where it sits:** below the existing re-review presets, replacing none of them. Warranted rounds still get the full re-review with the screen and validation funnel; the iteration ≥ 3 `bugs roster=3` rung stays.
- **NOT ADDRESSED findings** were screened and validated when first reported, so they go straight back to the fixer for another round (within the cap). At the cap they are listed in the final summary as `fix not verified`.
- **New breakage** is escalated, never fed to the fixer directly: below the cap, run the full re-review Step 5.4 would choose, on the round's delta, so the funnel screens it; at the cap, list it in the final summary as a possible regression.
- **Iterations:** the check itself does not count as an iteration; a repair round or full re-review it triggers does, so `--max-iterations` still bounds the loop.
- **Registration:** list `fix-verifier` with the validators and skill specialists in the repo CLAUDE.md. Under `--report`, record the verifier's usage in the ledger like any other dispatch.

## Acceptance

- [x] [run] `grep -c -E '^name: fix-verifier$|^description: .*Dispatch' decaf-quality/agents/fix-verifier.md` — expect: `2` (the agent exists, and its description carries a dispatch clause)
- [x] [run] `grep -c 'NOT ADDRESSED' decaf-quality/agents/fix-verifier.md` — expect: at least 1 (the verdict vocabulary is defined)
- [x] [run] `grep -E '^tools:' decaf-quality/agents/fix-verifier.md | grep -v -E 'Agent|Edit|Write'` — expect: one line (a tool allowlist with no Agent, Edit or Write)
- [x] [run] `grep -n 'fix-verifier' decaf-quality/skills/auto-code-review/SKILL.md` — expect: matches in Step 5 (the dispatch and its outcomes) and in Step 6's final summary
- [x] [run] `grep -c 'fix-verifier' CLAUDE.md` — expect: at least 1
- [x] [manual] A fresh agent walking auto-code-review picks the right branch for three rounds: one Medium fixed at iteration 1 of 3 (cheap check), any Medium-or-higher round at the cap (cheap check, results into the final summary), and a round of only Low fixes (skip); and on reported breakage below the cap it escalates to the Step 5.4 full re-review. Reason: the skill is prose an agent executes; no command can run it, so the check is an agent walkthrough.

## Notes
- `fix-verifier` follows finding-validator's shape (validators skip the reviewer personas' nine-section anatomy): `model: inherit` with the tier chosen at dispatch, a unique color, a `Dispatch —` clause, a read-only tool list, the shared working-tree safety rules, and JSON output for the main context to act on.
- Tested with fresh agents on three rounds. Old text: a single-Medium round and a High round at the cap both went straight to the final summary with no one checking the fixes; a Low-only round skipped. New text: both checked rounds dispatch the verifier without counting an iteration, the Low-only round skips, Medium breakage below the cap escalates to `review roster=4 reach=narrow` and never reaches the fixer directly, and an unaddressed finding at the cap lands under Unverified at the Cap.
- Verifier breakage escalates to Step 5.4's default rung, because it is not one of 5.4's named triggers. Making it one would be a separate decision.

## Summary

**Completed 2026-09-24** — New `decaf-quality:fix-verifier` agent: read-only, no subagents, mid tier at dispatch; verdicts each fixed finding ADDRESSED / NOT ADDRESSED and reports new breakage in the round's delta. auto-code-review Step 5 now sends every round that gets no full re-review but fixed a Medium-or-higher finding, including the last round at the cap, to a new Step 5.5; purely mechanical rounds still skip. Below the cap, breakage escalates to a full re-review and NOT ADDRESSED findings go back to the fixer; at the cap both land under Unverified at the Cap. The check does not count as an iteration. Registered in the repo CLAUDE.md, README and decaf-quality README. Verified by five acceptance greps and before/after agent walkthroughs.
