---
name: resolve-coverage-review
description: Walk through coverage review gaps one at a time and decide a resolution for each — write tests, skip, dismiss, or defer. Use "auto" for autonomous test-writing.
argument-hint: "[auto] [high|medium|all] [file]"
---

# Resolve Coverage Review Gaps

Iterate through the gaps in a coverage review, presenting each grouped gap and resolving it. Every group ends with a resolution: tests written, skipped, dismissed, or deferred.

**Two modes:**
- **Interactive** (default): present one group at a time, wait for user input.
- **Auto** (`auto` argument): ask clarifying questions upfront, then autonomously write tests for each group using best judgment.

## Critical Behavior Requirements

**YOU MUST FOLLOW THESE RULES:**

### Interactive Mode (default)

1. **MANDATORY STOP**: Use `AskUserQuestion` to present each group and wait for the user's choice BEFORE taking ANY action. Do NOT write tests autonomously.
2. **ONE AT A TIME**: Process groups ONE AT A TIME. Never batch. Never present more than one group per response.
3. **NO AUTONOMOUS TESTS**: Never write tests without explicit user approval via an AskUserQuestion response.

### Auto Mode

1. **UPFRONT QUESTIONS ONLY**: Ask ALL clarifying questions together in a single interaction BEFORE the loop. After the user confirms, do NOT stop to ask — proceed autonomously through every group.
2. **BEST-EFFORT DECISIONS**: For each group, decide whether to write tests, skip, or defer based on the gap's severity and the [Verify-First Rule](#verify-first-rule). No per-group approval.
3. **STOP ON FAILURE**: If a written test does not compile, revert it, record the group as skipped (with reason), and continue. Do NOT stop to ask.
4. **PROGRESS REPORTING**: Show a one-line status after each group (number, title, resolution). Do NOT print full group details.

### Both Modes

- **STATE TRACKING**: After the summary, write progress to `.decaf/code-reviews/.resolve-coverage-state.json`. Update it after each group — this enables recovery after context compaction.

## Verify-First Rule

Applies before writing any test. A gap is a claim about a past coverage run, not a fact about the code now — files may have changed since the review.

1. **Re-check the gap against the current code**: does the cited code still exist, uncovered, where the report says?
2. If the gap is **stale** (code removed, already tested, mis-cited): resolve as **dismissed** with the evidence; do not write a test to satisfy a phantom gap.
3. If a written test **fails because the uncovered code is actually buggy** (not because the test is wrong): do NOT leave the suite red and do NOT silently patch production code (out of scope here). Mark the test ignored/skipped with a `TODO` referencing the suspected bug, and **defer** a work item describing it. Record the group as `tests-written (bug suspected)`.

No performative coverage: a test that only executes a line without asserting its behavior is worse than no test — every test must verify an outcome.

## Argument Parsing

Parse `$ARGUMENTS`:

**Mode** (positional, optional): `auto` for autonomous; omitted = interactive.

**Severity filter** (positional, optional):
- `high` — only Critical + High gaps
- `medium` — Critical + High + Medium gaps
- `all` (default) — all gaps

**File** (remaining argument, optional): a specific review file, else the most recent `.decaf/code-reviews/COVERAGE_REVIEW_*.md`.

Examples: `auto`, `auto high`, `high`, `auto medium myreview.md`.

## Execution Steps

### Step 1: Locate the Coverage Review File

**If `$ARGUMENTS` specifies a file:** verify it exists; if not, inform the user and exit.

**Otherwise, find the latest review:**
```bash
ls .decaf/code-reviews/COVERAGE_REVIEW_*.md 2>/dev/null | sort -r | head -1
```

If no coverage review exists, inform the user:
> No coverage review found. Run `/decaf-quality:coverage-review` first to generate one.

### Step 2: Parse Findings

Read the review file and extract findings, identified by headers matching:
```
### #N 🔴|🟠|🟡|🟢 Severity: Title
```

Capture per finding: number, severity, title, file + line range, coverage %, category (`COVERAGE_*`), confidence anchor, why-it-matters, and suggested tests.

**Filter by severity** per the argument: `high` keeps Critical+High; `medium` keeps Critical+High+Medium; `all` keeps everything.

### Step 2.5: Group Findings

Coverage findings are granular (per-line/per-branch). After parsing, group them into logical units:
1. **Group by source file + class/type** (primary grouping).
2. Within a class, **sub-group by method/function** if findings span multiple methods.
3. Each group is one item to present. Group severity = highest among its findings. Group suggested tests = merged list.

The user answers once per class (or method cluster), not once per uncovered line.

### Step 3: Check for Existing State

If `.decaf/code-reviews/.resolve-coverage-state.json` exists and references the same review file, offer to resume. Otherwise start fresh.

### Step 4: Present Summary and Initialize State

