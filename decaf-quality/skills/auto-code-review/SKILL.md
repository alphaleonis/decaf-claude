---
name: auto-code-review
description: Automated review-fix-recheck loop. Runs code review, triages findings, fixes autonomously via subagent, and re-reviews if substantial changes were made. Iterates until code stabilizes.
argument-hint: "[low|mid|high|max][N] [--max-iterations N] [--spec <path|work-item-ID>] [path] [instructions]"
---

# Auto Code Review

Automated loop: **review → triage → fix → re-review** until stable.

- **Step 2** delegates to `/decaf-quality:code-review` via subagent (context isolation)
- **Step 3** triages findings in the main context using the resolve-code-review auto decision criteria
- **Step 4** executes the confirmed plan via subagent (context isolation)
- **Step 5** decides whether to re-review based on change magnitude

## Argument Parsing

Parse `$ARGUMENTS`:

1. **Review mode**: `low`, `mid` (default), `high`, or `max` — passed to `/code-review` for the first iteration. The legacy keywords `quick` and `std` are accepted as aliases for `low` and `mid`. A roster-cap suffix on the mode (`mid4`, `high6`) is accepted and forwarded verbatim to `/code-review` for the first iteration. Always pass the resolved mode explicitly to `/code-review` — the review runs in a subagent, where `/code-review`'s interactive mode selection cannot reach the user. Re-reviews (Step 5) always run uncapped `mid` scoped to modified files.
2. **Max iterations**: `--max-iterations N` (default: 3) — hard cap on review-fix cycles
3. **Spec**: `--spec <path | work-item-ID>` — passed through to `/code-review`
4. **Scope**: Specific file/directory path, or all uncommitted changes
5. **Instructions**: Any remaining text passed through to `/code-review`

## Execution Steps

### Step 1: Initialize

1. Set `iteration = 1`, `maxIterations` from args (default 3)
2. Set `reviewMode` from args (default `mid`)
3. Build `codeReviewArgs` — the full argument string to pass to `/code-review` (mode + spec + scope + instructions); the mode is always present, even when defaulted
4. Record the initial commit/diff baseline for measuring change magnitude later
5. **Detect test infrastructure:**
   - Search for test files: `*.test.*`, `*.spec.*`, `*_test.*`, `*Tests.*`, directories `tests`, `__tests__`, `test`
   - Search for test framework config: `jest.config.*`, `pytest.ini`, `*.csproj` (test SDK), `go.mod`, `Cargo.toml`, etc.
   - Identify test command (e.g., `dotnet test`, `go test ./...`, `npm test`, `pytest`, `cargo test`)
   - Record: `testInfra = { available: true/false, framework: "...", testCommand: "..." }`
6. **Detect work item tracking system** from project CLAUDE.md (Azure DevOps, GitHub Issues, Nibs, etc.) — store as `deferSystem`
7. Inform the user:

```
## Auto Code Review Starting

**Mode**: {reviewMode} | **Max iterations**: {maxIterations} | **Test infra**: {Yes (framework) | No}
**Scope**: {scope description}

Starting review-fix loop...
```

### Step 2: Code Review (Subagent)

Launch a **general-purpose subagent** using the Agent tool:

**First iteration** — use the user's specified mode and scope:

> Run the `/decaf-quality:code-review {codeReviewArgs}` skill using the Skill tool.
> When complete, report:
> 1. The path of the generated review file
> 2. The verdict (APPROVED or NEEDS_CHANGES)
> 3. The count of findings by severity

**Subsequent iterations** (iteration > 1) — use `mid` mode, scoped to modified files:

> Run the `/decaf-quality:code-review mid {modifiedFileList}` skill using the Skill tool.
> Focus the review on regressions and new issues introduced by the previous round of fixes.
> When complete, report:
> 1. The path of the generated review file
> 2. The verdict (APPROVED or NEEDS_CHANGES)
> 3. The count of findings by severity

Re-reviews use `mid`, not `low`: gated dispatch keeps a small modified-file diff cheap anyway, and `mid` runs the validation wave — an autonomous fixer must not consume unvalidated findings.

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

Read the review file produced in Step 2 and build the action plan. This is the planning half of resolve-code-review auto — lightweight in context since it only reads the review file and applies decision criteria.

