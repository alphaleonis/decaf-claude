---
name: init-memory
description: Manually load Vestige session context — use when the automatic startup hook didn't trigger the call
argument-hint: ""
---

# Initialize Memory

Manual fallback to load Vestige session context. Use this when the automatic `SessionStart` hook fired but the `session_context` call was not made.

## Prerequisites

Check that `mcp__vestige__session_context` is available in your tools. If not, tell the user:

> Vestige MCP server is not connected. Run `claude mcp add vestige vestige-mcp -s user` and restart Claude Code.

## Process

1. **Call `session_context`** with broad queries and the current project context:

   ```
   mcp__vestige__session_context({
     queries: ["user preferences", "instructions", "feedback"],
     context: {
       codebase: "[current project name if applicable]",
       topics: ["[relevant topics from recent messages]"]
     },
     include_intentions: true,
     include_predictions: true,
     token_budget: 1500
   })
   ```

2. **Confirm** to the user that memory context has been loaded, and briefly summarize what was retrieved (number of memories, any triggered intentions or predictions).
