// Erinra session start hook — outputs memory protocol as additionalContext.
// Runs on every session start, resume, clear, and context compaction.
// Uses Node.js for cross-platform compatibility (Windows + Linux + macOS).

console.log(`# Erinra Memory Protocol

You have access to erinra, a memory MCP server with hybrid semantic search (vector + FTS5 + RRF). Use it proactively.

## Session Start — DO THIS NOW

Load context with a single call:

mcp__erinra__context({
  queries: ["user preferences and instructions", "recent decisions and patterns"],
  include_taxonomy: true,
  content_budget: 2000,
  limit: 10
})

This returns deduplicated memories across all queries within the content budget, plus the full taxonomy (projects, types, tags, relations, stats).

If mcp__erinra__context is not available in your tools, warn the user:
"Erinra MCP server is not connected. Memory features are unavailable. To set up erinra, run: claude mcp add erinra -- erinra serve -s user and restart Claude Code."

## Automatic Saves — No Permission Needed

After solving a bug: store with content "BUG FIX: [error] | Root cause: [why] | Solution: [how]", tags: ["bug-fix"], projects: [project-name]
After learning user preferences: store immediately (coding style, libraries, communication, tools, workflows) with type: "preference"
After architectural decisions: store with type: "decision", tags describing the domain
After discovering code patterns: store with type: "pattern", projects: [project-name]

## Trigger Words — Auto-Save When User Says

"Remember this" / "Don't forget" -> store immediately
"I always..." / "I never..." / "I prefer..." -> store as type: "preference"
"This is important" -> store immediately

## During Work

- Notice a pattern? store with type: "pattern"
- Made a decision? store with type: "decision"
- Need to find something? search with relevant query
- Related memories? use links parameter when storing, or link after the fact

## Automatic Context Detection

When working, proactively search erinra if the task involves:
- A specific library or framework -> search for known patterns
- An error message -> search for previous solutions
- A codebase -> search with projects filter

## Proactive Behaviors

DO automatically:
- Save solutions after fixing problems
- Note user corrections as preferences
- Search before answering technical questions

DON'T ask permission to:
- Save bug fixes
- Update preferences
- Search for context

## Deduplication

Erinra does NOT deduplicate automatically. The store tool returns the top-3 most similar existing memories. Before storing, check if a similar memory already exists in the response. If so:
- If the new content supersedes the old: update the existing memory instead of creating a new one
- If they should be combined: use merge to combine them
- If the existing one is sufficient: skip storing

## What NOT to Store

Secrets, API keys, credentials, tokens. Temporary debugging state. Trivial or well-documented behavior. Project-specific conventions that belong in CLAUDE.md.

## Key Behaviors

- Store returns similar memories — use them to decide whether to update, merge, or skip.
- Search uses hybrid ranking (vector + keyword via RRF). Natural language queries work best.
- Search strengthens memory — every search updates access_count. Search liberally.
- Memory is retrieval. When in doubt, search erinra first. If nothing found, solve the problem, then save the solution.
- Use projects to scope memories to codebases. Use tags for cross-cutting concerns.
- Use links to connect related memories (related_to, caused_by, context_for, supersedes).
- Use archive instead of delete — it's non-destructive.
- Use get to fetch full content of specific memories by ID.
- Use list to browse/filter memories without a search query.`);
