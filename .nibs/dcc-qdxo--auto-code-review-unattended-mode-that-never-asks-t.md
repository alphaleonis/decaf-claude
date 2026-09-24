---
# dcc-qdxo
version: 1
title: 'auto-code-review: --unattended mode that never asks the user'
status: completed
type: task
priority: high
estimate: s
created_at: 2026-09-24T17:02:59Z
updated_at: 2026-09-24T17:31:55Z
parent: dcc-fq6j
order: aV
---

## Description

auto-code-review has no unattended mode, so it can stop an unattended run to ask a question:

- **Step 3d** asks the user which tracker to use when `deferSystem` was not detected and the first `defer` comes up.
- **Step 3e** asks via `AskUserQuestion` on iteration 1 when any finding has "genuinely ambiguous options".

batch-dev's `--unattended` section lists "the review tail" as unchanged, and auto-deliver reaches auto-code-review through batch-dev Phase 6a. So an auto-deliver run can stall at the review step, which is exactly the manufactured gate auto-deliver's invariant 1 forbids. Under `claude -p` the question cannot be answered at all. Not yet observed in a real run; found by reading the skills.

Add `--unattended` to auto-code-review: ambiguous findings resolve to `defer` without asking, and a missing defer system falls back to a non-interactive default (for example the work-items adapter's Markdown backend) that is named in the final summary. batch-dev forwards the flag from Phase 6a when it runs unattended.

## Acceptance

- [x] [run] `grep -n -- '--unattended' decaf-quality/skills/auto-code-review/SKILL.md` — expect: matches in Argument Parsing and in Steps 3d and 3e
- [x] [run] `grep -n 'auto-code-review' decaf-build/skills/batch-dev/SKILL.md | grep -c -- '--unattended'` — expect: at least 1 (Phase 6a forwards the flag)
- [x] [manual] Under `--unattended`, no path through auto-code-review reaches `AskUserQuestion`

## Notes
- With no tracker detected, an unattended run leaves deferred findings unfiled and lists each in the final summary's Deferred Items as `not filed — no tracker detected`, with severity, file:line and reason. The caller receives that summary in its own context and can file them. This keeps decaf-quality free of the tracker-adapter convention and avoids inventing a Markdown plan file in a project that has none. Once #dcc-u73a lands, batch-dev could pass the tracker it already uses.
- Step 3d files deferrals before Step 3e decides whether to ask, and Step 3c's table already sends findings with conflicting options to `defer`. So the unattended rule in 3e only skips the question; the plan stands as built.
- The manual criterion was settled by listing every ask point in auto-code-review: 3d's tracker question and 3e's iteration-1 question each carry an unattended rule, 3f's prompt only fires when 3e asks, and the code-review subagent never prompts because its preset is always passed explicitly.
- Tested with fresh agents on one scenario: an ambiguous Medium, an unverified Critical and no tracker, in a headless run under auto-deliver. Old text: the agent asked both questions and concluded the run would stall, even with auto-deliver's no-gate rule in view. New text: batch-dev forwarded `--unattended`, no question was asked, both findings were deferred and listed as unfiled. Attended control on the new text: both questions still asked.

## Summary

**Completed 2026-09-24** — auto-code-review gains `--unattended`: it never calls AskUserQuestion, keeps the Step 3c plan as built (conflicting options already defer), and with no tracker detected lists deferrals as unfiled in the final summary for the caller to file. batch-dev forwards the flag from Phase 6a and its unattended section no longer lists the review tail as able to pause. Verified by the acceptance greps, an inventory of every ask point, and fresh-agent tests: old text stalled on two questions, new text asked none, attended control still asks both.
