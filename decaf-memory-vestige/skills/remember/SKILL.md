---
name: remember
description: Store a memory in Vestige for future reference
argument-hint: "[what to remember]"
---

# Remember

Store a memory in Vestige's cognitive memory system.

## Prerequisites

Check that `mcp__vestige__smart_ingest` is available in your tools. If not, tell the user:

> Vestige MCP server is not connected. Run `claude mcp add vestige vestige-mcp -s user` and restart Claude Code.

## Usage

```
/decaf-memory-vestige:remember [description of what to remember]
```

## Process

1. **Clarify if needed** — If the user's input is vague, ask what they want to remember and why it matters.

2. **Classify the memory**:
   - `fact` — A piece of knowledge or preference
   - `pattern` — A reusable approach or convention
   - `decision` — An architectural or design choice
   - `event` — Something that happened (bug fix, incident, etc.)

3. **Choose the right tool**:
   - For code patterns → `mcp__vestige__codebase({ action: "remember_pattern", ... })`
   - For architectural decisions → `mcp__vestige__codebase({ action: "remember_decision", ... })`
   - For everything else → `mcp__vestige__smart_ingest({ ... })`

4. **Store it** — No need to search first. `smart_ingest` handles deduplication automatically. It will create a new memory, merge with an existing one, or skip if identical content already exists.

5. **Confirm** — Tell the user what was stored and how it was classified.

## Examples

**User:** `/remember HttpClient timeout doesn't work as expected with Polly retry`

**Response:**
```
I'll store this. Can you clarify:
1. What was the unexpected behavior?
2. What was the solution?

[After user responds]

Stored as bug-fix pattern:
- HttpClient.Timeout is per-attempt, not total
- Polly retry can exceed expected total timeout
- Solution: Wrap retry policy with Polly timeout policy
Tags: bug-fix, polly, httpclient, dotnet
```

**User:** `/remember I prefer tabs over spaces`

**Response:**
```
Stored as preference: "User prefers tabs over spaces for indentation"
```

## What NOT to Store

Guide users away from storing:
- **Project-specific patterns** → suggest adding to project CLAUDE.md instead
- **Well-documented behavior** → no need to store what's in the docs
- **Secrets or credentials** → never store sensitive data
- **Transient issues** → only store if likely to recur
