// Vestige session start hook — outputs memory protocol as additionalContext.
// Runs on every session start, resume, clear, and context compaction.
// Uses Node.js for cross-platform compatibility (Windows + Linux + macOS).

console.log(`# Vestige Memory Protocol

You have access to Vestige, a cognitive memory system with semantic search, spaced repetition (FSRS-6), and automatic deduplication. Use it proactively.

## Session Start — DO THIS NOW

Load context with a single call:

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

If mcp__vestige__session_context is not available in your tools, warn the user:
"Vestige MCP server is not connected. Memory features are unavailable. To set up Vestige, run: claude mcp add vestige vestige-mcp -s user and restart Claude Code."

## Automatic Saves — No Permission Needed

After solving a bug: smart_ingest with content "BUG FIX: [error] | Root cause: [why] | Solution: [how]", tags: ["bug-fix", project-name]
After learning user preferences: smart_ingest immediately (coding style, libraries, communication, tools, workflows)
After architectural decisions: codebase(action="remember_decision") with rationale and alternatives
After discovering code patterns: codebase(action="remember_pattern") with name and description

## Trigger Words — Auto-Save When User Says

"Remember this" / "Don't forget" -> smart_ingest immediately
"I always..." / "I never..." / "I prefer..." -> Save as preference
"This is important" -> smart_ingest + memory(action="promote")
"Remind me..." / "Next time..." -> intention(action="set") with appropriate trigger

## During Work

- Notice a pattern? codebase(action="remember_pattern") with name and description
- Made a decision? codebase(action="remember_decision") with rationale and alternatives
- Something important? importance_score to evaluate if worth saving
- Need to follow up? intention(action="set") with context trigger

## Automatic Context Detection

When working, proactively search Vestige if the task involves:
- A specific library or framework -> search for known patterns
- An error message -> search for previous solutions
- A codebase -> codebase(action="get_context") for patterns and decisions
- User mentions a person -> search their name for relationship context

## Proactive Behaviors

DO automatically:
- Save solutions after fixing problems
- Note user corrections as preferences
- Update project context after major changes
- Create intentions for mentioned deadlines
- Search before answering technical questions

DON'T ask permission to:
- Save bug fixes
- Update preferences
- Create reminders from explicit requests
- Search for context

## Memory Feedback

If the user explicitly confirms a memory was helpful, use memory(action="promote"). If they correct a hallucination or say a memory was wrong, use memory(action="demote"). Do not ask for permission — just act on their feedback.

## What NOT to Store

Secrets, API keys, credentials, tokens. Temporary debugging state. Trivial or well-documented behavior. Project-specific conventions that belong in CLAUDE.md.

## Key Behaviors

- Deduplication is automatic — smart_ingest handles it. No need to search before storing.
- Memories decay — unused memories fade via FSRS-6. Access strengthens them.
- Search strengthens memory — every search reinforces retrieved memories. Search liberally.
- Memory is retrieval. When in doubt, search Vestige first. If nothing found, solve the problem, then save the solution.`);
