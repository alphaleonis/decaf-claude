---
name: auto-code-review
description: Automated review-fix-recheck loop. Runs code review, triages findings, fixes autonomously via subagent, and re-reviews if substantial changes were made. Iterates until code stabilizes.
argument-hint: "[bugs|review|audit] [roster=N] [models=low|norm|high] [evidence=strong|norm|any] [reach=narrow|norm|wide] [--max-iterations N] [--spec <path|work-item-ID>] [--report] [path] [instructions]"
---

# Auto Code Review

Automated loop: **review → triage → fix → re-review** until stable.

- **Step 2** delegates to `/decaf-quality:code-review` via subagent (context isolation)
- **Step 3** triages findings in the main context using the resolve-code-review auto decision criteria
- **Step 4** executes the confirmed plan via subagent (context isolation)
- **Step 5** decides whether to re-review based on change magnitude

## Argument Parsing

Parse `$ARGUMENTS`:

1. **Review spec**: a `/code-review` preset — `bugs`, `review` (default) or `audit` — optionally followed by any of its axis overrides (`roster=N`, `models=`, `evidence=`, `reach=`). Collect the preset and every axis token into one `reviewSpec` string and forward it **verbatim** to `/code-review` for the first iteration; this skill does not interpret the axes, so a new one works here the day it ships.
   **Always pass a resolved preset explicitly** — the review runs in a subagent, where `/code-review`'s interactive preset selection cannot reach the user. Re-reviews (Step 5) do NOT inherit `reviewSpec` verbatim — they narrow within the caller's preset family and never exceed its roster, per Step 5.4 — and do not forward `--spec` either: compliance was judged on the first pass, and the re-review question is what the fixes broke.
2. **Max iterations**: `--max-iterations N` (default: 3) — hard cap on review-fix cycles
3. **Spec**: `--spec <path | work-item-ID>` — passed through to `/code-review`
4. **`--report`**: produce a comparison-grade session report for skill tuning (`@../../conventions/session-report.md`). Forward `--report` to **every** `/code-review` invocation (first pass and re-reviews), keep the session ledger through the loop (Steps 1–5), and write the report folder in Step 6.5. Callers (`auto-tdd`/`auto-dev`) may pass an implementation-phase record to include.
5. **Scope**: Specific file/directory path, or all uncommitted changes
6. **Instructions**: Any remaining text passed through to `/code-review`

## Execution Steps

### Step 1: Initialize

1. Set `iteration = 1`, `maxIterations` from args (default 3)
2. Set `reviewSpec` from args (default `review`) — the preset plus any axis overrides, as one verbatim string
3. Build `codeReviewArgs` — the full argument string to pass to `/code-review` (`reviewSpec` + `--spec` if set + `--report` if set + scope + instructions). The preset is always present, even when defaulted; axis overrides appear only if the caller gave them
4. Record the initial commit/diff baseline for measuring change magnitude later. **Also establish a recoverable snapshot** before any fix/probe phase mutates the uncommitted tree: `SNAPSHOT=$(git stash create)` — this records a commit object of the current uncommitted state *without* touching the working tree or the stash stack (empty output = tree already clean, so `HEAD` is the restore point). Keep `SNAPSHOT` for the loop; if work is ever lost to a bad revert or probe, restore it with `git checkout <SNAPSHOT> -- <path>` (or `git stash apply <SNAPSHOT>`). Prefer this over auto-committing WIP, so the user keeps control of their commit history.
5. **Detect test infrastructure:**
   - Search for test files: `*.test.*`, `*.spec.*`, `*_test.*`, `*Tests.*`, directories `tests`, `__tests__`, `test`
   - Search for test framework config: `jest.config.*`, `pytest.ini`, `*.csproj` (test SDK), `go.mod`, `Cargo.toml`, etc.
   - Identify test command (e.g., `dotnet test`, `go test ./...`, `npm test`, `pytest`, `cargo test`)
   - Record: `testInfra = { available: true/false, framework: "...", testCommand: "..." }`
6. **Detect work item tracking system** from project CLAUDE.md (Azure DevOps, GitHub Issues, Nibs, etc.) — store as `deferSystem`
7. **If `--report`**: start the session ledger (in-context notes; no state file). Record now: the exact invocation arguments including the resolved `reviewSpec`, the changeset baseline, and the caller's implementation-phase record if provided. Through the loop, record per iteration (the resolved spec + dropped agents, scope, verdict, finding counts, validation stats, review-file path, orchestrator usage from the Agent tool result), per fix round (subagent usage, action counts, files modified), every main-context triage decision, the Step 5.4 delta classification, any escalation trigger, + chosen `reReviewPreset`, and **every anomaly** (resume/nudge/retry/kill/flow deviation — or note "none" at the end). See `@../../conventions/session-report.md`.
8. Inform the user:

```
## Auto Code Review Starting

**Review**: {reviewSpec} | **Max iterations**: {maxIterations} | **Test infra**: {Yes (framework) | No}
**Scope**: {scope description}

Starting review-fix loop...
```

### Step 2: Code Review (Subagent)

