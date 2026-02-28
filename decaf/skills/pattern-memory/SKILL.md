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
- `mcp__memory__search_nodes` - Search by topic/keyword
- `mcp__memory__read_graph` - Browse full graph structure
- `mcp__memory__open_nodes` - Get details on specific entities

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

## Entity Types

Use these types when creating entities:

| Type | Use For | Example |
|------|---------|---------|
| `pattern` | Coding conventions, approaches | "async-cancellation-pattern" |
| `library-pattern` | Library-specific quirks | "polly-retry-with-timeout" |
| `bug-pattern` | Error solutions | "sqlclient-connection-pool-exhaustion" |
| `tool-pattern` | IDE/tooling workarounds | "rider-debugger-async-locals" |

## Storage Tools

- `mcp__memory__create_entities` - Create new pattern entity
- `mcp__memory__add_observations` - Add details to existing entity
- `mcp__memory__create_relations` - Link related patterns

## Entity Structure

When creating entities:

```
name: descriptive-kebab-case-name
entityType: pattern | library-pattern | bug-pattern | tool-pattern
observations:
  - "Key insight or behavior"
  - "When this applies"
  - "The solution or workaround"
  - "Related technologies: X, Y, Z"
```

## Example Workflow

**Querying:**
```
User: "I need to implement retry logic with Polly"
→ Search: mcp__memory__search_nodes({query: "polly retry"})
→ Found: "polly-retry-with-timeout" pattern with observations
→ Apply pattern to current task
```

**Storing:**
```
Solved: HttpClient timeout not respected when using Polly retry
→ Create entity:
  name: "polly-httpclient-timeout-interaction"
  entityType: "bug-pattern"
  observations:
    - "HttpClient.Timeout is per-attempt, not total"
    - "Polly retry can exceed expected total timeout"
    - "Solution: Use Polly timeout policy wrapping retry policy"
    - "Technologies: Polly, HttpClient, .NET"
```
