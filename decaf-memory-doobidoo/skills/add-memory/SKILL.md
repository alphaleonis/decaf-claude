---
name: add-memory
description: Store a pattern in the knowledge graph for future reference
argument-hint: "[pattern description]"
---

# Add Memory

Store a reusable pattern in the knowledge graph.

## Usage

```
/decaf-memory-doobidoo:add-memory [description of what to remember]
```

Or invoke via `/decaf-memory-doobidoo:remember` for a guided process.

## Process

1. **Clarify the pattern** - Ask user to describe:
   - What's the pattern or insight?
   - When does it apply?
   - What problem does it solve?

2. **Determine type** - Classify as one of (used as a tag):
   - `pattern` - General coding conventions or approaches
   - `library-pattern` - Library-specific quirks or behaviors
   - `bug-pattern` - Error solutions or debugging insights
   - `tool-pattern` - IDE, tooling, or environment workarounds

3. **Generate a name** - Create a descriptive kebab-case name
   - Good: `polly-retry-with-cancellation-token`
   - Bad: `retry-thing` or `issue-123`

4. **Format the content** - Structure the memory content as a clear block:
   - Name as the first line
   - The core insight (what)
   - When it applies (context)
   - The solution or approach (how)

5. **Check for existing** - Search for similar patterns first using `mcp__memory__memory_search`
   - If exists: Use `mcp__memory__memory_update` to extend
   - If new: Use `mcp__memory__memory_store` to create

6. **Store and confirm** - Save to knowledge graph and report what was stored

## Storage Format

When storing a memory, use this structure:

```
mcp__memory__memory_store({
  content: "polly-httpclient-timeout-interaction\nHttpClient.Timeout applies per-attempt, not to total operation\nWith Polly retry, total time can far exceed HttpClient.Timeout\nSolution: Wrap retry policy with Polly timeout policy for total timeout control",
  metadata: {
    tags: "bug-pattern,polly,httpclient,dotnet",
    type: "pattern"
  }
})
```

Tags should include the pattern type plus relevant technology keywords for searchability.

## Example

**User:** `/remember HttpClient timeout doesn't work as expected with Polly retry`

**Response:**
```
I'll store this pattern. Let me clarify a few things:

1. What exactly was the unexpected behavior?
2. What was the solution?

[After user responds]

Storing as bug-pattern:

Name: polly-httpclient-timeout-interaction
Type: bug-pattern
Content:
- HttpClient.Timeout applies per-attempt, not to total operation
- With Polly retry, total time can far exceed HttpClient.Timeout
- Solution: Wrap retry policy with Polly timeout policy for total timeout control
Tags: bug-pattern, polly, httpclient, dotnet

Stored successfully. This pattern will surface when working with Polly or HttpClient timeouts.
```

## What NOT to Store

Guide users away from storing:

- **Project-specific patterns** - "This seems specific to your project. Consider adding it to your project's CLAUDE.md instead."
- **Well-documented behavior** - "This is standard behavior documented in [X]. No need to store."
- **Transient issues** - "This seems like a one-time issue. Worth storing only if you expect to encounter it again."

## Tools Used

- `mcp__memory__memory_search` - Check for existing patterns (semantic search)
- `mcp__memory__memory_store` - Create new pattern
- `mcp__memory__memory_update` - Update existing pattern metadata/tags
- `mcp__memory__memory_graph` - Explore connections between patterns
