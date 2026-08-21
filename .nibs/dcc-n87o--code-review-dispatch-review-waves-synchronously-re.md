---
# dcc-n87o
version: 1
title: 'code-review: dispatch review waves synchronously; reports as final message'
status: completed
type: task
priority: normal
created_at: 2026-07-03T19:58:34Z
updated_at: 2026-07-15T19:18:57Z
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


## Correction (2026-07-15) — the root cause above is wrong; see dcc-8yio

`run_in_background: false` was never load-bearing, and the diagnosis in this nib ("'parallel calls in a single message' went stale when the harness made Agent calls background-by-default") does not describe the failure.

The Agent tool's `name` parameter selects the **execution model**. Without it, a dispatch is a task whose tool result is the agent's final message. With it, the agent becomes a mailbox-addressable actor whose final message has no return channel and is discarded. `run_in_background: false` is a parameter of the task model, so under `name` it is silently **inert, not overridden**. Verified by controlled experiment (dcc-8yio): two identical agents, sole variable `name` — the unnamed arm returned its answer as the tool result, the named arm returned a spawn ack and its answer was never delivered.

Consequences for reading this nib:

- The mandate it added is harmless and still correct, but it did not fix what it was filed against. sn96's reviewers were lost because they were **named**, not because they were backgrounded.
- The 2026-07-14 session ran clean only because its orchestrator happened not to name its agents (252 subagents, zero `name`, zero losses) — not because this mandate held.
- The 2026-07-15 gysg wave lost all ten reports with `run_in_background: false` set on every single call, which is what exposed the real cause.
- sn96's four "process issues" (premature return, broken reply topology, timer/watcher idling, idle-notification noise) are all this one root cause.
- sn96's companion suggestion — "orchestrators should be spawned with a `name` so they are addressable" — is actively harmful and is tracked in dcc-5dw3.

The real guard (forbid `name`, plus a tripwire on the spawn acknowledgment) landed in dcc-8yio.
