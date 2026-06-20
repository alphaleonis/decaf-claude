---
name: resolve-refactor
description: Walk through refactoring plan opportunities one at a time and decide a resolution for each — apply, apply incrementally, skip, dismiss, or defer. Use "auto" for autonomous application.
argument-hint: "[auto] [file]"
---

# Resolve Refactoring Opportunities

Iterate through the refactoring units in a refactoring plan, presenting each unit and resolving it. Every unit ends with a resolution: applied, applied incrementally, skipped, dismissed, or deferred.

**Two modes:**
- **Interactive** (default): present one unit at a time, wait for user input.
- **Auto** (`auto` argument): ask clarifying questions upfront, then autonomously apply each unit using best judgment.

## Critical Behavior Requirements

**YOU MUST FOLLOW THESE RULES:**

### Interactive Mode (default)

1. **MANDATORY STOP**: Use `AskUserQuestion` to present each unit and wait for the user's choice BEFORE taking ANY action. Do NOT implement refactorings autonomously.
2. **ONE AT A TIME**: Process refactoring units ONE AT A TIME. Never batch. Never present more than one unit per response.
3. **NO AUTONOMOUS REFACTORING**: Never implement a refactoring without explicit user approval via an AskUserQuestion response.

### Auto Mode

1. **UPFRONT QUESTIONS ONLY**: Ask ALL clarifying questions together in a single interaction BEFORE the loop. After the user confirms, do NOT stop to ask — proceed autonomously through every unit.
2. **BEST-EFFORT DECISIONS**: For each unit, decide whether to apply, skip, or defer based on the unit's star rating and the [Verify-First Rule](#verify-first-rule). No per-unit approval. Prefer **Apply (Incremental)** for Large-effort or multi-file units so verification happens between steps.
3. **STOP ON FAILURE**: If an applied refactoring does not compile/build, revert it, record the unit as skipped (with reason), and continue. Do NOT stop to ask.
4. **PROGRESS REPORTING**: Show a one-line status after each unit (number, title, resolution). Do NOT print full unit details.

### Both Modes

- **STATE TRACKING**: After the summary, write progress to `.refactoring-plans/.resolve-refactor-state.json`. Update it after each unit — this enables recovery after context compaction.

## Verify-First Rule

Applies before applying any refactoring. A refactoring opportunity is a claim about a past analysis run, not a fact about the code now — files may have changed since the plan was generated (the unit may already have been done, or the cited code may have moved or been deleted).

1. **Re-check the unit against the current code**: do the cited files and the "Before" structure still exist where the plan says? Has the refactoring already been applied, in whole or in part?
2. If the unit is **stale** (already refactored, code removed, mis-cited): resolve as **dismissed** with the evidence; do not apply a change to satisfy a phantom opportunity.
3. If the current code has **diverged but the opportunity still applies**: adapt the plan's steps to the current structure rather than applying them blindly.

Refactorings preserve behavior. If applying a unit would require a behavior change to make it compile (e.g., the "After" sketch assumes a signature the code no longer has), stop and treat it as needing adaptation — never force a behavior change in the name of a structural refactoring.

## Argument Parsing

Parse `$ARGUMENTS`:

**Mode** (positional, optional): `auto` for autonomous; omitted = interactive.

**File** (remaining argument, optional):
- If a file path is provided: use that specific plan file.
- Otherwise: use the most recent `.refactoring-plans/REFACTOR_PLAN_*.md` file.

Examples: `auto`, `auto myplan.md`, `.refactoring-plans/REFACTOR_PLAN_2026-03-03_14-30-45.md`.

## Execution Steps

### Step 1: Locate the Refactoring Plan File

**If `$ARGUMENTS` specifies a file:** verify it exists; if not, inform the user and exit.

**Otherwise, find the latest plan:**
```bash
ls .refactoring-plans/REFACTOR_PLAN_*.md 2>/dev/null | sort -r | head -1
```

If no refactoring plan exists, inform the user:
> No refactoring plan found. Run `/decaf-quality:refactor` first to generate one.

### Step 2: Parse Refactoring Units

Read the refactoring plan file and extract all refactoring units. Units are identified by headers matching:
```
### #N ★★★|★★ Title
```

