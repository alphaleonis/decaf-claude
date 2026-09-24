---
# dcc-qdxo
version: 1
title: 'auto-code-review: --unattended mode that never asks the user'
status: todo
type: task
priority: high
estimate: s
created_at: 2026-09-24T17:02:59Z
updated_at: 2026-09-24T17:03:11Z
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

- [ ] [run] `grep -n -- '--unattended' decaf-quality/skills/auto-code-review/SKILL.md` — expect: matches in Argument Parsing and in Steps 3d and 3e
- [ ] [run] `grep -n 'auto-code-review' decaf-build/skills/batch-dev/SKILL.md | grep -c -- '--unattended'` — expect: at least 1 (Phase 6a forwards the flag)
- [ ] [manual] Under `--unattended`, no path through auto-code-review reaches `AskUserQuestion`
