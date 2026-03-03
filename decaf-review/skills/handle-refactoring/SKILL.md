---
name: handle-refactoring
description: Walk through refactoring opportunities interactively, applying changes one at a time
argument-hint: "[file]"
---

# Handle Refactoring Opportunities

Iterate through refactoring plan opportunities one by one, presenting each refactoring unit and waiting for user input before proceeding.

## Critical Behavior Requirements

**YOU MUST FOLLOW THESE RULES:**

1. **MANDATORY STOP**: You MUST use `AskUserQuestion` to present each opportunity and wait for the user's choice BEFORE taking ANY action. Do NOT implement refactorings autonomously.

2. **ONE AT A TIME**: Process refactoring units ONE AT A TIME. Never batch multiple units together. Never present more than one unit per response.

3. **NO AUTONOMOUS REFACTORING**: Never implement a refactoring without explicit user approval via AskUserQuestion response.

4. **STATE TRACKING**: After presenting the summary, write progress state to `.refactoring-plans/.handle-refactoring-state.json`. Update this file after each unit is processed. This enables recovery after context compaction.

## Argument Parsing

Parse `$ARGUMENTS` to determine the refactoring plan file:

**File** (optional):
- If a file path is provided: Use that specific file
- Otherwise: Use the most recent `.refactoring-plans/REFACTOR_PLAN_*.md` file

## Execution Steps

### Step 1: Locate the Refactoring Plan File

**If `$ARGUMENTS` specifies a file:**
- Verify the file exists
- If not found, inform the user and exit

**Otherwise, find the latest plan:**
```bash
ls .refactoring-plans/REFACTOR_PLAN_*.md 2>/dev/null | sort -r | head -1
```

If no refactoring plan file exists, inform the user:
> No refactoring plan found. Run `/decaf-review:refactor` first to generate one.

### Step 2: Parse Refactoring Units

Read the refactoring plan file and extract all refactoring units. Units are identified by headers matching the pattern:
```
### #N ★★★|★★ Title
```

