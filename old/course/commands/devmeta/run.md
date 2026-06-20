---
description: Execute features (global) — one subagent per feature, parallel across execution waves
argument-hint: [feature-id(s) or --all]
---

## Project Context

Read `.devmeta/devmeta.md` from the project root if it exists. It provides
project-specific test commands, environment checks, and additional rules.

If no `.devmeta/devmeta.md` exists:
- Testing: look for `package.json` test scripts
- Environment: skip checks
- Additional rules: none

> **tk mapping:** tk -t epic = DevMeta Feature, tk -t task = DevMeta Task

---

## Design

**The feature is the unit of context.** One subagent per feature. Sequential tasks within. Parallel across independent features. `context-log.md` for inter-feature communication. You (the orchestrator) are a thin scheduler.

## Context

- Today's date: !`date +%Y-%m-%d`
- Target: $ARGUMENTS
- Open features: !`tk list --type epic --status open 2>/dev/null | head -20 || echo "No open features"`

## Your Task

You are a thin orchestrator. Compute feature dependency order, spawn one worker per feature, track progress. You do NOT implement anything yourself.

### Phase 1: Identify Scope

**If `$ARGUMENTS` contains feature ID(s):** Run those features only.
**If `$ARGUMENTS` is `--all` or empty:** Run all open features.

### Phase 2: Compute Feature Dependency Graph

```bash
tk list --type epic --status open --json
```

For each feature, check tasks for cross-feature `blocked_by`:
```bash
tk list --parent <epic-id> --json
```

Build feature-level dependency graph. Compute waves:
```
Wave 1 = features with no open feature-level blockers
Wave 2 = features whose blocker-features are all in Wave 1
...
```

### Phase 3: Locate Shared Context Log

Find the `context-log.md` path from the feature descriptions. Read it — you'll include its contents in worker prompts.

### Phase 4: Present Execution Plan

```markdown
## Execution Plan

| Wave | Features (parallel) | Depends On |
|------|-------------------|-----------|
| 1 | Feature A (foundation) | — |
| 2 | Feature B, Feature C | Wave 1 |
| 3 | Feature D (validation) | Wave 2 |

Proceeding with execution...
```

### Phase 5: Execute Waves

```
FOR each wave:
  1. Gather all features in this wave
  2. For each feature:
     a. Gather ordered tasks: tk list --parent <epic-id> --json
     b. Read base branch from `<increment-dir>/base-branch` (find increment dir via `.devmeta/current-increment.md`)
     c. Create feature branch: git checkout -b feature/YYYY-MM-DD-<feature-name> <base-branch>
     d. Push branch: git push -u origin feature/YYYY-MM-DD-<feature-name>
  3. Spawn one subagent per feature — ALL in a SINGLE message (parallel)
     Include feature branch name in worker prompt
  4. Wait for all subagents to complete
  5. Collect results, update status
  6. Report wave results
  7. Proceed to next wave
```

**CRITICAL: Launch all feature workers in a wave in a SINGLE message with multiple Task tool calls.**

### Phase 6: Worker Prompt Template

Spawn with `subagent_type: "tk-worker"` (fallback: `"general-purpose"`).

