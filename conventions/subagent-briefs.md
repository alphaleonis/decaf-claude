# Subagent dispatch & report delivery

How a dispatched agent's report gets back to the caller — and how it gets silently lost.
Applies to every skill that launches agents via the `Agent` tool (fan-outs, implementation
workers, review subagents, focused fixes, agent teams).

## The two dispatch modes

With agent teams enabled (`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`), the `Agent` tool has two
execution models, and `name` is what selects between them. Without agent teams a named agent is
an ordinary subagent, but dispatching unnamed is correct either way:

| Dispatch | Model | What comes back |
|----------|-------|-----------------|
| **No `name`** | Task — a call that returns | The agent's **final message** — the report: the tool result, or for a background call a hand-back once the agent finishes |
| **`name` set** (agent teams on) | Teammate — an actor with a mailbox | A spawn acknowledgment. The final message is **discarded** |

Verified by controlled experiment (dcc-8yio), with agent teams enabled: two identical agents,
same type, same prompt, differing only in `name` — the unnamed arm's answer came back; the
named arm returned a spawn ack and its answer was destroyed undelivered. Field-confirmed
in a full auto-deliver run: every named agent briefed without an explicit delivery
instruction delivered nothing (0/3); every agent whose brief carried one delivered (5/5).

## Rules

1. **Need only a report back? Dispatch unnamed.** The final message comes back to you, as the
   tool result or, for a background call, as a hand-back once the agent finishes; delivery is
   built in, and an agent with background children running stays alive until they report. Do **not** instruct a task-mode agent to `SendMessage` its report
   or write it to a file: on the task path that replaces reliable delivery with a channel
   that may have no receiver (an unnamed caller has no address, so replies bounce).
2. **Need mid-flight interaction? Name the agent — and add the delivery clause.** A
   teammate's final message is discarded, so every teammate brief MUST end with:

   > End your turn by calling `SendMessage` with `to: "<caller>"` carrying your full
   > report. Do not simply end your turn — a teammate's plain final message is not
   > delivered. If the work produced no output, say so explicitly.

   Ending the brief with *"your final message is the return value"* is the task-mode
   contract; on a named agent it loses the report.
3. **Tripwire — read what the dispatch returns.** A background launch acknowledgment
   ("Async agent launched successfully", report to follow) is the normal task path. If a
   dispatch you expected a report from instead returns `Spawned successfully` / "will receive
   instructions via mailbox", you are in teammate mode and no report is coming on its own. From the **main context** you can
   recover: `SendMessage` the agent an explicit *"send your full report as the reply to
   this message via SendMessage"* (a bare nudge produces another idle notification, not
   the report). From inside a **subagent** there is no address to reply to — re-dispatch
   unnamed instead.
4. **A dispatched agent cannot be reliably redirected.** Messages drain at the receiver's
   next tool round; an agent deep in a long tool call (a build, a test run, a commit) has
   no interrupt, and task-mode agents have no mailbox at all. If a decision changes after
   dispatch, do not assume a HOLD landed — verify what actually happened (`git status`,
   `git log`, the diff itself) before acting on the new decision.
5. **A finished agent can be resumed.** `SendMessage` with `to:` its agent ID (or a named
   agent's name) resumes it from its transcript, context intact. The send returns at once;
   the agent's reply arrives later as a hand-back, so wait for it as for a fresh background
   dispatch. Verified 2026-09-24: an unnamed agent resumed this way recalled values from its
   first turn. Resume when the agent's context is the point, as auto-code-review does with
   the implementer for repair rounds. This covers finished agents only; rule 4 governs one
   that is still running.
6. **Choose each dispatch's model tier: set `model`, never `name`.** A name changes how the
   report is delivered (rules 1–2); tiering changes only the `model` parameter. Two tiers:
   - **No override**: pass no `model`. Claude Code resolves it as usual: the agent
     definition's `model`, then `CLAUDE_CODE_SUBAGENT_MODEL`, then the main conversation's
     model (the built-in `Explore` type inherits that model, capped at Opus).
   - **Mid tier**: pass `model: sonnet`. A per-dispatch `model` outranks
     `CLAUDE_CODE_SUBAGENT_MODEL` unless `CLAUDE_CODE_SUBAGENT_MODEL_FORCE=1`.

   Never tier up: when the main model is already Sonnet or cheaper, pass no override. When
   the Agent tool offers no `model` parameter, dispatch without one.

   The build loops (auto-deliver, batch-dev, auto-dev, auto-tdd, auto-code-review) take
   `--models low|norm|high`, default `high`, and forward it down the chain. It governs
   their own dispatches only; reviewers take their tier from the `models=` axis inside
   `--review` (code-review Step 2d), which uses this same mid tier.

   | Dispatch | `high` | `norm` | `low` |
   |---|---|---|---|
   | Implementer, worktree lane, team member, workflow agent | no override | no override | no override |
   | Review orchestrator (auto-code-review Step 2) | no override | no override | no override |
   | Read-only explorer (batch-dev Phase 2) | no override | mid tier | mid tier |
   | Fresh fixer (auto-code-review Step 4) | no override | no override | mid tier |
   | Focused fix (auto-deliver VERIFY) | no override | no override | mid tier |
   | fix-verifier (auto-code-review Step 5.5) | mid tier | mid tier | mid tier |

   A resumed implementer keeps the model it was first dispatched on.
