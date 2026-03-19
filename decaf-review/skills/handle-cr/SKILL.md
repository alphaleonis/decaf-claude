---
name: handle-cr
description: Walk through code review findings interactively, addressing each issue. Use "auto" for autonomous fixing with TDD.
argument-hint: "[auto] [high|medium|all] [file]"
---

# Handle Code Review Findings

Iterate through code review findings, presenting each issue and resolving it.

**Two modes:**
- **Interactive** (default): Present one finding at a time, wait for user input.
- **Auto** (`auto` argument): Ask clarifying questions upfront, then autonomously fix or skip each finding using best judgment. Prefers TDD when test infrastructure is available.

## Critical Behavior Requirements

**YOU MUST FOLLOW THESE RULES:**

### Interactive Mode (default)

1. **MANDATORY STOP**: You MUST use `AskUserQuestion` to present each finding and wait for the user's choice BEFORE taking ANY action. Do NOT implement fixes autonomously.

2. **ONE AT A TIME**: Process findings ONE AT A TIME. Never batch multiple findings together. Never present more than one finding per response.

3. **NO AUTONOMOUS FIXES**: Never implement a fix without explicit user approval via AskUserQuestion response.

### Auto Mode

1. **UPFRONT QUESTIONS ONLY**: Ask ALL clarifying questions together in a single interaction BEFORE beginning the fix loop. After the user confirms, do NOT stop to ask — proceed autonomously through every finding.

