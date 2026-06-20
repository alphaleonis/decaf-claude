---
description: Check project and iteration progress (global), suggest next action
argument-hint: (no arguments needed)
---

## Project Context

Read `.devmeta/devmeta.md` from the project root if it exists. It provides
project-specific test commands, environment checks, and additional rules.

If no `.devmeta/devmeta.md` exists:
- Testing: look for `package.json` test scripts
- Environment: skip checks
- Additional rules: none

---

## Context

- Today's date: !`date +%Y-%m-%d`
- Open features: !`tk list --type epic --status open 2>/dev/null | head -20 || echo "No open features"`
- Closed features: !`tk list --type epic --status closed 2>/dev/null | head -20 || echo "None"`

## Your Task

Provide a clear status report and suggest the next action.

### Step 1: Read Project State

1. Read `.devmeta/current-increment.md` → current increment's `_overview.md` — iteration map
2. Find the current iteration (most recent with status != Complete):
   - Read its `status.md` in the increment's `iterations/` directory
3. Check tk status:
   ```bash
   tk list --type epic --json 2>/dev/null
   ```

### Step 2: Compute Progress

For each active iteration:
- Count features: total, complete, in-progress, blocked
- Count tasks: total, complete, in-progress, blocked, awaiting

### Step 3: Report

```markdown
## Project Status

### Current Iteration: <N> — <title>
**Status:** <Not started / In progress / Blocked / Complete>

| Feature | Status | Tasks | Progress |
|---------|--------|-------|----------|
| <name> | <status> | X/Y complete | <bar or %> |

### Overall Progress
- Iterations complete: X / N
- Current iteration: <N> — <progress summary>

### Blocked Items (if any)
| Item | Blocked By | Notes |
|------|-----------|-------|
| <feature/task> | <reason> | <from tk notes> |
```

### Step 4: Suggest Next Action

Based on current state, recommend ONE of:

| State | Suggestion |
|-------|-----------|
| No iteration started | Run `/devmeta:plan-iteration 1` to begin |
| Iteration planned, not started | Run `/devmeta:run --all` to execute |
| Iteration in progress, features running | Wait for completion or check blocked items |
| Iteration complete, not reflected | Run `/devmeta:reflect <N>` to capture learnings |
| I&A cycle complete, next not planned | Run `/devmeta:plan-iteration <N+1>` |
| Tasks blocked on human | List what's needed from the user |

```markdown
### Suggested Next Action
> <specific command or action>
```
