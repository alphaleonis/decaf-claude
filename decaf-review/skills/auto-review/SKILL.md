---
name: auto-review
description: Automated review-fix-recheck loop. Runs code review, triages findings, fixes autonomously via subagent, and re-reviews if substantial changes were made. Iterates until code stabilizes.
argument-hint: "[quick|std|max] [--max-iterations N] [--spec <path>] [path] [instructions]"
---

# Auto Review

Automated loop: **review → triage → fix → re-review** until stable.

- **Step 2** delegates to `/decaf-review:code-review` via subagent (context isolation)
- **Step 3** triages findings in the main context using handle-cr auto's decision criteria
- **Step 4** executes the confirmed plan via subagent (context isolation)
- **Step 5** decides whether to re-review based on change magnitude

## Argument Parsing

Parse `$ARGUMENTS`:

1. **Review mode**: `quick`, `max`, or `std` (default) — passed to `/code-review` for the first iteration
2. **Max iterations**: `--max-iterations N` (default: 3) — hard cap on review-fix cycles
3. **Spec path**: `--spec <path>` — passed through to `/code-review`
4. **Scope**: Specific file/directory path, or all uncommitted changes
5. **Instructions**: Any remaining text passed through to `/code-review`

## Execution Steps

### Step 1: Initialize

1. Set `iteration = 1`, `maxIterations` from args (default 3)
2. Set `reviewMode` from args (default `std`)
3. Build `codeReviewArgs` — the full argument string to pass to `/code-review` (mode + spec + scope + instructions)
4. Record the initial commit/diff baseline for measuring change magnitude later
5. **Detect test infrastructure:**
   - Search for test files: `*.test.*`, `*.spec.*`, `*_test.*`, `*Tests.*`, directories `tests`, `__tests__`, `test`
   - Search for test framework config: `jest.config.*`, `pytest.ini`, `*.csproj` (test SDK), `go.mod`, `Cargo.toml`, etc.
   - Identify test command (e.g., `dotnet test`, `go test ./...`, `npm test`, `pytest`, `cargo test`)
   - Record: `testInfra = { available: true/false, framework: "...", testCommand: "..." }`
6. **Detect work item tracking system** from project CLAUDE.md (Beans, Azure DevOps, GitHub Issues, etc.) — store as `deferSystem`
7. Inform the user:

```
## Auto Review Starting

**Mode**: {reviewMode} | **Max iterations**: {maxIterations} | **Test infra**: {Yes (framework) | No}
**Scope**: {scope description}

Starting review-fix loop...
```

### Step 2: Code Review (Subagent)

Launch a **general-purpose subagent** using the Agent tool:

**First iteration** — use the user's specified mode and scope:

> Run the `/decaf-review:code-review {codeReviewArgs}` skill using the Skill tool.
> When complete, report:
> 1. The path of the generated review file
> 2. The verdict (APPROVED or NEEDS_CHANGES)
> 3. The count of findings by severity

**Subsequent iterations** (iteration > 1) — use `quick` mode, scoped to modified files:

> Run the `/decaf-review:code-review quick {modifiedFileList}` skill using the Skill tool.
> Focus the review on regressions and new issues introduced by the previous round of fixes.
> When complete, report:
> 1. The path of the generated review file
> 2. The verdict (APPROVED or NEEDS_CHANGES)
> 3. The count of findings by severity

Wait for the subagent to complete.

- If verdict is **APPROVED** or no findings → go to **Step 6** (done)
- Otherwise → continue to **Step 3**

Report to the user:
```
### Iteration {N} — Review Complete
**Review file**: {path}
**Findings**: {Critical} 🔴 | {High} 🟠 | {Medium} 🟡 | {Low} 🟢
Triaging findings...
```

### Step 3: Triage Findings (Main Context)

Read the review file produced in Step 2 and build the action plan. This is the planning half of handle-cr auto — lightweight in context since it only reads the review file and applies decision criteria.