2. **BEST-EFFORT DECISIONS**: For each finding, decide whether and how to fix it based on the [Auto Mode Decision Criteria](#auto-mode-decision-criteria). Apply fixes or skip findings without waiting for user input.

3. **PREFER TDD**: When the project has test infrastructure (test framework configured, existing test files), use the TDD workflow (Red → Green → Refactor) for TDD-eligible findings. Fall back to direct fix when TDD is not feasible.

4. **PROGRESS REPORTING**: Show a brief one-line status after each finding is processed. Do NOT present full finding details — just the finding number, title, and action taken.

5. **STOP ON FAILURE**: If a fix fails to compile or breaks existing tests, revert the change, record the finding as skipped (with reason), and continue to the next finding. Do NOT stop to ask the user.

### Both Modes

- **STATE TRACKING**: After presenting the summary, write progress state to `.code-reviews/.handle-cr-state.json`. Update this file after each finding is processed. This enables recovery after context compaction.

## Argument Parsing

Parse `$ARGUMENTS` to determine mode, severity filter, and code review file:

**Mode** (positional, optional):
- `auto` — autonomous mode: ask questions upfront, then fix/skip without stopping
- (omitted) — interactive mode (default)

**Severity filter** (positional, optional):
- `high` — only Critical + High findings
- `medium` — Critical + High + Medium findings
- `all` (default) — all findings

**File** (remaining argument, optional):
- If a file path is provided: Use that specific file
- Otherwise: Use the most recent `.code-reviews/CODE_REVIEW_*.md` file

Examples: `auto`, `auto high`, `high`, `auto medium myreview.md`, `all myreview.md`

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

### Step 2b: Detect Test Infrastructure (Auto Mode Only)

When in auto mode, detect whether the project has test infrastructure:

1. **Search for test files**: Look for files matching `*.test.*`, `*.spec.*`, `*_test.*`, `*Tests.*`, or directories named `tests`, `__tests__`, `test`
2. **Search for test framework config**: Look for `jest.config.*`, `pytest.ini`, `pyproject.toml` (with pytest section), `*.csproj` (with test SDK), `go.mod` (with testing), `Cargo.toml` (with dev-dependencies), etc.
3. **Identify test command**: Determine how to run tests (e.g., `dotnet test`, `go test ./...`, `npm test`, `pytest`, `cargo test`)

Record in state:
```json
{
  "testInfra": {
    "available": true|false,
    "framework": "xunit|jest|pytest|go-test|...",
    "testCommand": "dotnet test|npm test|..."
  }
}
```

### Step 3: Check for Existing State

Check if `.code-reviews/.handle-cr-state.json` exists:
- If yes and it references the same review file, offer to resume from where we left off
- If no or different file, start fresh

### Step 4: Present Summary and Initialize State

#### Interactive Mode

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

#### Auto Mode

Show the summary AND the planned action for every finding, then ask for confirmation.

**4a. Build the action plan.** For each finding, apply the [Auto Mode Decision Criteria](#auto-mode-decision-criteria) to determine the planned action: **Fix (TDD)**, **Fix**, **Fix All Similar**, **Defer**, or **Skip**.

**4b. Present the plan:**

```
## Code Review: [filename] — Auto Mode

| Severity | Count |
|----------|-------|
| 🔴 Critical | X |
| 🟠 High | X |
| 🟡 Medium | X |
| 🟢 Low | X |

**Total findings:** N | **Test infrastructure:** [Yes (framework) | No]

### Planned Actions

| # | Severity | Title | File | Planned Action | Reason |
|---|----------|-------|------|----------------|--------|
| 1 | 🔴 Critical | Null ref in handler | Foo.cs:42 | Fix (TDD) | Behavioral bug, tests available |
| 2 | 🟠 High | SQL injection | Bar.cs:17 | Fix | Security, no test seam |
| 3 | 🟡 Medium | Extract shared logic | Baz.cs:99 | Defer | Requires design decision on abstraction |
| 4 | 🟡 Medium | Rename method | Qux.cs:12 | Skip | Naming/cosmetic |
| ... | ... | ... | ... | ... | ... |

### Questions

[List any findings that need user input — e.g., findings with multiple fix options where the agent can't confidently choose. For each, state the finding number, the options, and what the agent recommends.]

If no questions: "No ambiguous findings — ready to proceed."
```

**4c. Ask for confirmation:**

```
AskUserQuestion with:
- question: "Review the plan above. Should I proceed, or do you want to adjust any items? (You can say things like '#3 fix instead of skip' or 'skip all Low')"
- header: "Auto Mode Plan"
```

⚠️ **STOP HERE AND WAIT FOR USER RESPONSE.**

**4d. Process user response:**
- If the user says "go", "proceed", "yes", "looks good", etc.: begin the fix loop
- If the user adjusts items: update the plan accordingly, re-display the changed rows, and ask again
- If the user answers the listed questions: record their choices for use during the fix loop

#### Both Modes — Initialize State

Write initial state to `.code-reviews/.handle-cr-state.json`:
```json
{
  "mode": "interactive|auto",
  "reviewFile": ".code-reviews/CODE_REVIEW_xxx.md",
  "totalFindings": N,
  "currentIndex": 0,
  "processed": [],
  "actions": { "fixed": 0, "fixedTdd": 0, "fixedBatch": 0, "skipped": 0, "dismissed": 0, "deferred": 0 },
  "similarGroups": { "pattern-name": [1, 3, 7] },
  "deferSystem": null,
  "testInfra": { "available": false },
  "plannedActions": { "1": "fixTdd", "2": "fix", "3": "defer", "4": "skip" }
}
```

### Step 5: Process Findings

#### Interactive Mode — Process Each Finding (MANDATORY STOP POINT)

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

**5c. Handle the final response** (both modes use these action implementations):

→ Jump to [Action Implementations](#action-implementations).

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

#### Auto Mode — Autonomous Fix Loop

After the user confirms the plan in Step 4, iterate through all findings automatically:

**For each finding**, starting with the highest severity:

1. **Read the planned action** from the confirmed plan (or user-overridden action)
2. **Execute the action** using the [Action Implementations](#action-implementations). For **Defer** actions: detect or reuse `deferSystem`, create a follow-up work item with finding details, severity, and deferral reason.
3. **Verify** (fix actions only): Run `testCommand` (if available) or verify compilation after each fix. If verification fails:
   - Revert the change
   - Record as skipped with reason: `"fix failed: [error summary]"`
   - Continue to next finding
4. **Report progress** (one line):
   ```
   ✅ #N [Title] — [action taken] | 📋 #N [Title] — deferred: [work item ref] | ❌ #N [Title] — skipped: [reason]
   ```
5. **Update state file** (same format as interactive mode)
6. **Process similar findings together**: When reaching a finding that belongs to a similar group and the planned action is "Fix All Similar", process all findings in the group at once, then skip them individually as they come up.
7. **Continue** to next finding. Do NOT stop.

### Action Implementations

These implementations are shared by both modes.

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
- **Dismiss**: Record as dismissed. In interactive mode, the user may provide a reason via the free-form "Other" option — if so, store it. Otherwise record reason as `"dismissed"`. In auto mode, include the dismissal reason from the decision criteria.
- **Defer**: Create a work item in the project's tracking system:
  1. **Detect tracking system**: Check project CLAUDE.md for references to tracking systems (Beans, Azure DevOps, GitHub Issues, TODO comments, etc.)
  2. **First defer**: If no system detected and `deferSystem` is null in state file, ask the user which system to use via AskUserQuestion. Store the choice in state file under `"deferSystem"`.
  3. **Subsequent defers**: Reuse `deferSystem` from state file.
  4. **Create work item**: Create the item in the appropriate system (e.g., Beans task, GitHub issue, TODO comment in code). Store the work item reference.
- **Other** (free-form, interactive mode only): Implement whatever the user describes. If user types "Stop", jump to Step 6.

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

### Step 7: Clean Up Review File

Ask whether to delete the code review file that was just processed:

```
AskUserQuestion with:
- question: "Delete the code review file ([filename])?"
- header: "Clean up"
- options:
  - label: "Yes", description: "Delete the review file"
  - label: "No", description: "Keep the review file"
```

If the user chooses "Yes", delete the code review file.

### Step 8: Re-review Suggestion

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

## Auto Mode Decision Criteria

Use these rules to decide the planned action for each finding in auto mode.

### Fix (TDD) — preferred when all conditions met:
- Test infrastructure is available
- Finding is TDD-eligible (behavioral bug, not a test file, not cosmetic)
- Confidence >= 60

### Fix (direct) — when TDD not feasible:
- Severity is Critical or High (always attempt, regardless of confidence)
- Severity is Medium AND confidence >= 70 AND fix is clear/actionable
- Finding has a single unambiguous suggested fix
- Security findings (always attempt)

### Fix All Similar — when pattern group exists:
- Multiple findings share the same pattern
- The fix for one applies uniformly to all
- Apply TDD variant if test infrastructure available and eligible

### Defer — when the finding is valid but can't be fixed in this pass:
- Fix would require significant design decisions beyond the finding's scope
- Finding is too broad or requires larger architectural changes
- Fix has multiple conflicting options AND user did not resolve in upfront questions
- Finding spans multiple subsystems or requires cross-cutting coordination

Create a follow-up work item in the project's issue tracker (using the same `deferSystem` logic as interactive mode). Include the finding details, severity, and why it was deferred.

### Skip — when fix is not appropriate:
- Severity is Low (unless trivially fixable like removing unused imports)
- Confidence < 70 for Medium severity
- Purely cosmetic: naming, formatting, comment style, whitespace
- Documentation-only findings
- Finding is subjective or opinion-based

### Dismiss — when finding is likely a false positive:
- Confidence < 50
- Finding contradicts established project conventions (as seen in codebase)
- Finding is clearly incorrect based on context

### Summary of severity thresholds:

| Severity | Default Action | Override |
|----------|---------------|----------|
| 🔴 Critical | Always fix | — |
| 🟠 High | Always fix | Skip if confidence < 50 |
| 🟡 Medium | Fix if confidence >= 70 | Skip if cosmetic/subjective |
| 🟢 Low | Skip | Fix if trivial (unused imports, etc.) |

## Notes

- Always order findings by severity (Critical → High → Medium → Low)
- For each fix, verify the change compiles before moving on
- If a fix fails, offer alternatives (interactive) or skip with reason (auto)
- Keep track of all changes for the final summary
- If context is compacted mid-session, read `.code-reviews/.handle-cr-state.json` to resume
- Always use literal Unicode emoji characters (🔴🟠🟡🟢), never `:shortcode:` syntax like `:yellow_circle:`