Launch a **general-purpose subagent** using the Agent tool:

**First iteration** — use the caller's `reviewSpec` and scope:

> Run the `/decaf-quality:code-review {codeReviewArgs}` skill using the Skill tool.
> When complete, report:
> 1. The path of the generated review file
> 2. The verdict (APPROVED or NEEDS_CHANGES)
> 3. The count of findings by severity

**Subsequent iterations** (iteration > 1) — use `{reReviewPreset}` (computed in Step 5.4), scoped to modified files:

> Run the `/decaf-quality:code-review {reReviewPreset} {--report if set} {modifiedFileList}` skill using the Skill tool.
> Focus the review on regressions and new issues introduced by the previous round of fixes.
> For each behavior-changing fix, probe the boundary behavior of the changed decision point (inputs on and *between* the cases its new tests pin), not only the finding it addressed.
> When complete, report:
> 1. The path of the generated review file
> 2. The verdict (APPROVED or NEEDS_CHANGES)
> 3. The count of findings by severity

Wave re-reviews keep the screen and validation wave: wave findings are not self-calibrated, and an autonomous fixer must not consume unscreened, unvalidated wave claims. The solo seat is exempt by construction — it calibrates at generation, which is why iteration 1 under `bugs` already feeds the fixer directly and why a `bugs`-family re-review needs no funnel either. Re-reviews narrow within the caller's preset family and the roster is monotone — never above the first pass's, escalation only on a named trigger (Step 5.4): session evidence shows verdict-driving regressions in fix deltas are caught by the floor plus the best-fitting judgment specialists, while extra seats re-verify known-clean territory at full price.

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

**Exception — `reach=wide`.** Under that reach the review promotes pre-existing defects into the primary Findings list (labelled `pre-existing`) rather than into the informational section, because the operator asked for them: an autonomous loop is often the only reader that code will get. Triage them like any other primary finding. This is the one case where the loop is *meant* to touch the backlog, and it only happens when `reach=wide` was chosen explicitly or came from a preset that implies it — never by default.

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
| **High at anchor 50** — uncertain existence or impact; occurs only via the `bugs` path, which applies no confidence gate | `defer` |
| **Medium/Low at anchor 50** (`bugs` path only, same reason) | `skip` (awareness) |
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
| 🟠 High | 50 | Defer — uncertain; a human decides (`bugs` path only) |
| 🟡 Medium | 100 | Fix |
| 🟡 Medium | 75 | Fix if clear single fix; skip if cosmetic/subjective |
| 🟡 Medium | 50 | Skip to awareness (`bugs` path only) |
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
>    - Real, and the finding offers **alternative fixes** (e.g. a behavioral change vs. a doc-only clarification)? Default to the **least invasive** option that fully resolves the stated issue at its severity; escalate to the stronger option only when the minimal one leaves the issue unresolved. Note which option you took.
>    - No performative agreement — the evidence decides, not the reviewer's authority.
> 3. **Execute based on action** — but FIRST capture a per-fix restore point so a failed fix can be undone precisely without touching the rest of the uncommitted work: `FIX_SNAPSHOT=$(git stash create)` (records the current state as a commit object; leaves the working tree and stash stack untouched):
>    - **fixTdd**: Write a failing test that exposes the issue → run `{testCommand}` → verify the test FAILS (RED) → implement the fix → run tests → verify all pass (GREEN) → refactor if needed → verify still GREEN
>    - **fix**: Apply the suggested fix → run `{testCommand}` to verify (or verify compilation if no test command)
>    - **fixBatch**: Apply the fix pattern to all findings in the similar group (verify each location first — a pattern real in one file may be guarded in another) → verify
>    - **Boundary self-check for any behavior-changing fix** (a new or changed predicate, gate, threshold, or normalization): before moving on, enumerate the decision point's boundary inputs — including inputs that fall *between* the cases your new tests pin — and add a test case for each. A gate tested only at `-42 → reject` and `task → accept` ships broken for `task-42`.
> 4. **Verify**: Run `{testCommand}` after each fix. If verification fails, undo ONLY the fix you just applied — never discard the rest of the uncommitted work:
>    - Restore just the files you edited from the per-fix snapshot: `git checkout $FIX_SNAPSHOT -- <files-you-edited>` (or, if `git stash create` was unavailable, re-edit each file back to its exact pre-fix content).
>    - **Never `git checkout -- <files>`** (no snapshot ref) — that reverts to HEAD and wipes every uncommitted change in the file, i.e. the whole change under review, not just your failed fix.
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

