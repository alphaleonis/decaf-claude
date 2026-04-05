---
name: recall
description: Search erinra for stored memories
argument-hint: "[search query]"
---

# Recall

Search erinra for previously stored memories.

## Prerequisites

Check that `mcp__erinra__search` is available in your tools. If not, tell the user:

> Erinra MCP server is not connected. Run `claude mcp add erinra -- erinra serve -s user` and restart Claude Code.

## Usage

```
/decaf-memory:recall [search query]
```

Examples:
- `/recall HttpClient timeout` — Find memories about HttpClient timeouts
- `/recall user preferences` — Retrieve stored user preferences
- `/recall polly retry` — Find patterns about Polly retry policies

## Process

1. **Search** using `mcp__erinra__search` with the user's query:
   ```
   mcp__erinra__search({
     query: "[user's search terms]",
     limit: 10
   })
   ```

2. **Display results** showing:
   - Content (the memory itself)
   - Type
   - Tags
   - Projects
   - Score (relevance)
   - Links (outgoing and incoming relationships)

3. **If no results**, suggest:
   - Trying different keywords
   - Using `/decaf-memory:remember` to store something new

## Filtering

Use filters to narrow results:

```
mcp__erinra__search({
  query: "[search terms]",
  projects: ["project-name"],       // Filter by project (OR across projects)
  type: "pattern",                  // Filter by exact type
  tags: ["dotnet", "async"],        // Filter by tags (AND — must have all)
  include_archived: false,          // Default: false
  limit: 10
})
```

### Time filters

Narrow by when memories were created or last updated:

```
mcp__erinra__search({
  query: "[search terms]",
  created_max_age_days: 30,         // Created within the last 30 days
  updated_after: "2025-01-01T00:00:00Z"  // Updated after a specific date
})
```

Available time filters: `created_after`, `created_before`, `updated_after`, `updated_before`, `created_max_age_days`, `created_min_age_days`, `updated_max_age_days`, `updated_min_age_days`.

## Browsing (no query)

To browse memories without a search query, use `mcp__erinra__list` instead:

```
mcp__erinra__list({
  projects: ["project-name"],
  type: "decision",
  limit: 20
})
```

This supports the same filters as search but returns paginated results with a total count.

## Fetching Full Content

Search results may truncate long content. To get the full text of a memory:

```
mcp__erinra__get({ ids: ["[memory-id]"] })
```

## Exploring Links

Search results include outgoing and incoming links. To follow a link and see the related memory:

```
mcp__erinra__get({ ids: ["[linked-memory-id]"] })
```
