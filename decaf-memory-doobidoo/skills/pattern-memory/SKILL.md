---
name: pattern-memory
description: Check knowledge graph for relevant patterns when working with libraries, debugging errors, or starting tasks in familiar tech stacks. Store new reusable patterns after solving non-trivial problems.
user-invocable: false
---

# Pattern Memory

You have access to a persistent knowledge graph for storing and retrieving cross-project patterns.

## When to Query

Before starting work, search the knowledge graph if the task involves:

- A specific library or framework you've used before
- An error message or exception type
- A tech stack with known conventions (PowerShell, C#, Azure, etc.)
- A problem that feels familiar

**Query tools:**
- `mcp__plugin_decaf-memory-doobidoo_memory__memory_search` - Semantic search by topic/keyword (preferred — finds conceptually similar results even with different wording)
- `mcp__plugin_decaf-memory-doobidoo_memory__memory_list` - Browse patterns filtered by tags

## When to Store

After solving a problem, store it if:

- The pattern applies to multiple projects (not project-specific)
- It's a library quirk, workaround, or non-obvious behavior
- It's an error solution you'd want to remember months from now
- You discovered a tool or technique worth preserving

**Do NOT store:**
- Project-specific conventions (those belong in project CLAUDE.md)
- Obvious or well-documented behavior
- One-time fixes for transient issues

## Pattern Types

Use these as tags when storing memories:

| Tag | Use For | Example |
|-----|---------|---------|
| `pattern` | Coding conventions, approaches | "async-cancellation-pattern" |
| `library-pattern` | Library-specific quirks | "polly-retry-with-timeout" |
| `bug-pattern` | Error solutions | "sqlclient-connection-pool-exhaustion" |
| `tool-pattern` | IDE/tooling workarounds | "rider-debugger-async-locals" |

## Storage Format

When storing memories, structure content clearly and use tags for categorization:

```
mcp__plugin_decaf-memory-doobidoo_memory__memory_store({
  content: "pattern-name\nKey insight or behavior\nWhen this applies\nThe solution or workaround\nRelated technologies: X, Y, Z",
  metadata: {
    tags: "pattern-type,technology1,technology2",
    type: "pattern"
  }
})
```

## Example Workflow

**Querying:**
```
User: "I need to implement retry logic with Polly"
→ Search: mcp__plugin_decaf-memory-doobidoo_memory__memory_search({query: "polly retry"})
→ Found: pattern about polly-retry-with-timeout
→ Apply pattern to current task
```

**Storing:**
```
Solved: HttpClient timeout not respected when using Polly retry
→ Store:
  mcp__plugin_decaf-memory-doobidoo_memory__memory_store({
    content: "polly-httpclient-timeout-interaction\nHttpClient.Timeout is per-attempt, not total\nPolly retry can exceed expected total timeout\nSolution: Use Polly timeout policy wrapping retry policy",
    metadata: {
      tags: "bug-pattern,polly,httpclient,dotnet",
      type: "pattern"
    }
  })
```

## Tools Used

- `mcp__plugin_decaf-memory-doobidoo_memory__memory_search` - Semantic search for patterns
- `mcp__plugin_decaf-memory-doobidoo_memory__memory_store` - Create new pattern
- `mcp__plugin_decaf-memory-doobidoo_memory__memory_update` - Update existing pattern
- `mcp__plugin_decaf-memory-doobidoo_memory__memory_graph` - Explore connections between patterns