```
## Coverage Review: [filename]

| Severity | Count |
|----------|-------|
| 🔴 Critical | X |
| 🟠 High | X |
| 🟡 Medium | X |
| 🟢 Low | X |

**Total gaps:** N (grouped into M units)

[interactive] I'll walk you through each group ONE AT A TIME — Write Tests / Skip / Dismiss / Defer.
[auto] I'll write tests for each group autonomously and report results.
```

Write initial state to `.decaf/code-reviews/.resolve-coverage-state.json`:
```json
{
  "reviewFile": ".decaf/code-reviews/COVERAGE_REVIEW_xxx.md",
  "mode": "interactive|auto",
  "totalFindings": N,
  "totalGroups": M,
  "currentGroupIndex": 0,
  "processed": [],
  "actions": { "testsWritten": 0, "skipped": 0, "dismissed": 0, "deferred": 0 },
  "deferSystem": null
}
```

### Step 5: Process Each Group (highest severity first)

**5a. Present the group** (interactive mode; auto mode skips straight to acting):
```
## Group #N of M: [Severity Icon] [Title — e.g. "PaymentProcessor error paths"]

**File:** `src/PaymentProcessor.cs`
**Coverage:** 45% line, 30% branch
**Gaps:** 3 findings (lines 45-62, 78-85, 102-110)
**Categories:** COVERAGE_ERROR_PATH, COVERAGE_LOGIC

### Why it matters
[Combined assessments from all findings in the group]

### Suggested Tests
1. Should_ReturnError_When_PaymentGateway_TimesOut (lines 45-62)
2. Should_RollbackTransaction_On_PartialFailure (lines 78-85)
3. Should_RetryOnTransientError (lines 102-110)
```

**5b. Decide the resolution.**

*Interactive:* present exactly 4 options in a single flat `AskUserQuestion` and **STOP**:
```
- Write Tests — implement all suggested tests for this group
- Skip — move on, no tracking
- Dismiss — mark as a false positive / stale gap
- Defer — create a work item for later
```

*Auto:* apply the Verify-First Rule, then decide — write tests for Critical/High/Medium gaps that still exist; skip Low/trivial; dismiss stale gaps; defer when a suspected bug surfaces.

**5c. Apply the resolution:**
- **Write Tests**:
  1. Re-verify the gap (Verify-First Rule).
  2. Read the source file for context; find the existing test file or create one following project conventions.
  3. Implement all suggested tests for the group, each asserting real behavior (not just executing the line).
  4. Run the tests; ensure they compile and pass (handle a genuine-bug failure per the Verify-First Rule).
  5. [interactive] show the tests created.
- **Skip / Dismiss**: record (Dismiss may carry a free-form reason).
- **Defer**: create a work item in the project's tracking system.
  1. **Detect tracking system**: check the project CLAUDE.md for references to tracking systems (Nibs, Azure DevOps, GitHub Issues, TODO comments, etc.).
  2. **First defer**: if no system is detected and `deferSystem` is null in state, ask which to use (AskUserQuestion) and store it under `deferSystem`. In auto mode with no detectable system, fall back to a TODO comment / Markdown note.
  3. **Subsequent defers**: reuse `deferSystem` from the state file.

**5d. Update the state file** after each action (processed group with `findingIds` + `action`; dismissed groups carry a reason; deferred groups carry a work-item reference).

**5e. Show progress:** `✅ Group #N addressed. (X of M remaining)`

**5f. Next group.** Interactive: return to 5a, one at a time. Auto: continue without stopping.

### Step 6: Session Summary

```
## Coverage Session Complete

| Action | Count |
|--------|-------|
| Tests Written | X |
| Skipped | X |
| Dismissed | X |
| Deferred | X |

### Tests Created
- [files created/modified and what they cover]

### Remaining Gaps
- [skipped/unprocessed groups; deferred items with references]

### Dismissed
- [stale/false-positive gaps with reasons]
```

Delete `.decaf/code-reviews/.resolve-coverage-state.json` when complete.

### Step 7: Re-review Suggestion

If any tests were written, offer to re-check coverage on the modified files via `AskUserQuestion`:
```
- Yes — run /decaf-quality:coverage-review diff to confirm improved coverage
- No — done for now
```
If Yes, invoke `/decaf-quality:coverage-review diff`.

### Step 8: Clean Up Review File

Ask whether to delete the coverage review file (`AskUserQuestion`: Yes / No). Delete only if the user chooses Yes.

## Notes

- Order groups by severity (Critical → High → Medium → Low).
- Verify each written test compiles and passes before moving on.
- Keep all changes tracked for the final summary.
- If context is compacted mid-session, read `.decaf/code-reviews/.resolve-coverage-state.json` to resume.
- Use literal Unicode severity icons (🔴🟠🟡🟢), never `:shortcode:` syntax.
