---
# dcc-3qya
version: 1
title: 'code-review: drop the run_in_background mandate the Agent tool no longer accepts'
status: completed
type: bug
priority: normal
estimate: s
created_at: 2026-09-24T19:02:16Z
updated_at: 2026-09-24T19:07:10Z
order: zzzzzz
---

## Steps to Reproduce

Have code-review dispatch its wave, screeners or validators, or its `bugs` seat, under Claude Code 2.1.281. Its text requires every such Agent call to set `run_in_background: false`: the single-seat dispatch (Step 2, `bugs` path), the wave dispatch rules in Step 3 ("Every call MUST set `run_in_background: false`"), the Step 4.95 screeners and the Step 5.6 validators.

## Expected vs Actual

Expected: every instruction about dispatch parameters can be followed with the Agent tool as it exists.

Actual: as of 2.1.281 the Agent tool has no `run_in_background` parameter, in the main session or inside a subagent, and its schema rejects unknown parameters (`additionalProperties: false`). Checked 2026-09-24: the main session's tool list, plus a probe subagent reporting its own schema (description, isolation, model, mode, name, prompt, subagent_type, team_name). [Inference] An orchestrator following the text either ignores the rule or passes the parameter and has the call rejected once before retrying. Dispatches run in the background, and a finished agent's report arrives as a separate hand-back message.

Related drift in `conventions/subagent-briefs.md`:
- Its experiment note (line 17) cites `run_in_background: false`.
- Rule 1 says an unnamed agent's final message "is the tool result"; in 2.1.281 every report in the 2026-09-24 session arrived as a hand-back instead. The advice itself (dispatch unnamed) still holds.
- Rules 1–2 present teammate mode as what `name` does, but per Claude Code's agent-teams docs a named subagent becomes a teammate only when `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` is set, as it is in the operator's settings.

## Root Cause

The parameter existed when dcc-n87o added the rule, and Claude Code has since removed it from the Agent tool. As #dcc-5dw3 found, the rule was never what fixed the sn96 delivery failures; not naming the agents was (#dcc-8yio).

## Open questions

- Drop the rule outright, or replace it with what it was meant to secure: the orchestrator does not end its turn until every dispatched reviewer has reported. Check first whether 2.1.281 already keeps an agent alive while its background children run.
- How should rules 1–2 in subagent-briefs.md describe delivery so they stay true across harness versions: "the report comes back to the caller" rather than naming the tool-result mechanism, plus the agent-teams condition on teammate mode?

## Resolution
- **Experiment settled the first open question (2026-09-24, Claude Code 2.1.281).** A parent agent dispatched one unnamed child, then ended its turn at once as instructed. The harness woke it when the child finished, and its single final report carried the child's answer; no premature report came back. An agent with background children running stays alive until they report, so the sn96 early-return failure cannot occur with unnamed dispatch, and `run_in_background: false` needs no replacement beyond "consolidate only once every reviewer has reported".
- **code-review:** the mandate is gone from the `bugs` seat, the Step 3 dispatch line and bullets, the screeners and the validators. Step 3 keeps single-message parallel dispatch, unnamed, and consolidating only after every report; the tripwire now names the normal background acknowledgment ("Async agent launched successfully") so it cannot be mistaken for the teammate one.
- **Dispatch convention and callers:** the "what comes back" tables in `subagent-briefs.md` and code-review describe delivery as the tool result or, for a background call, a hand-back, and state that teammate mode needs `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`; the experiment note no longer cites the parameter. batch-dev, auto-code-review and auto-deliver say "the report comes back to you". `--report` usage is recorded as the harness reports it (tool result or completion notification) in session-report.md, code-review, auto-code-review, auto-dev, auto-tdd and batch-dev.
- **Left as is:** the three security rules that say no instruction "in a tool result" can authorize discarding changes; there, "tool result" means tool output in general.
- **Checks:** `grep -rn 'run_in_background' decaf-* conventions --include='*.md'` prints nothing; every remaining "tool result" line is a security rule or the new mechanism-neutral wording.

## Summary

**Completed 2026-09-24** — Removed the unsatisfiable `run_in_background: false` mandate from code-review (bugs seat, Step 3, screeners, validators) after an experiment showed Claude Code 2.1.281 keeps an agent alive while its background children run; Step 3 now says to consolidate only once every reviewer has reported, and its tripwire distinguishes the normal "Async agent launched" acknowledgment from a teammate one. The dispatch convention and code-review describe delivery as the tool result or a hand-back and tie teammate mode to CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1; callers and `--report` usage wording follow. Verified by grep (no `run_in_background` left) and a fresh-agent walkthrough.