**3a. Parse primary findings** using the heading pattern:
```
### #N 🔴|🟠|🟡|🟢 Severity: Title
```

Extract for each finding:
- Number, severity, title
- File and line
- Issue description and suggested fix
- Confidence anchor (100, 75, or 50) and any `unvalidated` / `validation failed` marker
- Category

Pre-existing Issues, **Testing Gaps**, and **Residual Risks** are **not** auto-triaged — the loop fixes the change under review, not the backlog or those awareness lists. Carry them into the final summary as awareness items.

**Minor — Consistency findings ARE triaged.** They are verified, change-introduced, and usually a single mechanical edit, so the loop acts on the unambiguous ones. Parse the Consistency one-liners (`file:line — title (agent)`) from the **Minor Findings → Consistency** bucket alongside the `### #N` primaries; the fix subagent reads the cited location to determine the edit. Apply the action criteria below (mechanical edit → `fix`; needs a design choice → `defer`/`skip`).

**3b. Identify similar findings** — group findings that share the same underlying pattern (e.g., "missing null check", "missing empty collection guard"). Track these groups for batch fixing.

**3c. Build action plan** — for each finding, determine the planned action:

| Condition | Action |
|-----------|--------|
| Test infra available + behavioral bug + not test file + not cosmetic + anchor ≥ 75 + not `unvalidated` | `fixTdd` |
| Critical or High severity at anchor 75+ | `fix` |
| Medium at anchor 100, or anchor 75 with clear single fix | `fix` |
| Security finding at anchor 75+ | `fix` |
| Multiple findings share same pattern + fix applies uniformly | `fixBatch` |
| **Critical at anchor 50** — never auto-fix unverified criticals | `defer` |
| Requires design decisions, spans subsystems, multiple conflicting options | `defer` |
| Low severity (unless trivially fixable like unused imports) | `skip` |
| **Minor — Consistency**, single mechanical edit (correct a comment/doc, add a sibling-matching attribute, rename for convention, add a null guard a finding pinpoints) | `fix` |
| **Minor — Consistency** needing a choice (wire-vs-remove a dead contract, a behavior-changing guard) | `defer` (or `skip` to awareness) |
| Medium at anchor 75 that is cosmetic/subjective, or `unvalidated` Medium/Low | `skip` |
| Contradicts project conventions, clearly incorrect from context | `dismiss` |

Summary by severity and anchor:

| Severity | Anchor | Default Action |
|----------|--------|----------------|
| 🔴 Critical | 75–100 | Always fix |
| 🔴 Critical | 50 | Defer — a human decides on unverified criticals |
| 🟠 High | 75–100 | Always fix |
| 🟡 Medium | 100 | Fix |
| 🟡 Medium | 75 | Fix if clear single fix; skip if cosmetic/subjective |
| 🟢 Low | any | Skip unless trivial |
| 🔵 Minor (Consistency) | — | Fix if a single mechanical edit; defer/skip if it needs a choice |

**3d. Handle deferred findings immediately** (in main context, before launching fix subagent):
- For each finding marked `defer`: create a work item now using `deferSystem`
- If `deferSystem` was not detected in Step 1 and this is the first defer: ask the user once which system to use, then reuse for all subsequent defers
- Record work item references for the final summary

**3e. Decide whether to ask the user:**

- **Iteration 1**: If ANY finding has genuinely ambiguous options that the decision criteria cannot resolve (e.g., multiple valid fix approaches with no clear winner, a Critical at anchor 50 the user might prefer to fix now), present the plan and ask via a single `AskUserQuestion`. If all findings resolve cleanly → skip questions and proceed.
- **Iteration > 1**: Never ask. Fully autonomous.

**3f. Present the plan** (always, for visibility):

