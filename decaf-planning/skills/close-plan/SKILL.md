---
name: close-plan
description: Close a completed phase or plan by reconciling planned vs. actual, recording deviations and decisions, updating the parent work item, and creating follow-ups for deferred work. Use after finishing a phase or plan to prevent silent drift.
argument-hint: "<phase/plan reference or work item ID>"
---

# Close Plan

Reconcile what was planned against what was actually built, then close the work item. Prevents orphaned plans and silent drift by forcing explicit closure with a durable summary.

## Why This Exists

Without explicit closure, the next session sees a phase with some acceptance criteria checked and no explanation of why — was it deferred deliberately or just forgotten? Decisions made mid-implementation live only in code and commits. Descoped work vanishes unless someone creates follow-up items.

This skill is the bookkeeping step the AI would otherwise skip.

## Process

### 1. Identify what to close

The user provides a reference to a phase or plan:
- A work item ID (beans, GitHub issue, Azure DevOps work item)
- A phase number or title from a plan in conversation context
- A path to a plan file

If unclear, ask the user which phase or plan they want to close.

Read the work item or plan section to get:
- The original description ("what to build")
- Acceptance criteria
- Scope boundaries (touches / off limits), if present
- Parent work item or plan reference

### 2. Gather what actually happened

Determine what was built by examining:

- **Git history**: Run `git log` for the relevant time period or branch to see what commits were made. Look at commit messages for context.
- **Acceptance criteria status**: For each criterion, determine if it was met, partially met, or not addressed.
- **Scope boundary adherence**: If the phase had "touches" and "off limits" sections, check whether work stayed within bounds or expanded beyond them.

If the work was done in the current session, use conversation context as well. If it was done in prior sessions, rely on git history and the current state of the code.

### 3. Draft the closure summary

Produce a structured summary:

```markdown
## Closure Summary

**Status**: Completed | Partially completed
**Date**: <YYYY-MM-DD>

### Acceptance Criteria

- [x] Criterion 1
- [x] Criterion 2
- [ ] Criterion 3 — deferred: <reason>

### Deviations

Changes that differed from the original plan:
- <what changed and why>

### Decisions Made During Implementation

Architectural or design decisions not in the original plan:
- <decision and rationale>

### Deferred Work

Work that was planned but not completed:
- <what was deferred and why>
```

**Keep it concise.** A few bullet points per section is ideal. Don't pad sections that have nothing to report — omit empty sections entirely.

### 4. Show the summary to the user

Present the draft summary before making any changes. The user may want to adjust, add context, or correct the assessment.

### 5. Update the work item

@../../../../conventions/work-items.md

**Update the phase/plan work item:**
- Append the closure summary to the work item body
- Mark the work item as completed/closed (if the system supports status updates)

**Update the parent work item:**
- If the closed item has a parent (milestone, plan), update the parent to reflect progress:
  - Check off the completed phase in any checklist
  - If decisions were made that affect other phases, note them in the parent body

**System-specific details:**

| System | Close action |
|--------|-------------|
| Beans | Append summary to body via `beans edit`, update status to `done` via `beans update --status done` |
| GitHub Issues | Add summary as a comment, close the issue |
| Azure DevOps | Append summary to description, update state to Closed/Done |
| Markdown | Append summary section under the phase in the plan file |

### 6. Create follow-up items

For each piece of deferred work identified in step 3, create a new work item:

- **Title**: Descriptive title for the deferred work
- **Body**: What needs to be done, why it was deferred, and any context from the original phase
- **Parent**: Same parent as the closed phase (so it stays in the same plan/milestone)

Skip this step if nothing was deferred.

### 7. Confirm closure

After all updates are made, inform the user:

```
Closed: <phase/plan reference>
- N/M acceptance criteria met
- N deviations recorded
- N follow-up items created: <references>
```

## Example Usage

```
/decaf-planning:close-plan 3                    # Close phase 3 from plan in context
/decaf-planning:close-plan BEAN-42              # Close a beans work item
/decaf-planning:close-plan ./plans/auth.md#2    # Close phase 2 in a plan file
```
