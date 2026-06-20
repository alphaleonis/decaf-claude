---
name: init-memory
description: Manually load erinra session context — use when the automatic startup hook didn't trigger the call
argument-hint: ""
---

# Initialize Memory

Manual fallback to load erinra session context. Use this when the automatic `SessionStart` hook fired but the memory context was not loaded.

## Prerequisites

Check that `mcp__erinra__context` is available in your tools. If not, tell the user:

> Erinra MCP server is not connected. Run `claude mcp add erinra -- erinra serve -s user` and restart Claude Code.

## Process

1. **Load context** — use the batched `context` tool to retrieve taxonomy and relevant memories in a single call:

   ```
   mcp__erinra__context({
     queries: ["user preferences and instructions", "recent decisions and patterns"],
     include_taxonomy: true,
     content_budget: 2000,
     limit: 10
   })
   ```

   This returns deduplicated memories across all queries within the content budget, plus the full taxonomy (projects, types, tags, relations, stats).

2. **Confirm** to the user that memory context has been loaded, and briefly summarize what was retrieved (number of memories, projects, types found).
