---
# dcc-n87o
version: 1
title: 'code-review: dispatch review waves synchronously; reports as final message'
status: completed
type: task
priority: normal
created_at: 2026-07-03T19:58:34Z
updated_at: 2026-07-03T20:03:29Z
order: ay
---

Session evidence (reports/2026-07-03-nibs-sn96-code-review-session): orchestrators spawned reviewers in the background and ended their turn to 'wait' — 3 resumes in iteration 1, 2 resumes + a kill in iteration 3, ~400-550k wasted tokens, one lost consolidated report. Reviewers also tried to SendMessage their spawner ('No agent named general-purpose is reachable') and broadcast to main instead. Root cause: SKILL.md's 'parallel calls in a single message' predates the harness making Agent calls background-by-default, so the mandate no longer implies synchronous execution. Iteration 2 (synchronous) ran clean at 161,520 orchestrator tokens vs iteration 1's 559,973.

## Todo

- [x] Step 3: require run_in_background: false on every review-agent call; forbid ending the turn / arming timers to wait
- [x] Base context template: reviewers return the report as their final message; never SendMessage, never write files
- [x] Step 5.6 validator dispatch: same run_in_background: false requirement
- [x] Rename stale 'Task tool' references to 'Agent tool'
- [x] broad-reviewer.md: fix 'Write findings to the specified output file' to final-message return


## Summary of Changes

- decaf-quality/skills/code-review/SKILL.md Step 3: dispatch section rewritten — Agent tool, single message, run_in_background: false mandatory on every call; rationale documented (subagent final message is its return value; backgrounded waves broadcast reports to main); timers/watchers and turn-ending waits forbidden; reviewers return reports as final message, never SendMessage/files.
- Base context template: added explicit final-message return instruction.
- Step 5.6 validator dispatch: same synchronous rule.
- Renamed remaining 'Task tool' references (model-tiering section + fallback) to 'Agent tool'.
- decaf-quality/agents/broad-reviewer.md: 'Write findings to the specified output file' → return as final message.
