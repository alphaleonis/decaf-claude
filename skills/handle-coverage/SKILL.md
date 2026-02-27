---
name: handle-coverage
description: Walk through coverage review findings interactively, writing tests for gaps
argument-hint: "[high|medium|all] [file]"
---

# Handle Coverage Review Findings

Iterate through coverage gap findings one by one, presenting each grouped issue and waiting for user input before proceeding.

## Critical Behavior Requirements

**YOU MUST FOLLOW THESE RULES:**

1. **MANDATORY STOP**: You MUST use `AskUserQuestion` to present each group and wait for the user's choice BEFORE taking ANY action. Do NOT write tests autonomously.

2. **ONE AT A TIME**: Process groups ONE AT A TIME. Never batch multiple groups together. Never present more than one group per response.

3. **NO AUTONOMOUS TESTS**: Never write tests without explicit user approval via AskUserQuestion response.

4. **STATE TRACKING**: After presenting the summary, write progress state to `.code-reviews/.handle-coverage-state.json`. Update this file after each group is processed. This enables recovery after context compaction.

## Argument Parsing

Parse `$ARGUMENTS` to determine severity filter and coverage review file:

**Severity filter** (first positional argument, optional):
- `high` — only Critical + High findings
- `medium` — Critical + High + Medium findings
- `all` (default) — all findings

**File** (remaining argument, optional):
- If a file path is provided: Use that specific file
- Otherwise: Use the most recent `.code-reviews/COVERAGE_REVIEW_*.md` file

## Execution Steps

### Step 1: Locate the Coverage Review File

**If `$ARGUMENTS` specifies a file:**
- Verify the file exists
- If not found, inform the user and exit

**Otherwise, find the latest review:**
```bash
ls -t .code-reviews/COVERAGE_REVIEW_*.md 2>/dev/null | head -1
```

If no coverage review file exists, inform the user:
> No coverage review found. Run `/decaf:coverage-review` first to generate one.

### Step 2: Parse Findings

Read the coverage review file and extract all findings. Findings are identified by headers matching the pattern:
```
### #N Severity: Title
```

Where severity is one of: Critical, High, Medium, Low.

