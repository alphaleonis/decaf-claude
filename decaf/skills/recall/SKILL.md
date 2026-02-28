---
name: recall
description: Search the knowledge graph for stored patterns
argument-hint: "[search query]"
---

# Recall Pattern

Search the knowledge graph for previously stored patterns.

## Usage

```
/decaf:recall [search query]
```

Examples:
- `/decaf:recall HttpClient timeout` - Find patterns related to HttpClient timeouts
- `/decaf:recall Polly retry` - Find patterns about Polly retry policies
- `/decaf:recall GitHub MCP` - Find tool preferences or patterns about GitHub

## Process

1. **Search the knowledge graph** using `mcp__memory__search_nodes` with the provided query
2. **Display matching patterns** with their:
   - Name
   - Type (pattern, library-pattern, bug-pattern, tool-pattern)
   - Observations (the stored insights)
3. **If no results**, suggest:
   - Trying different keywords
   - Using `/decaf:remember` to store a new pattern

## Tools Used

- `mcp__memory__search_nodes` - Search for patterns by keyword
- `mcp__memory__open_nodes` - Get full details of specific patterns
- `mcp__memory__read_graph` - Browse all stored patterns (use sparingly)

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
