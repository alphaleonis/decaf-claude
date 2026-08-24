# Subagent dispatch & report delivery

How a dispatched agent's report gets back to the caller — and how it gets silently lost.
Applies to every skill that launches agents via the `Agent` tool (fan-outs, implementation
workers, review subagents, focused fixes, agent teams).

## The two dispatch modes

The `Agent` tool has two execution models, and `name` is what selects between them:

| Dispatch | Model | What the tool result is |
|----------|-------|-------------------------|
| **No `name`** | Task — a call that returns | The agent's **final message** — the report |
| **`name` set** | Teammate — an actor with a mailbox | A spawn acknowledgment. The final message is **discarded** |

Verified by controlled experiment (dcc-8yio): two identical agents, same type, same prompt,
both `run_in_background: false` — the unnamed arm returned its answer as the tool result;
the named arm returned a spawn ack and its answer was destroyed undelivered. Field-confirmed
in a full auto-deliver run: every named agent briefed without an explicit delivery
instruction delivered nothing (0/3); every agent whose brief carried one delivered (5/5).

## Rules

1. **Need only a report back? Dispatch unnamed.** The final message is the tool result —
   delivery is built in. Do **not** instruct a task-mode agent to `SendMessage` its report
   or write it to a file: on the task path that replaces reliable delivery with a channel
   that may have no receiver (an unnamed caller has no address, so replies bounce).
2. **Need mid-flight interaction? Name the agent — and add the delivery clause.** A
   teammate's final message is discarded, so every teammate brief MUST end with:

   > End your turn by calling `SendMessage` with `to: "<caller>"` carrying your full
   > report. Do not simply end your turn — a teammate's plain final message is not
   > delivered. If the work produced no output, say so explicitly.

   Ending the brief with *"your final message is the return value"* is the task-mode
   contract; on a named agent it loses the report.
3. **Tripwire — read the first tool result.** If a dispatch you expected a report from
   returns `Spawned successfully` / "will receive instructions via mailbox", you are in
   teammate mode and no report is coming on its own. From the **main context** you can
   recover: `SendMessage` the agent an explicit *"send your full report as the reply to
   this message via SendMessage"* (a bare nudge produces another idle notification, not
   the report). From inside a **subagent** there is no address to reply to — re-dispatch
   unnamed instead.
4. **A dispatched agent cannot be reliably redirected.** Messages drain at the receiver's
   next tool round; an agent deep in a long tool call (a build, a test run, a commit) has
   no interrupt, and task-mode agents have no mailbox at all. If a decision changes after
   dispatch, do not assume a HOLD landed — verify what actually happened (`git status`,
   `git log`, the diff itself) before acting on the new decision.
