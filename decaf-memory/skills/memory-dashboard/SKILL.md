---
name: memory-dashboard
description: Open the Vestige 3D memory dashboard in the browser
---

# Memory Dashboard

Open the Vestige 3D memory visualization dashboard.

## Process

Run the following command to open the dashboard:

```bash
xdg-open http://localhost:3927/dashboard 2>/dev/null || open http://localhost:3927/dashboard 2>/dev/null || echo "Open http://localhost:3927/dashboard in your browser"
```

The dashboard shows a real-time 3D neural graph of your memories, retention curves, and memory health. It runs automatically when the Vestige MCP server is active on port 3927.

If the dashboard doesn't load, verify that the Vestige MCP server is running.