Build a list of units with:
- Number (#1, #2, etc.)
- Star rating (★★★ or ★★)
- Title
- Impact and effort
- Files involved
- Category
- Problem description
- Before/after code sketches
- Refactoring steps

### Step 3: Check for Existing State

Check if `.refactoring-plans/.handle-refactoring-state.json` exists:
- If yes and it references the same plan file, offer to resume from where we left off
- If no or different file, start fresh

### Step 4: Present Summary and Initialize State

Show the user the overall summary:

```
## Refactoring Plan: [filename]

| Rating | Count |
|--------|-------|
| ★★★ | X |
| ★★ | X |

**Total units:** N

I'll walk you through each refactoring unit ONE AT A TIME. For each one, choose an action:
- **Apply** — implement the refactoring
- **Apply (Incremental)** — implement step by step with verification between steps
- **Skip**, Dismiss, Defer
```

Write initial state to `.refactoring-plans/.handle-refactoring-state.json`:
```json
{
  "planFile": ".refactoring-plans/REFACTOR_PLAN_xxx.md",
  "totalUnits": N,
  "currentIndex": 0,
  "processed": [],
  "actions": { "applied": 0, "appliedIncremental": 0, "skipped": 0, "dismissed": 0, "deferred": 0 },
  "deferSystem": null
}
```

### Step 5: Process Each Unit (MANDATORY STOP POINT)

For each unit, starting with ★★★ then ★★:

**5a. Present the unit:**
```
## Unit #N of M: [Star Rating] [Title]

**Impact:** High | **Effort:** Medium
**Files:** `src/OrderProcessor.cs`, `src/PaymentService.cs`
**Category:** validation-scattering
**Found by:** coherence-analyst, structural-analyst
**Confidence:** 88/100

### Problem
[Problem description from the plan]

### Before
```language
[Before code sketch]
```

### After
```language
[After code sketch]
```

### Steps
1. [Step 1]
2. [Step 2]
3. [Step 3]
```

**5b. MANDATORY: Present options and wait for user choice.**

Build the full list of options. AskUserQuestion supports max 4 options, so always use a two-step flow:

**Step 1 — top-level choice:**
```
AskUserQuestion with:
- question: "How would you like to handle this refactoring opportunity?"
- header: "Action"
- options:
  - label: "Apply...", description: "Implement this refactoring (more options)"
  - label: "Skip...", description: "Don't apply this now (more options)"
```

⚠️ **STOP HERE AND WAIT FOR USER RESPONSE.**

**Step 2 — follow-up based on choice:**

If user chose "Apply...":
```
AskUserQuestion with:
- question: "Which approach?"
- header: "Apply"
- options:
  - label: "Apply", description: "Implement the full refactoring"
  - label: "Apply (Incremental)", description: "Step by step with verification between each step"
```

If user chose "Skip...":
```
AskUserQuestion with:
- question: "How should this opportunity be tracked?"
- header: "Skip type"
- options:
  - label: "Skip", description: "Move to next unit, no tracking"
  - label: "Dismiss", description: "Mark as not worth doing"
  - label: "Defer", description: "Create a work item for later"
```

⚠️ **STOP HERE AND WAIT FOR USER RESPONSE.**

**5c. Handle the final response:**

- **Apply**: Implement the full refactoring:
  1. Read all affected files
  2. Implement all steps from the plan
  3. Verify the code compiles/builds
  4. Show the user what changed
- **Apply (Incremental)**: Implement step by step:
  1. For each step in the plan:
     a. Read relevant files
     b. Implement that step only
     c. Verify compilation
     d. Show what changed
     e. Wait for user confirmation before next step (use AskUserQuestion: "Continue to next step?" with "Continue" / "Stop here")
  2. After all steps or user stops, show cumulative changes
- **Skip**: Record as skipped, proceed to next
- **Dismiss**: Record as dismissed. The user may provide a reason via the free-form "Other" option — if so, store it. Otherwise record reason as `"dismissed"`.
- **Defer**: Create a work item in the project's tracking system:
  1. **Detect tracking system**: Check project CLAUDE.md for references to tracking systems (Beans, Azure DevOps, GitHub Issues, TODO comments, etc.)
  2. **First defer**: If no system detected and `deferSystem` is null in state file, ask the user which system to use via AskUserQuestion. Store the choice in state file under `"deferSystem"`.
  3. **Subsequent defers**: Reuse `deferSystem` from state file.
  4. **Create work item**: Create the item in the appropriate system. Store the work item reference.
- **Other** (free-form): Implement whatever the user describes. If user types "Stop", jump to Step 6.

**5d. Update state file** after each action:
```json
{
  "currentIndex": N,
  "processed": [..., { "unit": N, "action": "applied|appliedIncremental|skipped|dismissed|deferred|other" }],
  "actions": { "applied": X, "appliedIncremental": Y, "skipped": W, "dismissed": D, "deferred": F }
}
```
For dismissed units, include reason: `{ "unit": N, "action": "dismissed", "reason": "..." }`
For deferred units, include work item reference: `{ "unit": N, "action": "deferred", "workItem": "..." }`

**5e. Show progress:**
```
✅ Unit #N addressed. (X of M remaining)
```

**5f. Return to 5a for next unit.** Do NOT batch - present one unit, wait, process, repeat.

### Step 6: Session Summary

When all units are processed or the user stops:

```
## Refactoring Session Complete

| Action | Count |
|--------|-------|
| Applied | X |
| Applied (Incremental) | X |
| Skipped | X |
| Dismissed | X |
| Deferred | X |

### Changes Made
- [List of files modified and what was refactored]

### Remaining Opportunities
- [List of skipped or unprocessed units, if any]
- [Deferred items with their work item references]

### Dismissed Opportunities
- [List of dismissed items with reasons, if any]
```

Delete `.refactoring-plans/.handle-refactoring-state.json` when complete.

### Step 7: Re-review Suggestion

If any refactorings were applied during the session:

1. List the files that were modified
2. Ask via AskUserQuestion:

```
AskUserQuestion with:
- question: "Run a quick code review on the modified files to verify refactorings?"
- header: "Re-review"
- options:
  - label: "Yes", description: "Run /decaf-review:code-review quick on modified files"
  - label: "No", description: "Done for now"
```

If the user chooses "Yes", invoke `/decaf-review:code-review quick <modified-files>`.

### Step 8: Clean Up Plan File

Ask whether to delete the refactoring plan file:

```
AskUserQuestion with:
- question: "Delete the refactoring plan file ([filename])?"
- header: "Clean up"
- options:
  - label: "Yes", description: "Delete the plan file"
  - label: "No", description: "Keep the plan file"
```

If the user chooses "Yes", delete the refactoring plan file.

## Notes

- Always order units by star rating (★★★ first, then ★★)
- For each refactoring, verify the change compiles before moving on
- If a refactoring fails, offer alternatives or let the user skip
- Keep track of all changes for the final summary
- If context is compacted mid-session, read `.refactoring-plans/.handle-refactoring-state.json` to resume
- Always use literal Unicode emoji characters, never `:shortcode:` syntax
