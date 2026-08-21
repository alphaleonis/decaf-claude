---
# dcc-5dw3
version: 1
title: 'sn96 report: correct the ''name the orchestrators'' tuning suggestion (harmful)'
status: todo
type: task
priority: normal
created_at: 2026-07-15T19:16:21Z
updated_at: 2026-07-15T19:16:21Z
order: zzk
---

The sn96 session report (`reports/2026-07-03-nibs-sn96-code-review-session/README.md`, process issue 2) recommends:

> orchestrators should be spawned with a `name` so they are addressable

This is wrong and actively harmful — see dcc-8yio for the verified root cause. Naming an agent flips it from the task model (the call returns the final message as a tool result) into the teammate model (a mailbox actor whose report has no return channel). Naming the orchestrator would break *its* return path to its own caller, converting a one-level failure into a two-level one.

The suggestion cannot be salvaged by naming everything, either: the teammate registry is a session-scoped **star** with exactly one well-known anchor (`team-lead` = the main conversation). A nested orchestrator can never be a mail hub for its own children, because nothing knows its name but its parent. The decaf skill chain is a **tree** (batch-dev → auto-code-review → code-review → reviewers); the actor model composes one level deep only.

Two further corrections in the same report:

- Its four "process issues" (premature return, broken reply topology, timer/watcher idling, idle-notification noise) are not four problems — they are one root cause.
- Its §4 issue-1 "post-analysis note", crediting dcc-n87o with the fix, is wrong: `run_in_background: false` was never load-bearing. The 2026-07-14 session ran clean because its orchestrator happened not to name its agents.

Left uncorrected, this recommendation keeps pulling future tuning sessions toward the exact bug it was filed against — it has already survived two weeks in the corpus and was independently re-derived by the 2026-07-15 session agent, which proposed naming the orchestrators for the same reason.

`reports/` exists only on the `tuning` branch, so this correction lands there — separate from dcc-8yio's skill patch on `main`.

## Todo

- [ ] Correct process issue 2's tuning suggestion; point at dcc-8yio
- [ ] Correct the §4 issue-1 post-analysis note crediting dcc-n87o
- [ ] Reconcile §6's resulting-skill-changes list with the real cause
