---
# dcc-6yi4
version: 1
title: 'auto-code-review: fix-round boundary self-check + least-invasive-fix preference'
status: completed
type: task
priority: normal
created_at: 2026-07-03T19:58:50Z
updated_at: 2026-07-03T20:04:01Z
order: "n"
---

Session evidence: iteration 3's headline regression (charset gate broke exact foreign-ID lookup) was introduced by fix round 2 implementing iteration 2's suggested behavioral fix when a doc-only alternative was offered; the fix's own new tests pinned '-42' -> reject and 'task' -> accept but never the exact-ID 'task-42' — DESIGN-1: 'the gap sits precisely between the two pinned cases'. A full 10-agent wave (est. 0.6-1.1M tokens) then caught what a fix-time boundary probe would have.

## Todo

- [x] Step 4 execution rules: when a finding offers alternative fixes, default to the least invasive that fully resolves it; note the choice
- [x] Step 4 execution rules: behavior-changing fixes (new/changed predicate, gate, threshold, normalization) must enumerate boundary inputs — including inputs between the cases the new tests pin — and add a test case for each
- [x] Step 2 re-review prompt: instruct reviewers to probe boundary behavior of each behavior-changing fix


## Summary of Changes

- decaf-quality/skills/auto-code-review/SKILL.md Step 4 (fix subagent template), rule 2: added least-invasive-fix bullet — when a finding offers alternatives, default to the minimal option that fully resolves the issue at its severity, note the choice.
- Step 4 rule 3: added boundary self-check bullet for behavior-changing fixes — enumerate boundary inputs including those between the pinned test cases, with the task-42 charset-gate example as the cautionary case.
- Step 2 subsequent-iteration prompt: reviewers instructed to probe boundary behavior of behavior-changing fixes (done alongside dcc-n7bm's edit).
