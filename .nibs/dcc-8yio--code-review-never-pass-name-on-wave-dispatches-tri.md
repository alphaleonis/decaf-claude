---
# dcc-8yio
version: 1
title: 'code-review: never pass name on wave dispatches; tripwire the spawn ack'
status: completed
type: task
priority: high
created_at: 2026-07-15T19:15:11Z
updated_at: 2026-07-15T19:17:01Z
order: zzV
---

Verified root cause of the 2026-07-15 gysg wave losing all 10 reviewer reports — and, retroactively, of all four process issues filed from the sn96 session (2026-07-03).

## Root cause

The Agent tool has two execution models, and the `name` parameter selects between them:

- **no `name`** → task model: the call returns the agent's final message as the tool result.
- **`name` set** → teammate model: the agent becomes a mailbox-addressable actor, the call returns a spawn ack, and the final message has no return channel — it is discarded.

`run_in_background: false` is a parameter of the task model. With `name` set there is no call to block on, so the flag is silently **inert, not overridden**. dcc-n87o's mandate was therefore never load-bearing.

## Evidence

- **gysg wave** (nibs session b8aac675, 2026-07-15 20:07): the review orchestrator dispatched all 10 reviewers with `run_in_background: false` AND `name`. All 10 returned `Spawned successfully … will receive instructions via mailbox`. No report reached it.
- **Differential:** the 2026-07-14 batch-dev session ran 252 subagents — zero passed `name`, zero spawn acks, all reports returned as tool results. The nibs main session made 30 general-purpose dispatches (`run_in_background: false`, no `name`); all 30 returned normally.
- **Controlled experiment** (decaf-claude session f780cfd2): two agents, same subagent_type/model/prompt, both `run_in_background: false`, sole variable `name`. Unnamed arm → tool result `MANGO-42`. Named arm → spawn ack; `MANGO-42` present in its on-disk transcript, never delivered.
- Transcript filenames encode the mode: named → `agent-a<name>-<hash>.jsonl`, unnamed → `agent-a<hash>.jsonl`.

## Why it was silent, and why it hit hardest

Reviewers had two exits; teammate mode closed both:

- **final message** → no caller waiting → discarded. This is exactly what SKILL.md instructs them to do.
- **SendMessage** → the orchestrator was unnamed, so the reply address `general-purpose` is an agent *type*, not an identity → bounced. 5 of 10 improvised a re-address to `team-lead` and landed in the main conversation hours later.

The 5 that obeyed the "final message, never SendMessage" contract lost their reports: adversarial, broad, design, knowledge, quick — the highest-yield lanes in the corpus. Compliance was punished; deviation got through.

The parent did not die first: all 10 reviewers finished by 20:09:00; the orchestrator wrote its fallback file at 20:15:10 and lived until 20:15:37. Keeping it alive, or retrying, would have changed nothing.

Consequence: `36106d2` in nibs (18 files, +1110/-112, data-safety surface) was committed on a single-reviewer APPROVED, with 5 reports never read by anyone.

## Supersedes / corrects

- **dcc-n87o's root-cause claim** ("'parallel in a single message' went stale when the harness made Agent calls background-by-default") is wrong. The mandate it added is harmless but was never the fix.
- **The sn96 report's tuning suggestion** — "orchestrators should be spawned with a `name` so they are addressable" — is actively harmful. Naming the orchestrator flips *it* into teammate mode, breaking its own return path one level up. The teammate registry is a session-scoped star with exactly one well-known anchor (`team-lead` = main), so a nested orchestrator can never be a mail hub. The skill chain is a tree; the actor model composes one level deep only. (`reports/` lives on `tuning` — correction tracked below.)
- All four sn96 "process issues" — premature return, broken reply topology, timer/watcher idling, idle-notification noise — are this one root cause.

## Todo
- [x] Step 3: forbid `name`; document the two execution models; add the spawn-ack tripwire
- [x] Step 3: state that parallelism comes from batching calls into one message, not from backgrounding
- [x] Step 3: mark the final-message contract as task-path-only, and say why that makes the tripwire non-optional
- [x] Step 2c: defuse "team" as a naming cue
- [x] Step 4/5 validator dispatch: same contract, tripwire included
- [x] Split the sn96 report correction out to dcc-5dw3 (lives on `tuning`)

## Summary

Root cause verified by controlled experiment: the Agent tool's `name` parameter selects the execution model. No `name` -> task (the final message returns as the tool result); `name` set -> teammate (a mailbox actor whose report has no return channel). `run_in_background: false` is inert under `name`, so dcc-n87o's mandate was never load-bearing.

Patched decaf-quality/skills/code-review/SKILL.md:
- Step 3 dispatch: forbids `name`, documents both execution models, and adds a tripwire on the spawn acknowledgment — the only signal distinguishing a mis-dispatched wave from a working one.
- Step 3: parallelism comes from batching calls into one message, not from backgrounding.
- Step 3: the "report as final message" contract marked task-path-only — in teammate mode it destroys the reports of the reviewers that obey it.
- Step 2c: "team" defused as a naming cue.
- Step 5.6 validator dispatch: same contract, tripwire included.

Follow-up dcc-5dw3 filed for the sn96 report's contrary "name the orchestrators" suggestion (reports/ lives on `tuning`).
