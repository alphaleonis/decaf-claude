---
# dcc-k163
version: 1
title: Record each subagent's actual token spend in --report session reports
status: completed
type: feature
tags:
    - code-review
created_at: 2026-11-03T15:07:53Z
updated_at: 2026-11-03T17:09:56Z
parent: dcc-b578
order: a0
---

Record each subagent's actual token spend in `--report` session reports, so cost comparisons between presets and reviewers rest on measurements instead of the turn-weighted estimate. Recommendation 1 of the dcc-s612 corpus analysis.

## Problem

Every token figure in a code-review report is the subagent's `totalTokens`, which counts only its final API request. The hooks docs say so: "Token count from the subagent's final API request ... This isn't a total across the whole run." Actual spend is that figure times a multiplier that depends on how many requests the agent made: about 3× for `finding-validator` and about 23× for `solo-reviewer` (median, 5,198 subagent transcripts on disk on 2026-11-03). So reported figures misrank agents by cost, not just misscale them.

## Approach

`decaf-quality/scripts/agent-spend.js <agent-id>...` finds each subagent's transcript (`<config>/projects/*/*/subagents/agent-<id>.jsonl`, `<config>` being `CLAUDE_CONFIG_DIR` or `~/.claude`), sums `message.usage` once per `message.id`, and prints a Markdown table: agent ID, agent type, requests, input, output, cache read, cache write, spend. One API response is written as several records repeating its usage; in 4 of 8,610 repeated responses the last record carries a higher output count, so the last record wins.

It runs only under `--report`, which spends no tokens otherwise (operator constraint, 2026-11-03):

- `code-review --report` records each agent's ID as its result arrives, runs the script once over the wave before writing Session Metrics, and pastes the table under **Spend**. The harness figure moves to a "Final request" column.
- `auto-code-review --report` records the IDs of the implementer, review orchestrators, fresh fixers and fix-verifiers, and runs the script once over them in Step 6.5.
- `conventions/session-report.md` states that the harness figure is the final request, that spend comes from the script, and that per-agent spend excludes children, so it sums without double counting.

Verified 2026-11-03: `scripts/check-agent-spend-meter.sh` runs a headless Haiku session with one subagent; the summed transcripts equal the session's metered `modelUsage` on all four components.

Rejected: a `SubagentStop` hook writing a log for every subagent. It costs no model tokens, but it does work in every session; the transcripts are still on disk when a report is written, so the `--report` path can read them directly. OpenTelemetry counters replace non-official agent names with `"custom"` and never carry `agent_id`; `api_request` events need telemetry and a collector running.

## Acceptance

- [x] [run] `node --test decaf-quality/scripts/` — expect: all pass, including one response written as several records counted once, with the last record's output
- [x] [run] `scripts/check-agent-spend-meter.sh` — expect: exit 0, `ok` on input, output, cacheRead and cacheWrite. Spends a little Haiku usage; rerun after a Claude Code update, since the transcript format is undocumented.
- [x] [run] `scripts/check-skill-references.sh` — expect: exit 0
- [x] [manual] A `code-review --report` run shows a Spend table whose rows match its agents. Reason: the report is written by the orchestrator, not by code a test can call.

## Summary

**Completed 2026-11-03** — Built decaf-quality/scripts/agent-spend.js, which sums a subagent's transcript once per message id, and wired it into code-review, auto-code-review and the session-report convention under --report only; the harness figure is now recorded as Final request. No SubagentStop hook: the transcripts are on disk at report time, so nothing runs without --report. Verified by the unit tests, the headless meter check (exact match on all four components) and a bibbla code-review --report run on 2026-11-03 whose 14-agent Spend table matched a re-run of the script.
