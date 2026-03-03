---
name: recall
description: Search the knowledge graph for stored patterns
argument-hint: "[search query]"
---

# Recall Pattern

Search the knowledge graph for previously stored patterns.

## Usage

```
/decaf-memory-doobidoo:recall [search query]
```

Examples:
- `/decaf-memory-doobidoo:recall HttpClient timeout` - Find patterns related to HttpClient timeouts
- `/decaf-memory-doobidoo:recall Polly retry` - Find patterns about Polly retry policies
- `/decaf-memory-doobidoo:recall GitHub MCP` - Find tool preferences or patterns about GitHub

## Process

1. **Search the knowledge graph** using `mcp__memory-service__memory_search` with the provided query (mode: `semantic` for best results)
2. **Display matching patterns** with their:
   - Content
   - Tags (pattern type: pattern, library-pattern, bug-pattern, tool-pattern)
   - Metadata
3. **If no results**, suggest:
   - Trying different keywords
   - Using `/decaf-memory-doobidoo:remember` to store a new pattern

## Tools Used

- `mcp__memory-service__memory_search` - Semantic search for patterns by keyword (default mode)
- `mcp__memory-service__memory_list` - Browse stored patterns with tag filtering

## Example Output

```
Found 2 patterns matching "HttpClient":

## prefer-github-mcp-over-gh-cli (tool-pattern)
- Use the GitHub MCP server tools (mcp__github__*) instead of the gh CLI
- GitHub MCP provides authenticated access without needing separate gh auth
- Technologies: GitHub, MCP, Claude Code

## polly-httpclient-timeout-interaction (bug-pattern)
- HttpClient.Timeout applies per-attempt, not to total operation
- With Polly retry, total time can far exceed HttpClient.Timeout
- Solution: Wrap retry policy with Polly timeout policy
- Technologies: Polly, HttpClient, .NET
```
