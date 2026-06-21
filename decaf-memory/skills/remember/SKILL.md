---
name: remember
description: Store a memory in erinra for future reference
argument-hint: "[what to remember]"
---

# Remember

Store a memory in erinra.

## Prerequisites

Check that `mcp__erinra__store` is available in your tools. If not, tell the user:

> Erinra MCP server is not connected. Run `claude mcp add erinra -- erinra serve -s user` and restart Claude Code.

## Usage

```
/decaf-memory:remember [description of what to remember]
```

## Process

1. **Clarify if needed** — If the user's input is vague, ask what they want to remember and why it matters.

2. **Classify the memory** — Choose a type:
   - `preference` — User preference or working style
   - `pattern` — A reusable approach or convention
   - `decision` — An architectural or design choice
   - `bug-fix` — A bug and its solution
   - `fact` — A piece of factual knowledge
   - `concept` — A concept or mental model
   - `note` — A general note
   - `event` — Something that happened
   - Or any other descriptive type string

3. **Store it** using `mcp__erinra__store`:
   ```
   mcp__erinra__store({
     content: "[the memory content]",
     type: "[type]",
     projects: ["[project-name if applicable]"],
     tags: ["[relevant tags]"],
     links: [{ target_id: "[id]", relation: "[relation]" }]  // optional: link to related memories
   })
   ```

   The `links` parameter is optional. Use it to connect the new memory to existing ones with relations like `related_to`, `caused_by`, `context_for`, or `supersedes`.

4. **Check the response** — `store` returns the top-3 most similar existing memories. If a very similar one exists:
   - If the new content supersedes it: use `mcp__erinra__update` on the existing memory instead
   - If they should be combined: use `mcp__erinra__merge` to combine them
   - If the existing one is already sufficient: tell the user it was already stored

5. **Confirm** — Tell the user what was stored and how it was classified.

## Examples

**User:** `/remember HttpClient timeout doesn't work as expected with Polly retry`

**Response:**
```
I'll store this. Can you clarify:
1. What was the unexpected behavior?
2. What was the solution?

[After user responds]

Stored as bug-fix:
- HttpClient.Timeout is per-attempt, not total
- Polly retry can exceed expected total timeout
- Solution: Wrap retry policy with Polly timeout policy
Tags: polly, httpclient, dotnet
```

**User:** `/remember I prefer tabs over spaces`

**Response:**
```
Stored as preference: "User prefers tabs over spaces for indentation"
```

## What NOT to Store

Guide users away from storing:
- **Project-specific patterns** -> suggest adding to project CLAUDE.md instead
- **Well-documented behavior** -> no need to store what's in the docs
- **Secrets or credentials** -> never store sensitive data
- **Transient issues** -> only store if likely to recur
