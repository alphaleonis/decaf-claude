---
name: handle-cr
description: Walk through code review findings interactively, addressing each issue
argument-hint: "[high|medium|all] [file]"
---

# Handle Code Review Findings

Iterate through code review findings one by one, presenting each issue and waiting for user input before proceeding.

## Critical Behavior Requirements

**YOU MUST FOLLOW THESE RULES:**

1. **MANDATORY STOP**: You MUST use `AskUserQuestion` to present each finding and wait for the user's choice BEFORE taking ANY action. Do NOT implement fixes autonomously.

2. **ONE AT A TIME**: Process findings ONE AT A TIME. Never batch multiple findings together. Never present more than one finding per response.

3. **NO AUTONOMOUS FIXES**: Never implement a fix without explicit user approval via AskUserQuestion response.

4. **STATE TRACKING**: After presenting the summary, write progress state to `.code-reviews/.handle-cr-state.json`. Update this file after each finding is processed. This enables recovery after context compaction.

## Argument Parsing

Parse `$ARGUMENTS` to determine severity filter and code review file:

**Severity filter** (first positional argument, optional):
- `high` — only Critical + High findings
- `medium` — Critical + High + Medium findings
- `all` (default) — all findings

**File** (remaining argument, optional):
- If a file path is provided: Use that specific file
- Otherwise: Use the most recent `.code-reviews/CODE_REVIEW_*.md` file

## Execution Steps

### Step 1: Locate the Code Review File

**If `$ARGUMENTS` specifies a file:**
- Verify the file exists
- If not found, inform the user and exit

**Otherwise, find the latest review:**
```bash
ls .code-reviews/CODE_REVIEW_*.md 2>/dev/null | sort -r | head -1
```

If no code review file exists, inform the user:
> No code review found. Run `/decaf-review:code-review` first to generate one.

### Step 2: Parse Findings

Read the code review file and extract all findings. Findings are identified by headers matching the pattern:
```
### #N 🔴|🟠|🟡|🟢 Severity: Title
```

