---
name: add-memory
description: Store a pattern in the knowledge graph for future reference
argument-hint: "[pattern description]"
---

# Add Memory

Store a reusable pattern in the knowledge graph.

## Usage

```
/decaf:add-memory [description of what to remember]
```

Or invoke via `/decaf:remember` for a guided process.

## Process

1. **Clarify the pattern** - Ask user to describe:
   - What's the pattern or insight?
   - When does it apply?
   - What problem does it solve?

2. **Determine type** - Classify as one of:
   - `pattern` - General coding conventions or approaches
   - `library-pattern` - Library-specific quirks or behaviors
   - `bug-pattern` - Error solutions or debugging insights
   - `tool-pattern` - IDE, tooling, or environment workarounds

3. **Generate entity name** - Create a descriptive kebab-case name
   - Good: `polly-retry-with-cancellation-token`
   - Bad: `retry-thing` or `issue-123`

4. **Extract observations** - Break down into discrete facts:
   - The core insight (what)
   - When it applies (context)
   - The solution or approach (how)
   - Related technologies (tags)

5. **Check for existing** - Search for similar patterns first
   - If exists: Use `add_observations` to extend
   - If new: Use `create_entities` to create

6. **Store and confirm** - Save to knowledge graph and report what was stored

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
Observations:
- HttpClient.Timeout applies per-attempt, not to total operation
- With Polly retry, total time can far exceed HttpClient.Timeout
- Solution: Wrap retry policy with Polly timeout policy for total timeout control
- Technologies: Polly, HttpClient, .NET

Stored successfully. This pattern will surface when working with Polly or HttpClient timeouts.
```

## What NOT to Store

Guide users away from storing:

- **Project-specific patterns** → "This seems specific to your project. Consider adding it to your project's CLAUDE.md instead."
- **Well-documented behavior** → "This is standard behavior documented in [X]. No need to store."
- **Transient issues** → "This seems like a one-time issue. Worth storing only if you expect to encounter it again."

## Tools Used

- `mcp__memory__search_nodes` - Check for existing patterns
- `mcp__memory__create_entities` - Create new pattern
- `mcp__memory__add_observations` - Extend existing pattern
- `mcp__memory__create_relations` - Link related patterns
