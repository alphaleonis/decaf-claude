---
name: vestige-init
description: Initialize Vestige cognitive memory system. Provides session startup, automatic memory behaviors, and proactive save/recall patterns. Loaded automatically on plugin activation.
user-invocable: false
---

# Vestige Memory Protocol

You have access to Vestige, a cognitive memory system with semantic search, spaced repetition (FSRS-6), and automatic deduplication. Use it proactively.

## Prerequisites Check

Before using any Vestige functionality, verify the MCP server is available by checking for `mcp__vestige__search` in your available tools.

**If Vestige tools are NOT available**, warn the user:

> Vestige MCP server is not connected. Memory features are unavailable.
> To set up Vestige, run: `claude mcp add vestige vestige-mcp -s user`
> Then restart Claude Code.

If the tools are not available, do not attempt to call them — skip all memory behaviors described below.

## Session Start

At the beginning of every conversation, load context with a single call:

```
mcp__vestige__session_context({
  queries: ["user preferences", "instructions"],
  context: {
    codebase: "[current project name if applicable]",
    topics: ["[relevant topics from user's first message]"]
  },
  include_intentions: true,
  include_predictions: true,
  token_budget: 1500
})
```

This retrieves user preferences, project context, triggered intentions, and predictions in one call.

## Automatic Saves — No Permission Needed

### After solving a bug or error
```
mcp__vestige__smart_ingest({
  content: "BUG FIX: [error message] | Root cause: [why] | Solution: [how]",
  node_type: "event",
  tags: ["bug-fix", "[project-name]"]
})
```

### After learning user preferences
Save immediately when the user expresses preferences about coding style, libraries, communication, tools, or workflows:
```
mcp__vestige__smart_ingest({
  content: "[preference description]",
  node_type: "fact",
  tags: ["preference"]
})
```

### After architectural decisions
```
mcp__vestige__codebase({
  action: "remember_decision",
  codebase: "[project-name]",
  decision: "[what was decided]",
  rationale: "[why]",
  alternatives: ["[option A]", "[option B]"],
  files: ["[affected files]"]
})
```

### After discovering code patterns
```
mcp__vestige__codebase({
  action: "remember_pattern",
  codebase: "[project-name]",
  name: "[pattern-name]",
  description: "[how and when to use it]",
  files: ["[where it's used]"]
})
```

## Trigger Words — Auto-Save When User Says

| User says | Action |
|-----------|--------|
| "Remember this" / "Don't forget" | `smart_ingest` immediately |
| "I always..." / "I never..." / "I prefer..." | Save as preference |
| "This is important" | `smart_ingest` + `memory(action="promote")` |
| "Remind me..." / "Next time..." | `intention(action="set")` with appropriate trigger |

## Automatic Context Detection

When working, proactively search Vestige if the task involves:
- A specific library or framework → search for known patterns
- An error message → search for previous solutions
- A codebase → `codebase(action="get_context")` for patterns and decisions

## Memory Feedback

- **When a memory proves helpful**: `mcp__vestige__memory({ action: "promote", id: "[id]" })`
- **When a memory is wrong or misleading**: `mcp__vestige__memory({ action: "demote", id: "[id]" })`
- User explicitly confirms a memory was helpful → promote it
- User corrects a memory → demote it and store the correction

## What NOT to Store

- Secrets, API keys, credentials, tokens
- Temporary debugging state
- Trivial or well-documented behavior
- Project-specific conventions that belong in CLAUDE.md

## How Vestige Differs from a Simple Store

- **Deduplication is automatic** — `smart_ingest` compares against existing memories and decides whether to create, update, or merge. No need to search before storing.
- **Memories decay** — unused memories fade naturally via FSRS-6. Access strengthens them. This keeps context lean.
- **Search strengthens memory** — every search reinforces the retrieved memories (Testing Effect). Search liberally.

## Tools Reference

| Tool | Use for |
|------|---------|
| `mcp__vestige__smart_ingest` | Store new memories (auto-dedup) |
| `mcp__vestige__search` | Find memories by semantic similarity |
| `mcp__vestige__memory` | Get, edit, delete, promote, demote a specific memory |
| `mcp__vestige__codebase` | Store/retrieve code patterns and architectural decisions |
| `mcp__vestige__intention` | Set/check reminders with time or context triggers |
| `mcp__vestige__session_context` | One-call session initialization |
| `mcp__vestige__explore_connections` | Find reasoning chains and associations between memories |
| `mcp__vestige__dream` | Trigger consolidation to discover hidden connections |
