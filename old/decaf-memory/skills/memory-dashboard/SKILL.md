---
name: memory-dashboard
description: Open the erinra memory dashboard in the browser
---

# Memory Dashboard

Open the erinra memory visualization dashboard.

## Prerequisites

The erinra MCP server must be running with `--web` so the dashboard daemon is available. The recommended MCP setup:

```bash
claude mcp add erinra -- erinra serve --web -s user
```

## Process

1. **Ensure the MCP server is alive.** If you have NOT called any `mcp__erinra__*` tool earlier in this session, call `mcp__erinra__context` first to wake the server and start the web daemon:

   ```
   mcp__erinra__context({
     queries: ["user preferences"],
     include_taxonomy: true,
     content_budget: 500,
     limit: 5
   })
   ```

   If you have already interacted with erinra MCP tools in this session, skip this step.

2. **Open the dashboard.** Run `erinra dash --open-only` to open it in the default browser:

   ```bash
   erinra dash --open-only
   ```

   This reads the daemon state, constructs an authenticated URL, opens the browser, and exits immediately.

If the command fails, tell the user their MCP server may not be configured with `--web`. Suggest updating their MCP configuration:

```bash
claude mcp remove erinra
claude mcp add erinra -- erinra serve --web -s user
```

## Notes

- Port and bind address are configurable via `~/.erinra/config.toml` under `[web]`, or via `--port` / `--bind` flags on `erinra serve`
- The daemon auto-shuts down 60 seconds after the last client (MCP server) disconnects
