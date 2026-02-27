---
name: coverage-review
description: Run code coverage analysis and review gaps for severity and test suggestions
argument-hint: "[diff|full] [path] [instructions]"
---

# Coverage Review

Run code coverage tools, parse results, and launch a reviewer agent to assess which gaps matter and suggest test improvements.

## Argument Parsing

Parse `$ARGUMENTS` to determine:
1. **Mode**: `diff` (default) or `full`
2. **Path**: Optional file/directory to restrict scope
3. **Instructions**: Any additional review instructions

| Mode | Scope | Use Case |
|------|-------|----------|
| `diff` (default) | Changed/new code only (git diff HEAD) | PR review, incremental work |
| `full` | All project files | Baseline assessment, release readiness |

## Execution Steps

### Step 1: Read Coverage Configuration

Look for a `## Coverage` section in the project's CLAUDE.md. Expected format is documented in:

@../conventions/coverage-config.md

If no `## Coverage` section is found, inform the user with the setup template from the convention file and exit:

```
No coverage configuration found in CLAUDE.md.

Add a ## Coverage section to your project's CLAUDE.md. See conventions/coverage-config.md for format and examples.
```

### Step 2: Determine Scope

- **`diff` mode**: Get changed files from `git diff HEAD --name-only`. These files are the review scope. If no uncommitted changes, fall back to `git diff HEAD~1..HEAD --name-only`.
- **`full` mode**: All project source files are in scope.
- If a specific `path` argument is provided, further restrict scope to that path.

If scope is empty (no changed files in diff mode), inform the user and exit.

### Step 3: Run Coverage

Execute the configured coverage command via Bash. Wait for completion.

```bash
# Example: run the command from CLAUDE.md ## Coverage section
<configured command>
```

If the command fails (non-zero exit), show the error output and exit:

```
Coverage command failed (exit code N):
<stderr/stdout>

Check that the command in your CLAUDE.md ## Coverage section is correct.
```

### Step 4: Parse Coverage Report

Find the report file(s) at the configured report path using Glob. Read and parse based on format:

#### Cobertura XML
Extract `<package>` -> `<class>` -> `<line>` elements. Per-file: line-rate, branch-rate, uncovered line numbers.

#### LCOV
Parse `SF:`, `DA:`, `BRDA:`, `BRF:`, `BRH:` records. Per-file: line hits, branch hits, uncovered lines.

#### Clover XML
Extract `<file>` -> `<line>` elements. Per-file: covered/uncovered statements and branches.

**For `diff` mode**: Filter parsed data to only include files from the changed file list (Step 2). Match by file path suffix since coverage tools may use absolute or project-relative paths.

**Extract per-file:**
- Line coverage % and uncovered line ranges
- Branch coverage % and uncovered branch locations
- Whether file is above/below configured thresholds

### Step 5: Build Gap Context

For each file with coverage gaps (below threshold, or with significant uncovered ranges):

1. **Read source code** of uncovered line ranges (include ~5 lines of surrounding context)
2. **Classify uncovered code** broadly:
   - Error handling / exception paths
   - Security-sensitive code (auth, crypto, input validation)
   - Business logic / state transitions
   - Data validation / boundary checks
   - Boilerplate / simple accessors / trivial code
3. **Rank files** by gap severity potential:
   - Error paths and security code > complex business logic > data validation > simple/trivial code

**Cap at top ~15 files** to keep agent context manageable. Summarize the rest as a table:

```markdown
## Additional Files Below Threshold (not sent to reviewer)

| File | Line % | Branch % | Status |
|------|--------|----------|--------|
| ... | ... | ... | ... |
```

### Step 6: Launch Coverage Reviewer Agent

Launch `decaf:coverage-reviewer` via the Task tool with the following prompt structure:

```
Review these code coverage gaps for severity and suggest test improvements.

## Project Coverage Summary
- Overall line coverage: XX% (threshold: YY%) — STATUS
- Overall branch coverage: XX% (threshold: YY%) — STATUS
- Files analyzed: N total, M below threshold

## Coverage Gaps (by priority)

### File: `path/to/file.cs` — 45% line, 30% branch
**Uncovered lines 45-62:**
```<language>
<source code of uncovered lines with surrounding context>
```
**Classification**: Error handling for payment failures

### File: `path/to/other.cs` — 70% line, 55% branch
**Uncovered lines 23-30:**
```<language>
<source code>
```
**Classification**: Business logic — order state transition

...

## Additional Instructions
<any user-provided instructions from $ARGUMENTS>
```

**For `full` mode with many gaps** (more than 8 files below threshold): Consider launching 2 `decaf:coverage-reviewer` agents in parallel, splitting the file list roughly in half by priority rank. Merge the results.

### Step 7: Generate Report

Create a timestamped report file in `.code-reviews/` at the repo root. Never overwrite existing reviews.

```bash
mkdir -p .code-reviews
FILENAME=".code-reviews/COVERAGE_REVIEW_$(date '+%Y-%m-%d_%H-%M-%S').md"
```

**Report format:**

```markdown
# Coverage Review

**Mode**: diff | **Date**: YYYY-MM-DD
**Scope**: N files analyzed, M below threshold
**Overall**: XX% line (threshold: YY%), XX% branch (threshold: YY%)

## Summary

| Metric | Value | Threshold | Status |
|--------|-------|-----------|--------|
| Line coverage | 72% | 80% | Below |
| Branch coverage | 65% | 70% | Below |
| Changed lines covered | 45/60 (75%) | — | — |

**Verdict**: NEEDS_COVERAGE | ADEQUATE

- **NEEDS_COVERAGE**: Any metric below configured thresholds
- **ADEQUATE**: All metrics at or above thresholds

---

## Gap Findings

### #1 Critical: Uncovered error handling in PaymentProcessor.cs

| | |
|---|---|
| **File** | `src/PaymentProcessor.cs:45-62` |
| **Coverage** | 0% (18 lines) |
| **Category** | error-handling-gap |

**Why it matters:** <agent's severity assessment>

**Suggested tests:**
- <specific test case suggestions from agent>

---

### #2 High: ...
...

---

## Coverage by File

| File | Line % | Branch % | Status | Uncovered Lines |
|------|--------|----------|--------|-----------------|
| `src/PaymentProcessor.cs` | 45% | 30% | Below | 45-62, 78-85 |
| `src/UserAuth.cs` | 70% | 55% | Below | 23-30 |
| `src/Utils.cs` | 95% | 90% | OK | — |
```

### Output Notification

After creating the report file, inform the user:

```
Coverage review complete: .code-reviews/COVERAGE_REVIEW_2026-02-27_14-30-45.md
```

## Example Usage

```
/decaf:coverage-review                          # diff mode, changed files
/decaf:coverage-review full                     # Full project coverage
/decaf:coverage-review diff src/Payments/       # diff mode, specific path
/decaf:coverage-review full focus on error paths # Full mode with instructions
```
