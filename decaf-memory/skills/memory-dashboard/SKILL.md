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

Run `erinra dash --open-only` to open the dashboard in the default browser:

```bash
erinra dash --open-only
```

This reads the daemon state, constructs an authenticated URL, opens the browser, and exits immediately. It requires the daemon to already be running (started by `erinra serve --web`).

If the command fails, tell the user their MCP server may not be configured with `--web`. Suggest updating their MCP configuration:

```bash
claude mcp remove erinra
claude mcp add erinra -- erinra serve --web -s user
```

## Notes

- Port and bind address are configurable via `~/.erinra/config.toml` under `[web]`, or via `--port` / `--bind` flags on `erinra serve`
- The daemon auto-shuts down 60 seconds after the last client (MCP server) disconnects
