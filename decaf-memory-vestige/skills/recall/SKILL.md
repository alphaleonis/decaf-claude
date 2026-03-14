---
name: recall
description: Search Vestige for stored memories
argument-hint: "[search query]"
---

# Recall

Search Vestige's cognitive memory system for previously stored memories.

## Prerequisites

Check that `mcp__vestige__search` is available in your tools. If not, tell the user:

> Vestige MCP server is not connected. Run `claude mcp add vestige vestige-mcp -s user` and restart Claude Code.

## Usage

```
/decaf-memory-vestige:recall [search query]
```

Examples:
- `/recall HttpClient timeout` — Find memories about HttpClient timeouts
- `/recall user preferences` — Retrieve stored user preferences
- `/recall polly retry` — Find patterns about Polly retry policies

## Process

1. **Search** using `mcp__vestige__search` with the user's query:
   ```
   mcp__vestige__search({
     query: "[user's search terms]",
     limit: 10,
     detail_level: "summary"
   })
   ```

2. **Display results** showing:
   - Content (the memory itself)
   - Tags
   - Type (fact, pattern, decision, event)
   - Retention strength (how well-remembered it is)

3. **If no results**, suggest:
   - Trying different keywords
   - Using `/decaf-memory-vestige:remember` to store something new

4. **If results are helpful**, promote them:
   ```
   mcp__vestige__memory({ action: "promote", id: "[memory_id]" })
   ```
   This strengthens the memory so it surfaces more easily next time.

## For Code-Specific Queries

When searching for code patterns or decisions in a specific project, use the codebase tool instead:

```
mcp__vestige__codebase({
  action: "get_context",
  codebase: "[project-name]",
  limit: 10
})
```

## Exploring Connections

If the user wants to understand how memories relate to each other:

```
mcp__vestige__explore_connections({
  action: "associations",
  from: "[memory_id]",
  limit: 10
})
```