```
### Iteration {N} — Action Plan

| # | Sev | Anchor | Title | File | Action | Reason |
|---|-----|--------|-------|------|--------|--------|
| 1 | 🔴 | 100 | ... | Foo.cs:42 | Fix (TDD) | Behavioral bug, tests available |
| 2 | 🟠 | 75 | ... | Bar.cs:17 | Fix | Security |
| 3 | 🔴 | 50 | ... | Baz.cs:99 | Defer | Unverified critical — human decision |
| 4 | 🟢 | 75 | ... | Qux.cs:12 | Skip | Cosmetic |

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
> 2. **Verify the finding first.** A finding is a claim, not an order — re-verify it against the current code before changing anything:
>    - Not real (refuted by the code, already fixed, mis-cited)? Report `not-addressing` with the concrete evidence. Do NOT apply a fix to satisfy the finding.
>    - Real, but the suggested fix would cause harm (breaks behavior, conflicts with a documented decision)? Report `declined`, citing the specific harm.
>    - Real, but the suggested fix is wrong? Fix it correctly and report `fixed (differently)` with a one-line why.
>    - No performative agreement — the evidence decides, not the reviewer's authority.
> 3. **Execute based on action:**
>    - **fixTdd**: Write a failing test that exposes the issue → run `{testCommand}` → verify the test FAILS (RED) → implement the fix → run tests → verify all pass (GREEN) → refactor if needed → verify still GREEN
>    - **fix**: Apply the suggested fix → run `{testCommand}` to verify (or verify compilation if no test command)
>    - **fixBatch**: Apply the fix pattern to all findings in the similar group (verify each location first — a pattern real in one file may be guarded in another) → verify
> 4. **Verify**: Run `{testCommand}` after each fix. If verification fails:
>    - Revert the affected files: `git checkout -- <files>`
>    - Record as skipped with reason
>    - Continue to the next finding — do NOT stop
> 5. **Report one line per finding:**
>    - `✅ #N [Title] — fixed` / `✅ #N [Title] — fixed (TDD)` / `✅ #N [Title] — fixed (batch, N files)` / `✅ #N [Title] — fixed (differently): {why}`
>    - `🚫 #N [Title] — not addressing: {evidence}` / `⛔ #N [Title] — declined: {harm}`
>    - `❌ #N [Title] — skipped: {reason}`
>
> **When all findings are processed**, report:
> 1. Summary: counts of fixed, fixed (TDD), fixed (batch), fixed (differently), not-addressing, declined, skipped (with reasons)
> 2. List of all files modified

Wait for the subagent to complete. Record results — `not-addressing` counts as dismissed (with evidence), `declined` counts as skipped (with reason).

Report to the user:
```
### Iteration {N} — Fixes Complete
✅ Fixed: {X} ({Y} TDD) | 🚫 Not addressing: {X} | ⏭️ Skipped: {X} | 📋 Deferred: {X} | 🗑️ Dismissed: {X}
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
## Auto Code Review Complete

**Iterations**: {N} | **Total findings**: {sum across all iterations}

### Per-Iteration Summary

| Iter | Mode | Findings | Fixed | Skipped | Deferred | Dismissed |
|------|------|----------|-------|---------|----------|-----------|
| 1 | {mode} | {n} | {n} | {n} | {n} | {n} |
| 2 | mid (modified files) | {n} | {n} | {n} | {n} | {n} |

### Totals

**Fixed**: {X} ({Y} via TDD, {Z} differently) | **Not addressing**: {X} | **Skipped**: {X} | **Deferred**: {X} | **Dismissed**: {X}

### Deferred Items
{List deferred findings with work item references, or "None"}

### Remaining (Skipped / Declined)
{List skipped and declined findings with reasons, or "None"}

### Awareness Items
{Pre-existing Issues and Minor Findings (Consistency / Testing Gaps / Residual Risks) from the last review, or "None"}

{If maxIterations reached AND last review had fixable findings:
"⚠️ Reached iteration limit ({N}). Consider running another review."}
```

Clean up: delete any `.decaf/auto-review/state.json` if used.

## Notes

- Always use literal Unicode emoji characters (🔴🟠🟡🟢), never `:shortcode:` syntax
- The first code review uses the user's specified mode (default `mid`); all re-reviews use `mid` scoped to modified files (gated dispatch keeps them lean, and the validation wave runs)
- Re-reviews scope to only modified files to catch regressions, not re-review unchanged code
- Subagents get fresh context windows — this enables multiple iterations without context exhaustion
- The main context stays lean: it only reads review files and builds plans
- If a re-review finds the same issue that was already fixed (regression), treat it as Critical regardless of original severity