4. **Set `reReviewPreset` — conservative by default, within the caller's preset family.** A re-review asks a different question from the first pass: *what did the fixes break?* — not *what else is wrong with this code?* So it narrows rather than repeating, and it never spends more than the original ask did. Two rules bound every choice below:

   - **Roster monotonicity.** A re-review's roster never exceeds `max(3, first-pass resolved roster)` — read the first pass's resolved roster from the first review file's header (the `**Preset**` line, or count the `**Reviewers**` list). Fix-delta *size* never raises the roster: the response to a risky delta is *which* specialists fill the capped slots (gated dispatch and the ranking pick seats to fit the delta), not more of them.
   - **Escalation needs a named trigger.** Moving above the default rung requires one of: the fix delta touches concurrency/locking, a trust boundary (auth, parsing of external input, secrets), or data mutations; a previous re-review in this loop found a regression; or a fix failed verification and was re-applied. Name the trigger in the report (and, under `--report`, in the ledger). No trigger, no escalation — regardless of how many lines the fixes changed.

   Classify the fix delta (count changed **executable production lines**, excluding docs, comments, test files, generated files; note which triggers, if any, are present), then:

   - **Caller ran `bugs`** (the single seat):
     - default — `bugs` scoped to the modified files: the seat again, on a smaller diff. Its self-calibration already drove iteration 1; the re-review is the same mechanism pointed at less code.
     - a named trigger stands — `bugs roster=3`: the cheap wave (floor + best-fitting specialist, `models=low`, `evidence=norm`, `reach=narrow`), adding corroboration and the screen/validation funnel exactly where the fixer introduced risk. (A caller who explicitly ran the `bugs roster=N` wave re-reviews as `bugs roster=3`, default and triggered alike — the ceiling rule caps it.)
   - **Caller ran `review` or `audit`** (a wave):
     - default — `review roster=4 reach=narrow`
     - a named trigger stands — `review roster=min(6, first-pass resolved roster) reach=narrow`. There is no uncapped rung: a large or high-risk delta gets at most what the original change got.
   - **Later re-reviews** (iteration ≥ 3): `bugs` callers keep the rule above; wave callers drop to `bugs roster=3`, scoped to the newest fix round's delta only. By the third pass the changeset's character is known; a minimal pass is regression insurance on the latest fixes, not fresh discovery. (`roster` counts the floor, so `roster=3` = floor + the single best-fitting specialist.)

   **`reach=narrow` on every re-review, and it matters more than the roster.** The first pass already reported what the surrounding code is missing; a later pass re-reporting the same absences is noise the triage step has to reject again each round. Narrowing to defects introduced by the fixes is what stops the loop re-litigating its own backlog.

   **`evidence` stays `norm` in re-review waves.** At three or four seats corroboration is scarce; `strong` demands a lone reviewer score ≥80 alone, which is exactly how small waves binned consensus defects (dcc-sk3k).

   **Never inherit `audit` into a re-review.** If the first pass ran `audit` — the case where pre-existing defects are promoted to primary and get fixed — later passes still narrow. Otherwise every iteration re-surfaces the whole backlog and the loop cannot converge.

Then:
- Record this iteration's summary in history
- Increment `iteration`
- Set `modifiedFileList` to the files modified by fixes
- Report: `Substantial changes detected ({X} fixes, {Y} lines changed). Re-reviewing modified files ({reReviewPreset})...`
- Go to **Step 2**

### Step 6: Final Summary

```
## Auto Code Review Complete

**Iterations**: {N} | **Total findings**: {sum across all iterations}

### Per-Iteration Summary

| Iter | Review | Findings | Fixed | Skipped | Deferred | Dismissed |
|------|--------|----------|-------|---------|----------|-----------|
| 1 | {reviewSpec} | {n} | {n} | {n} | {n} | {n} |
| 2 | {reReviewPreset} (modified files) | {n} | {n} | {n} | {n} | {n} |

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

### Step 6.5: Session Report (only with `--report`)

Assemble the session report from the ledger, per `@../../conventions/session-report.md`:

1. Create `.decaf/session-reports/<YYYY-MM-DD>-<work-item-or-slug>-code-review-session/` (never overwrite — suffix `-2`, `-3`, … on collision).
2. **Copy** each iteration's consolidated review file into it as `iteration-N-consolidated-review.md` (byte-identical copies via `cp`, not regeneration).
3. Write `README.md` in the convention's six-section format: iteration overview, agent inventory, token usage (per-reviewer/validator figures come from each consolidated file's Session Metrics section), process observations (the anomalies ledger — "zero anomalies" is itself a result), timeline, per-agent yield. Apply the truth discipline: harness figures verbatim, `[Estimate]`/`[Inference]`/`[Unverified]` labels, missing data recorded as missing.
4. Tell the user: `📊 Session report: <path>` after the final summary.

The report records; cross-session comparison and tuning decisions stay with the operator.

## Notes

- Always use literal Unicode emoji characters (🔴🟠🟡🟢), never `:shortcode:` syntax
- The first code review uses the user's specified preset (default `review`); all re-reviews narrow **within that preset's family** — `reach=narrow` always, roster never above the first pass's, escalation only on a named trigger per Step 5.4. `bugs` callers re-review with the seat itself; wave callers default to `review roster=4` and drop to `bugs roster=3` from the third pass. Wave re-reviews keep the screen and validation wave
- Re-reviews scope to only modified files to catch regressions, not re-review unchanged code
- Subagents get fresh context windows — this enables multiple iterations without context exhaustion
- The main context stays lean: it only reads review files and builds plans
- If a re-review finds the same issue that was already fixed (regression), treat it as Critical regardless of original severity