Build a list of units with: number (#1, #2, …), star rating (★★★ or ★★), title, impact, effort, files involved, category, problem description, before/after code sketches, and refactoring steps.

### Step 3: Check for Existing State

If `.refactoring-plans/.resolve-refactor-state.json` exists and references the same plan file, offer to resume. Otherwise start fresh.

### Step 4: Present Summary and Initialize State

```
## Refactoring Plan: [filename]

| Rating | Count |
|--------|-------|
| ★★★ | X |
| ★★ | X |

**Total units:** N

[interactive] I'll walk you through each unit ONE AT A TIME — Apply / Apply (Incremental) / Skip / Dismiss / Defer.
[auto] I'll apply each unit autonomously and report results.
```

Write initial state to `.refactoring-plans/.resolve-refactor-state.json`:
```json
{
  "planFile": ".refactoring-plans/REFACTOR_PLAN_xxx.md",
  "mode": "interactive|auto",
  "totalUnits": N,
  "currentIndex": 0,
  "processed": [],
  "actions": { "applied": 0, "appliedIncremental": 0, "skipped": 0, "dismissed": 0, "deferred": 0 },
  "deferSystem": null
}
```

### Step 5: Process Each Unit (highest star rating first)

For each unit, starting with ★★★ then ★★:

**5a. Present the unit** (interactive mode; auto mode skips straight to acting):
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

**5b. Decide the resolution.**

*Interactive:* AskUserQuestion supports max 4 options, so use a two-step flow.

**Step 1 — top-level choice (STOP and WAIT for response):**
```
AskUserQuestion with:
- question: "How would you like to handle this refactoring opportunity?"
- header: "Action"
- options:
  - label: "Apply...", description: "Implement this refactoring (more options)"
  - label: "Skip...", description: "Don't apply this now (more options)"
```

**Step 2 — follow-up based on choice (STOP and WAIT for response):**

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

*Auto:* apply the Verify-First Rule, then decide — apply ★★★/★★ units that still exist (prefer Apply Incremental for Large-effort or multi-file units); dismiss stale units; defer when a unit needs adaptation or surfaces a suspected bug.

**5c. Apply the resolution:**

- **Apply**: implement the full refactoring:
  1. Re-verify the unit (Verify-First Rule).
  2. Read all affected files.
  3. Implement all steps from the plan.
  4. Verify the code compiles/builds.
  5. [interactive] show the user what changed.
- **Apply (Incremental)**: implement step by step:
  1. Re-verify the unit (Verify-First Rule).
  2. For each step in the plan:
     a. Read the relevant files.
     b. Implement that step only.
     c. Verify compilation/build.
     d. Show what changed.
     e. [interactive] wait for user confirmation before the next step (AskUserQuestion: "Continue to next step?" — "Continue" / "Stop here"). [auto] continue automatically; on a build failure, revert that step and stop the unit (record it as skipped with reason).
  3. After all steps (or the user stops), show cumulative changes.
- **Skip**: record as skipped, proceed to next.
- **Dismiss**: record as dismissed. In interactive mode the user may provide a reason via the free-form "Other" option — if so, store it; otherwise record `"dismissed"`. In auto mode, record the Verify-First evidence as the reason.
- **Defer**: create a work item in the project's tracking system.
  1. **Detect tracking system**: check the project CLAUDE.md for references to tracking systems (Nibs, Azure DevOps, GitHub Issues, TODO comments, etc.).
  2. **First defer**: if no system is detected and `deferSystem` is null in the state file, ask the user which system to use (AskUserQuestion). Store the choice under `"deferSystem"`. In auto mode with no detectable system, fall back to a TODO comment / Markdown note and record that choice.
  3. **Subsequent defers**: reuse `deferSystem` from the state file.
  4. **Create the work item** and store its reference.
- **Other** (free-form, interactive only): implement whatever the user describes. If the user types "Stop", jump to Step 6.

**5d. Update the state file** after each action:
```json
{
  "currentIndex": N,
  "processed": [..., { "unit": N, "action": "applied|appliedIncremental|skipped|dismissed|deferred|other" }],
  "actions": { "applied": X, "appliedIncremental": Y, "skipped": W, "dismissed": D, "deferred": F }
}
```
Dismissed units carry a `"reason"`; deferred units carry a `"workItem"` reference.

**5e. Show progress:** `✅ Unit #N addressed. (X of M remaining)`

**5f. Next unit.** Interactive: return to 5a, one at a time. Auto: continue without stopping.

### Step 6: Session Summary

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
- [files modified and what was refactored]

### Remaining Opportunities
- [skipped/unprocessed units; deferred items with their work-item references]

### Dismissed Opportunities
- [dismissed items with reasons, if any]
```

Delete `.refactoring-plans/.resolve-refactor-state.json` when complete.

### Step 7: Re-review Suggestion

If any refactorings were applied during the session, offer to verify the modified files via `AskUserQuestion`:
```
- Yes — run /decaf-quality:code-review low on the modified files to verify refactorings
- No — done for now
```
If Yes, invoke `/decaf-quality:code-review low <modified-files>`.

### Step 8: Clean Up Plan File

Ask whether to delete the refactoring plan file (`AskUserQuestion`: Yes / No). Delete only if the user chooses Yes.

## Notes

- Order units by star rating (★★★ first, then ★★).
- Refactorings preserve behavior — verify each applied unit compiles/builds before moving on.
- If a refactoring fails to build, revert it; offer alternatives (interactive) or skip with reason (auto).
- Keep all changes tracked for the final summary.
- If context is compacted mid-session, read `.refactoring-plans/.resolve-refactor-state.json` to resume.
- Use literal Unicode star characters (★), never `:shortcode:` syntax.