**3a. Parse findings** using the heading pattern:
```
### #N 🔴|🟠|🟡|🟢 Severity: Title
```

Extract for each finding:
- Number, severity, title
- File and line
- Issue description and suggested fix
- Confidence score
- Category

**3b. Identify similar findings** — group findings that share the same underlying pattern (e.g., "missing null check", "missing empty collection guard"). Track these groups for batch fixing.

**3c. Build action plan** — for each finding, determine the planned action:

| Condition | Action |
|-----------|--------|
| Test infra available + behavioral bug + not test file + not cosmetic + confidence ≥ 60 | `fixTdd` |
| Critical or High severity | `fix` |
| Medium + confidence ≥ 70 + clear single fix | `fix` |
| Security finding | `fix` |
| Multiple findings share same pattern + fix applies uniformly | `fixBatch` |
| Requires design decisions, spans subsystems, multiple conflicting options | `defer` |
| Low severity (unless trivially fixable like unused imports) | `skip` |
| Medium + confidence < 70, or cosmetic/subjective/doc-only | `skip` |
| Confidence < 50, contradicts conventions, clearly incorrect | `dismiss` |

Severity thresholds:

| Severity | Default Action | Override |
|----------|---------------|----------|
| 🔴 Critical | Always fix | — |
| 🟠 High | Always fix | Skip if confidence < 50 |
| 🟡 Medium | Fix if confidence ≥ 70 | Skip if cosmetic/subjective |
| 🟢 Low | Skip | Fix if trivial (unused imports, etc.) |

**3d. Handle deferred findings immediately** (in main context, before launching fix subagent):
- For each finding marked `defer`: create a work item now using `deferSystem`
- If `deferSystem` was not detected in Step 1 and this is the first defer: ask the user once which system to use, then reuse for all subsequent defers
- Record work item references for the final summary

**3e. Decide whether to ask the user:**

- **Iteration 1**: If ANY finding has genuinely ambiguous options that the decision criteria cannot resolve (e.g., multiple valid fix approaches with no clear winner, unclear intent), present the plan and ask via a single `AskUserQuestion`. If all findings resolve cleanly → skip questions and proceed.
- **Iteration > 1**: Never ask. Fully autonomous.

**3f. Present the plan** (always, for visibility):

```
### Iteration {N} — Action Plan

| # | Sev | Title | File | Action | Reason |
|---|-----|-------|------|--------|--------|
| 1 | 🔴 | ... | Foo.cs:42 | Fix (TDD) | Behavioral bug, tests available |
| 2 | 🟠 | ... | Bar.cs:17 | Fix | Security |
| 3 | 🟡 | ... | Baz.cs:99 | Defer | Needs design decision |
| 4 | 🟢 | ... | Qux.cs:12 | Skip | Cosmetic |

**Fix**: X | **Skip**: X | **Defer**: X | **Dismiss**: X
```

If asking the user (3e), use `AskUserQuestion`:
```
question: "Review the plan above. Proceed, or adjust? (e.g., '#3 fix instead of defer', 'skip all Low')"
```
Wait for response. Apply adjustments if any, then proceed.

If no findings have a fix action → skip Step 4, go to **Step 6**.

### Step 4: Execute Fixes (Subagent)

Launch a **general-purpose subagent** to execute the confirmed plan. Build the subagent prompt with:

1. The review file path (so it can read finding details)
2. The planned actions table (finding # → action, only actionable items)
3. Test infrastructure details (test command)
4. Similar groups (which findings to batch)

**Subagent prompt template:**

> You are executing planned fixes for code review findings.
>
> **Review file**: `{reviewFilePath}` — read this for full finding details (issue description, suggested fix, file/line).
>
> **Test command**: `{testCommand}` (or "none — verify compilation only" if unavailable)
>
> **Planned actions:**
>
> | # | Severity | Title | File | Action |
> |---|----------|-------|------|--------|
> | {for each finding with a fix action} |
>
> {If similar groups exist: "**Similar groups**: Findings #{X}, #{Y}, #{Z} share the same pattern — fix as a batch when processing the first one, then skip the rest."}
>
> **Execution rules — process findings in severity order (Critical → Low):**
>
> For each finding:
>
> 1. **Read the finding details** from the review file
> 2. **Execute based on action:**
>    - **fixTdd**: Write a failing test that exposes the issue → run `{testCommand}` → verify the test FAILS (RED) → implement the fix → run tests → verify all pass (GREEN) → refactor if needed → verify still GREEN
>    - **fix**: Apply the suggested fix → run `{testCommand}` to verify (or verify compilation if no test command)
>    - **fixBatch**: Apply the fix pattern to all findings in the similar group → verify
> 3. **Verify**: Run `{testCommand}` after each fix. If verification fails:
>    - Revert the affected files: `git checkout -- <files>`
>    - Record as skipped with reason
>    - Continue to the next finding — do NOT stop
> 4. **Report one line per finding:**
>    - `✅ #N [Title] — fixed` or `✅ #N [Title] — fixed (TDD)` or `✅ #N [Title] — fixed (batch, N files)`
>    - `❌ #N [Title] — skipped: {reason}`
>
> **When all findings are processed**, report:
> 1. Summary: counts of fixed, fixed (TDD), fixed (batch), skipped (with reasons)
> 2. List of all files modified

Wait for the subagent to complete. Record results.

Report to the user:
```
### Iteration {N} — Fixes Complete
✅ Fixed: {X} ({Y} TDD) | ⏭️ Skipped: {X} | 📋 Deferred: {X} | 🗑️ Dismissed: {X}
```

### Step 5: Evaluate Re-review Need

After the fix subagent completes:

1. Count how many findings were actually fixed (from subagent report)
2. Get list of modified files (from subagent report)
3. Run `git diff --stat` to measure total change magnitude

**Re-review is warranted if ANY of these are true:**
- At least **3 findings were fixed** (not skipped/deferred/dismissed)
- Total **lines changed > 50**

**AND** `iteration < maxIterations`.

If re-review is **not** warranted → go to **Step 6**.

Otherwise:
- Record this iteration's summary in history
- Increment `iteration`
- Set `modifiedFileList` to the files modified by fixes
- Report: `Substantial changes detected ({X} fixes, {Y} lines changed). Re-reviewing modified files...`
- Go to **Step 2**

### Step 6: Final Summary

```
## Auto Review Complete

**Iterations**: {N} | **Total findings**: {sum across all iterations}

### Per-Iteration Summary

| Iter | Mode | Findings | Fixed | Skipped | Deferred | Dismissed |
|------|------|----------|-------|---------|----------|-----------|
| 1 | {mode} | {n} | {n} | {n} | {n} | {n} |
| 2 | quick | {n} | {n} | {n} | {n} | {n} |

### Totals

**Fixed**: {X} ({Y} via TDD) | **Skipped**: {X} | **Deferred**: {X} | **Dismissed**: {X}

### Deferred Items
{List deferred findings with work item references, or "None"}

### Remaining (Skipped)
{List skipped findings with reasons, or "None"}

{If maxIterations reached AND last review had fixable findings:
"⚠️ Reached iteration limit ({N}). Consider running another review."}
```

Clean up: delete any `.auto-review-state.json` if used.

## Notes

- Always use literal Unicode emoji characters (🔴🟠🟡🟢), never `:shortcode:` syntax
- The first code review uses the user's specified mode; all re-reviews use `quick`
- Re-reviews scope to only modified files to catch regressions, not re-review unchanged code
- Subagents get fresh context windows — this enables multiple iterations without context exhaustion
- The main context stays lean: it only reads review files and builds plans
- If a re-review finds the same issue that was already fixed (regression), treat it as Critical regardless of original severity