Build a list of findings with:
- Number (#1, #2, etc.)
- Severity (Critical, High, Medium, Low)
- Title
- File and line
- Issue description
- Suggested fix (note if multiple options are presented)

**Filter by severity:** Apply the severity filter from arguments. Remove findings below the threshold:
- `high`: Keep only Critical and High
- `medium`: Keep Critical, High, and Medium
- `all`: Keep everything

**Identify similar issues:** Group findings that share the same underlying pattern (e.g., "missing null check", "missing empty collection guard", "undocumented parameter"). Track these groups to enable batch fixing.

### Step 3: Check for Existing State

Check if `.code-reviews/.handle-cr-state.json` exists:
- If yes and it references the same review file, offer to resume from where we left off
- If no or different file, start fresh

### Step 4: Present Summary and Initialize State

Show the user the overall summary:

```
## Code Review: [filename]

| Severity | Count |
|----------|-------|
| 🔴 Critical | X |
| 🟠 High | X |
| 🟡 Medium | X |
| 🟢 Low | X |

**Total findings:** N

I'll walk you through each finding ONE AT A TIME. For each one, choose an action:
- **Apply Fix**, Fix (TDD), Fix All Similar
- **Skip**, Dismiss (false positive), Defer (create work item)
```

Write initial state to `.code-reviews/.handle-cr-state.json`:
```json
{
  "reviewFile": ".code-reviews/CODE_REVIEW_xxx.md",
  "totalFindings": N,
  "currentIndex": 0,
  "processed": [],
  "actions": { "fixed": 0, "fixedTdd": 0, "fixedBatch": 0, "skipped": 0, "dismissed": 0, "deferred": 0 },
  "similarGroups": { "pattern-name": [1, 3, 7], ... },
  "deferSystem": null
}
```

### Step 5: Process Each Finding (MANDATORY STOP POINT)

For each finding, starting with the highest severity:

**5a. Present the finding:**
```
## Finding #N of M: [Severity Icon] [Title]

**File:** `path/to/file.cs:line`
**Category:** category
**Found by:** agent1, agent2
**Confidence:** XX/100

### Issue
[Issue description]

### Suggested Fix
[Fix description and code snippet if applicable]
```

**5b. MANDATORY: Present options and wait for user choice.**

Build the full list of fix and skip options first, then decide how to present them.

**Available fix options (built dynamically):**

| Option | Condition | Description |
|--------|-----------|-------------|
| "Apply Fix" | Always present | Implement the suggested fix |
| "Apply Fix (TDD)" | Testable behavioral bug AND not a test file | Write failing test first, then fix |
| "Fix All Similar" | Other unprocessed findings share same pattern | Fix this and N other similar issues |
| "Fix All Similar (TDD)" | Both TDD and batch conditions met | TDD workflow for all similar issues |

TDD eligibility:
- NOT a test file (filename contains `test`, `spec`, or is in `tests`/`__tests__` directory)
- Testable code (NOT documentation, comments, naming, formatting, or config changes)
- Behavioral bug that can be verified with a test

If the suggested fix has **multiple distinct options** (e.g., "Option 1: ... or Option 2: ..."), replace the single "Apply Fix" option with `"Apply Fix (Option 1)"`, `"Apply Fix (Option 2)"`, etc.

**Available skip options (always 3):**

| Option | Description |
|--------|-------------|
| "Skip" | Move to next finding, no tracking |
| "Dismiss" | Mark as false positive |
| "Defer" | Create a work item for later |

**Presentation rule — flatten when possible:**

AskUserQuestion supports max 4 options. Count the total options (fix options + skip options). If the total is **<= 4**, present them all in a **single** AskUserQuestion:

```
AskUserQuestion with:
- question: "How would you like to handle this finding?"
- header: "Action"
- options: [all fix options + all skip options, max 4]
```

If the total is **> 4**, use a two-step flow:

**Step 1 — top-level choice:**
```
AskUserQuestion with:
- question: "How would you like to handle this finding?"
- header: "Action"
- options:
  - label: "Fix...", description: "Address this finding (more options)"
  - label: "Skip...", description: "Don't fix this now (more options)"
```

⚠️ **STOP HERE AND WAIT FOR USER RESPONSE.**

**Step 2 — follow-up based on choice:**

If user chose "Fix...":
```
AskUserQuestion with:
- question: "Which fix approach?"
- header: "Fix type"
- options: [dynamically built fix options list]
```

If user chose "Skip...":
```
AskUserQuestion with:
- question: "How should this finding be tracked?"
- header: "Skip type"
- options:
  - label: "Skip", description: "Move to next finding, no tracking"
  - label: "Dismiss", description: "Mark as false positive"
  - label: "Defer", description: "Create a work item for later"
```

⚠️ **STOP HERE AND WAIT FOR USER RESPONSE.**

**5c. Handle the final response:**

- **Apply Fix** (or **Apply Fix (Option N)**): Implement the suggested fix (or specified option), verify it compiles, show the result
- **Apply Fix (TDD)** / **Fix All Similar (TDD)**: Follow the TDD workflow:
  1. **Red**: Write test(s) that expose the bug/issue. Run tests and verify they fail for the expected reason.
  2. **Green**: Implement the fix. Run tests and verify they now pass.
  3. **Refactor** (optional): Clean up if needed while keeping tests green.
  4. Show the user the test(s) created and the fix applied.
- **Fix All Similar**: Apply the same fix pattern to all similar issues:
  1. List all affected files/locations
  2. Apply fixes to each location
  3. Verify compilation
  4. Mark all related findings as processed
- **Skip**: Record as skipped, proceed to next
- **Dismiss**: Record as dismissed. The user may provide a reason via the free-form "Other" option — if so, store it. Otherwise record reason as `"dismissed"`.
- **Defer**: Create a work item in the project's tracking system:
  1. **Detect tracking system**: Check project CLAUDE.md for references to tracking systems (Beans, Azure DevOps, GitHub Issues, TODO comments, etc.)
  2. **First defer**: If no system detected and `deferSystem` is null in state file, ask the user which system to use via AskUserQuestion. Store the choice in state file under `"deferSystem"`.
  3. **Subsequent defers**: Reuse `deferSystem` from state file.
  4. **Create work item**: Create the item in the appropriate system (e.g., Beans task, GitHub issue, TODO comment in code). Store the work item reference.
- **Other** (free-form): Implement whatever the user describes. If user types "Stop", jump to Step 6.

**5d. Update state file** after each action:
```json
{
  "currentIndex": N,
  "processed": [..., { "finding": N, "action": "fixed|fixedTdd|fixedBatch|skipped|dismissed|deferred|other" }],
  "actions": { "fixed": X, "fixedTdd": Y, "fixedBatch": Z, "skipped": W, "dismissed": D, "deferred": F }
}
```
For dismissed findings, include reason: `{ "finding": N, "action": "dismissed", "reason": "..." }`
For deferred findings, include work item reference: `{ "finding": N, "action": "deferred", "workItem": "..." }`
For batch fixes, add entries for all affected findings to the `processed` array.

**5e. Show progress:**
```
✅ Finding #N addressed. (X of M remaining)
```

**5f. Return to 5a for next finding.** Do NOT batch - present one finding, wait, process, repeat.

### Step 6: Session Summary

When all findings are processed or the user stops:

```
## Review Session Complete

| Action | Count |
|--------|-------|
| Fixed | X |
| Fixed (TDD) | X |
| Fixed (Batch) | X |
| Skipped | X |
| Dismissed | X |
| Deferred | X |

### Changes Made
- [List of files modified and what was done]

### Remaining Issues
- [List of skipped or unprocessed findings, if any]
- [Deferred items with their work item references]

### Dismissed Findings
- [List of false positives with reasons, if any]

### Agent Summary
[Copy the Agent Summary table from the code review file verbatim]
```

Delete `.code-reviews/.handle-cr-state.json` when complete.

### Step 7: Re-review Suggestion

If any fixes were applied during the session:

1. List the files that were modified
2. Ask via AskUserQuestion:

```
AskUserQuestion with:
- question: "Run a quick code review on the modified files to verify fixes?"
- header: "Re-review"
- options:
  - label: "Yes", description: "Run /decaf-review:code-review quick on modified files"
  - label: "No", description: "Done for now"
```

If the user chooses "Yes", invoke `/decaf-review:code-review quick <modified-files>`.

### Step 8: Clean Up Review File

Ask whether to delete the code review file:

```
AskUserQuestion with:
- question: "Delete the code review file ([filename])?"
- header: "Clean up"
- options:
  - label: "Yes", description: "Delete the review file"
  - label: "No", description: "Keep the review file"
```

If the user chooses "Yes", delete the code review file.

## Notes

- Always order findings by severity (Critical → High → Medium → Low)
- For each fix, verify the change compiles before moving on
- If a fix fails, offer alternatives or let the user skip
- Keep track of all changes for the final summary
- If context is compacted mid-session, read `.code-reviews/.handle-cr-state.json` to resume
- Always use literal Unicode emoji characters (🔴🟠🟡🟢), never `:shortcode:` syntax like `:yellow_circle:`