Build a list of findings with:
- Number (#1, #2, etc.)
- Severity (Critical, High, Medium, Low)
- Title
- File and line range
- Coverage percentage
- Category (e.g., error-handling-gap, logic-gap)
- Why it matters (severity assessment)
- Suggested tests (list of test case suggestions)

**Filter by severity:** Apply the severity filter from arguments. Remove findings below the threshold:
- `high`: Keep only Critical and High
- `medium`: Keep Critical, High, and Medium
- `all`: Keep everything

### Step 2.5: Group Findings

Coverage findings are often granular (per-line or per-branch). Walking through each individually would be tedious. After parsing, group findings into logical units:

1. **Group by source file + class/type** (primary grouping)
2. Within a class, **sub-group by method/function** if findings span multiple methods
3. Each group becomes one "item" to present to the user
4. The group's severity = highest severity among its findings
5. The group's suggested tests = merged list from all findings in the group

This means the user answers once per class (or per method cluster in a large class), not once per uncovered line.

### Step 3: Check for Existing State

Check if `.code-reviews/.handle-coverage-state.json` exists:
- If yes and it references the same review file, offer to resume from where we left off
- If no or different file, start fresh

### Step 4: Present Summary and Initialize State

Show the user the overall summary:

```
## Coverage Review: [filename]

| Severity | Count |
|----------|-------|
| 🔴 Critical | X |
| 🟠 High | X |
| 🟡 Medium | X |
| 🟢 Low | X |

**Total findings:** N (grouped into M logical units)

I'll walk you through each group ONE AT A TIME. For each one, choose an action:
- **Write Tests** — implement suggested test cases
- **Skip**, Dismiss (false positive), Defer (create work item)
```

Write initial state to `.code-reviews/.handle-coverage-state.json`:
```json
{
  "reviewFile": ".code-reviews/COVERAGE_REVIEW_xxx.md",
  "totalFindings": N,
  "totalGroups": M,
  "currentGroupIndex": 0,
  "processed": [],
  "actions": { "testsWritten": 0, "skipped": 0, "dismissed": 0, "deferred": 0 },
  "deferSystem": null
}
```

### Step 5: Process Each Group (MANDATORY STOP POINT)

For each group, starting with the highest severity:

**5a. Present the group:**
```
## Group #N of M: [Severity Icon] [Title — e.g. "PaymentProcessor error paths"]

**File:** `src/PaymentProcessor.cs`
**Coverage:** 45% line, 30% branch
**Gaps:** 3 findings (lines 45-62, 78-85, 102-110)
**Categories:** error-handling-gap, logic-gap

### Why it matters
[Combined severity assessments from all findings in group]

### Suggested Tests
1. Should_ReturnError_When_PaymentGateway_TimesOut (lines 45-62)
2. Should_RollbackTransaction_On_PartialFailure (lines 78-85)
3. Should_RetryOnTransientError (lines 102-110)
```

**5b. MANDATORY: Present options and wait for user choice.**

Always present exactly 4 options in a single flat AskUserQuestion (1 fix + 3 skip):

```
AskUserQuestion with:
- question: "How would you like to handle this coverage gap?"
- header: "Action"
- options:
  - label: "Write Tests", description: "Implement all suggested test cases for this group"
  - label: "Skip", description: "Move to next group, no tracking"
  - label: "Dismiss", description: "Mark as false positive"
  - label: "Defer", description: "Create a work item for later"
```

**5c. Handle the response:**

- **Write Tests**:
  1. Read the source file for context
  2. Find the existing test file for the source file, or create one following project conventions
  3. Implement all suggested tests for the group
  4. Run tests to verify they compile and pass
  5. Show the user the tests created
  6. Mark all findings in the group as processed
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
  "currentGroupIndex": N,
  "processed": [..., { "group": N, "findingIds": [1, 3, 5], "action": "testsWritten|skipped|dismissed|deferred|other" }],
  "actions": { "testsWritten": X, "skipped": W, "dismissed": D, "deferred": F }
}
```
For dismissed groups, include reason: `{ "group": N, "findingIds": [...], "action": "dismissed", "reason": "..." }`
For deferred groups, include work item reference: `{ "group": N, "findingIds": [...], "action": "deferred", "workItem": "..." }`

**5e. Show progress:**
```
✅ Group #N addressed. (X of M remaining)
```

**5f. Return to 5a for next group.** Do NOT batch - present one group, wait, process, repeat.

### Step 6: Session Summary

When all groups are processed or the user stops:

```
## Coverage Session Complete

| Action | Count |
|--------|-------|
| Tests Written | X |
| Skipped | X |
| Dismissed | X |
| Deferred | X |

### Tests Created
- [List of test files created/modified and what was covered]

### Remaining Gaps
- [List of skipped or unprocessed groups, if any]
- [Deferred items with their work item references]

### Dismissed Findings
- [List of false positives with reasons, if any]
```

Delete `.code-reviews/.handle-coverage-state.json` when complete.

### Step 7: Re-review Suggestion

If any tests were written during the session:

1. List the files that were modified
2. Ask via AskUserQuestion:

```
AskUserQuestion with:
- question: "Run a coverage review on the modified files to verify improved coverage?"
- header: "Re-review"
- options:
  - label: "Yes", description: "Run /decaf:coverage-review diff on modified files"
  - label: "No", description: "Done for now"
```

If the user chooses "Yes", invoke `/decaf:coverage-review diff`.

## Notes

- Always order groups by severity (Critical -> High -> Medium -> Low)
- For each test written, verify the change compiles and tests pass before moving on
- If test writing fails, offer alternatives or let the user skip
- Keep track of all changes for the final summary
- If context is compacted mid-session, read `.code-reviews/.handle-coverage-state.json` to resume
- Always use literal Unicode emoji characters (🔴🟠🟡🟢), never `:shortcode:` syntax like `:yellow_circle:`
