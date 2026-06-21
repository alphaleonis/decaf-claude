// Erinra session start hook — outputs memory protocol as additionalContext.
// Runs on every session start, resume, clear, and context compaction.
// Uses Node.js for cross-platform compatibility (Windows + Linux + macOS).

console.log(`# Erinra Memory Guide

You have access to **erinra**, a memory MCP server with hybrid semantic search (vector + FTS5 + RRF). The tools are prefixed \`mcp__erinra__\`.

If \`mcp__erinra__context\` is not available in your tools, warn the user:
"Erinra MCP server is not connected. Memory features are unavailable. To set up erinra, run: \`claude mcp add erinra -- erinra serve -s user\` and restart Claude Code."

## Available Tools

| Tool | Purpose |
|------|---------|
| \`context\` | Batched retrieval: multi-query search + taxonomy in one call. Use to load session context. |
| \`store\` | Save a memory. Returns top-3 similar existing memories for dedup. |
| \`search\` | Hybrid search (vector + keyword via RRF). Natural language queries work best. |
| \`get\` | Fetch full content of specific memories by ID. |
| \`list\` | Browse/filter memories without a search query. |
| \`update\` | Update an existing memory's content or metadata. |
| \`merge\` | Combine two memories into one. |
| \`link\` / \`unlink\` | Connect/disconnect related memories (related_to, caused_by, context_for, supersedes). |
| \`archive\` | Non-destructive removal. Prefer over delete. |
| \`discover\` | Refresh the full taxonomy (projects, types, tags, relations, stats). |

## When to Search

Search erinra **before answering** when the task involves:
- A specific library, framework, or tool the user has used before
- An error message that may have been solved previously
- A codebase with known patterns or decisions
- A question about user preferences or past decisions

## When to Store

**After solving a bug:** content "BUG FIX: [error] | Root cause: [why] | Solution: [how]", tags: ["bug-fix"], projects: [project-name]
**After learning user preferences:** store immediately with type: "preference"
**After architectural decisions:** store with type: "decision", tags describing the domain
**After discovering code patterns:** store with type: "pattern", projects: [project-name]

### Trigger Words — Auto-Save When User Says

- "Remember this" / "Don't forget" → store immediately
- "I always..." / "I never..." / "I prefer..." → store as type: "preference"
- "This is important" → store immediately

## Deduplication

Erinra does NOT deduplicate automatically. The \`store\` tool returns the top-3 most similar existing memories. Before storing, check the response:
- If the new content supersedes the old: \`update\` the existing memory
- If they should be combined: \`merge\` them
- If the existing one is sufficient: skip storing

## What NOT to Store

Secrets, API keys, credentials, tokens. Temporary debugging state. Trivial or well-documented behavior. Project-specific conventions that belong in CLAUDE.md.

## Loading Session Context

When you need broad context (e.g., starting work on a project, or the user asks about past decisions), use the batched \`context\` tool:

\`\`\`
mcp__erinra__context({
  queries: ["user preferences and instructions", "recent decisions and patterns"],
  include_taxonomy: true,
  content_budget: 2000,
  limit: 10
})
\`\`\`

## Tips

- \`store\` returns similar memories — use them to decide whether to update, merge, or skip.
- Search strengthens memory — every search updates access_count. Search liberally.
- Use \`projects\` to scope memories to codebases. Use \`tags\` for cross-cutting concerns.
- Use \`links\` to connect related memories.
- Use \`archive\` instead of delete — it's non-destructive.`);