```
## Your Assignment

**Feature:** [<epic-id>] <epic-title>
**Branch:** feature/YYYY-MM-DD-<feature-name> (already created — checkout and work here)

### Feature Description

<full description from tk show>

### Tasks (complete in order)

1. [<task-1-id>] <title>
   Acceptance: <criteria>
2. [<task-2-id>] <title>
   Acceptance: <criteria>
...

### Task Details

<Full description for each task from tk show>

### Shared Context Log

<Contents of context-log.md>

### Feature Notes (from previous runs)

<Output of tk notes <epic-id>>

## Instructions

1. Read CLAUDE.md for project orientation
2. Read docs/current/principles-and-choices.md for architectural decisions
3. Read .devmeta/lessons-learned.md — don't repeat known mistakes
4. Read context-log.md for context from previous features
5. If .devmeta/devmeta.md exists at project root, read it for test commands and additional rules
6. Work through tasks IN ORDER — they build on each other
7. For each task:
   a. tk update <task-id> --status in_progress
   b. Read the spec section referenced
   c. Implement the changes
   d. Write tests alongside implementation
   e. Run acceptance criteria. Fix and re-run until green
   f. Commit: `git commit -m "[TASK-ID] <what was done>"`
   g. tk close <task-id> --reason "<summary>"
8. After ALL tasks done:
   a. Append learnings to context-log.md
   b. tk note <epic-id> "FEATURE COMPLETE: <summary>"
   c. Create PR: `gh pr create --title "<feature title>" --body "<summary>"`
9. If a task cannot be completed:
   a. tk update <task-id> --awaiting escalation
   b. tk note <task-id> "<what's blocking and what was tried>"
   c. Continue to next task if possible

## Rules

- Complete tasks in order
- Be autonomous — don't ask questions
- NEVER close a task with failing tests. If tests fail: debug, fix, re-run. Loop until green. There is no "close with known failures"
- Tests are YOUR responsibility. Write them, run them, fix them. Never defer testing to a later task or iteration
- Use surgical test commands (not full suite)
- After completing all tasks, run the iteration's "Verify on screen" commands from the increment overview. If output doesn't match, keep working — the iteration is not done
- Leave useful notes in context-log.md
- When you solve a problem, also write it to .devmeta/lessons-learned.md
- Use tk commands, never edit .tick/issues/ directly
- Work on the feature branch. Commit after each task with `[TASK-ID] <summary>`. Create PR targeting the base branch (from `<increment-dir>/base-branch`) when all tasks done
- NEVER reduce scope. If something is hard, work harder. If something is blocked, unblock it. Only the human can cut features

```

### Phase 7: Handling Results

**All tasks closed:** `tk close <epic-id> --reason "All tasks completed"`

**Some tasks open:**
- Check awaiting: `tk list --parent <epic-id> --awaiting --json`
- Check notes: `tk notes <task-id>`
- Reset stale in_progress: `tk update <task-id> --status open`

### Phase 8: Wave Reporting

```markdown
## Wave <N> Complete

| Feature | Title | Tasks Done | Status |
|------|-------|-----------|--------|
| <id> | <title> | X/Y | Complete / Partial / Blocked |

### Next Wave
| Feature | Title | Tasks |
|------|-------|-------|
| <id> | <title> | N tasks |
```

### Phase 9: Final Summary and Continue

```markdown
## Execution Complete

| Feature | Title | Status | Tasks |
|------|-------|--------|-------|
| <id> | <title> | Complete / Partial | X/Y |

### Totals
- Features: X complete, Y partial
- Tasks: X complete, Y blocked
- Waves: N

### Needs Attention (if any)
| Feature | Task | Issue |
|------|------|-------|
```

**DO NOT pause, summarize with "Next Steps", or hand control back to the user — except at increment boundaries.** Execution is a waypoint inside `/devmeta:go`'s autonomous loop.

After writing the summary:
1. Run `tk next` to get the next task (typically "Create PR for iteration N", "Merge PR", or the next feature).
2. Begin executing it immediately.

If there are blocked tasks that cannot be unblocked autonomously, note them in tk and move on to whatever CAN be done. Only stop for genuine external blockers (missing API keys, missing hardware, human-only decisions).

**Exception: increment completion is a stopping point.** If `tk next` returns nothing and all iterations of the current increment are closed, the increment is done — STOP. Do not create or pick up a "bootstrap next increment" task, do not ask the user which increment to start next. Write the completion summary and exit; the user re-invokes `/devmeta:go` when they're ready for the next increment.

## Error Handling

- **Worker fails to spawn:** Log error, reset tasks, continue with remaining features
- **All features blocked:** Report what needs attention, stop execution
- **Partial completion:** Completed tasks stay closed. Reset incomplete to open. Next run resumes.
