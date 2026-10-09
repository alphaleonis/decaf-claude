---
# dcc-642p
version: 1
title: Tool-use backstop for write-comments if the pointer is ignored
status: draft
type: task
priority: low
created_at: 2026-10-09T21:03:07Z
updated_at: 2026-10-09T21:03:07Z
parent: dcc-ghl5
blocked_by:
    - dcc-ghl5
order: a0
---

Apply only if agents skip `/decaf-quality:write-comments` despite the SessionStart/SubagentStart pointer.

A non-blocking backstop:

- `PreToolUse` on the `Skill` tool records `session_id` + `agent_id` when `write-comments` is invoked (state under `${CLAUDE_PLUGIN_DATA}`).
- `PostToolUse` on `Edit|Write` for source files: if this agent has no record, add `additionalContext` once — "Invoke `/decaf-quality:write-comments` now and check the comments in the edit you just made."

Unverified: that `Skill` tool calls fire `PreToolUse`. Test before building.
Known gaps: edits made through Bash bypass the matcher; the source-file filter is an extension list.

Rejected alternative: `PreToolUse` deny-once on the first edit (rules in the deny reason). Untested how agents react to a large deny reason; costs a round trip per writing agent.
