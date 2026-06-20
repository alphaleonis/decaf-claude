---
description: DevMeta Delivery Engine (global) — drives increments to completion
---

## Project Context

Read `.devmeta/devmeta.md` from the project root if it exists. It provides
project-specific test commands, environment checks, and additional rules.

If no `.devmeta/devmeta.md` exists:
- Testing: look for `package.json` test scripts
- Environment: skip checks
- Additional rules: none

> **tk mapping:** tk -t epic = DevMeta Feature, tk -t task = DevMeta Task

---

## Purpose

This is the single command that drives the entire project. Run it to start. Run it again to continue. It figures out where the project is and does the next thing, autonomously, until it hits a genuine external blocker or closes all gaps.

**Current increment:** Defined in `.devmeta/current-increment.md`. Follow the pointer to the active increment's `_overview.md` for scope, iterations, and gap analysis. The active line names the increment as `Increment <NN>-<XXX>` (integer + 3-letter random suffix added to avoid parallel-branch collisions); its directory is `.devmeta/increments/increment-<NN>-<XXX>/`. Iteration numbers within use the integer only (`<NN>.1`, `<NN>.1R`).

**You are the project driver.** You don't ask the user what to do — you assess the state and act. The only time you stop and ask is when you need something that requires human action on their physical machine (installing software, creating accounts, providing API keys).

## Phase 0: Assess State

**Ticks are the single source of truth for project state.** Run these commands:

```bash
tk list --all --status all    # Full project state — iterations, features, tasks
tk next                       # What should I do right now?
tk next <iteration-id>        # What's next within the current iteration?
```

Then read context files as needed:
1. `CLAUDE.md` (already loaded)
2. `.devmeta/current-increment.md` — which increment is active
3. Current increment's `_overview.md` — scope, iterations, gap analysis
4. Current iteration's `status.md` in the increment's `iterations/` directory

**The rule: if `tk next` returns a task, do that task.** Don't interpret markdown files to figure out what to do — the tick structure already encodes the answer.

## Iteration Rhythm: Execute → Inspect & Adapt

Every execution iteration is followed by a dedicated I&A cycle. This is structural — not optional, not a task that can be forgotten.

```
Iteration N: Execute (code, tests, commits, PR)
    → closes with "Kick off I&A Cycle NR" task
Iteration NR: Inspect & Adapt (code review, docs audit, plan reassessment, context handoff)
    → last task IS the first concrete task of next iteration (e.g., "Plan Iteration N+1")
Iteration N+1: Execute
    → ...
```

Both execution and I&A cycle iterations are top-level ticks with their own children. Continuity is ensured by making the last I&A cycle task be **real work for the next iteration**, not a meta "Continue to" task. This eliminates the boundary where the agent historically stops.

### Execution Iteration Structure

```
Iteration N (epic, top-level)
├── Feature A: <name> (epic, parent: iteration)
│   ├── Task 1: <implementation work> (task)
│   ├── Task 2: <implementation work> (task)
│   └── Re-ground after Feature A (task)  ← ALWAYS LAST IN EVERY FEATURE
├── Feature B: <name> (epic, parent: iteration)
│   └── ...
├── Create PR for iteration N (task, parent: iteration)
├── Merge PR and return to base branch (task, parent: iteration)  ← MERGE BEFORE I&A CYCLE
├── Commit metadata to base branch (task, parent: iteration)  ← COMMIT .tick/ AND .devmeta/ FILES
└── Kick off I&A Cycle NR (task, parent: iteration)  ← ALWAYS LAST
```

### I&A Cycle Structure

```
Iteration NR: Inspect & Adapt (epic, top-level, blocked by iteration N, runs on base branch from `<increment-dir>/base-branch` after merge)
├── Run /devmeta:reflect N (task)  ← invokes the full 12-step I&A process
└── Plan Iteration N+1 (task)  ← REAL WORK, not a boundary
```

The I&A cycle task invokes `/devmeta:reflect N` as a skill. Do NOT break it into separate tasks -- the skill handles the full sequence internally (code review, docs audit, gap verification, project history update, plan reassessment, and more).

### Re-grounding Task (after every feature)

When you reach a "Re-ground after Feature X" task, do ALL of these before closing it:
1. Update `.devmeta/project-history.md` with entry for what you just built
2. Update iteration `status.md` with feature completion
3. Capture any lessons in `.devmeta/lessons-learned.md`
4. Run `tk list --parent <iteration-id>` to see where you are in the iteration

### Commit Metadata to Base Branch (after every merge)

After merging a PR and returning to the base branch, `.tick/` and `.devmeta/` files will have been modified during orchestration but NOT included in the feature branch PR (since they live on the base branch). You MUST commit them:

```bash
git add .tick/ .devmeta/ tsconfig.tsbuildinfo
git status --short   # verify only metadata files staged
git commit -m "Update .tick/ and .devmeta/ metadata for iteration N"
```

This is NOT optional. Without this step, 30-40 metadata files accumulate as dirty working tree state across iterations. The commit goes directly on the base branch — no PR needed for metadata-only changes.

### Last I&A Cycle Task = First Task of Next Iteration

The last task in every I&A cycle is **concrete work for the next iteration** — typically "Plan Iteration N+1: read scope from _overview.md, create feature tick structure, begin first task." This is NOT a meta/handoff task. It's real work.

When you reach the last I&A cycle task:
1. Do the work described in the task (read scope, create features, create tick structure)
2. Close the task and the I&A cycle iteration
3. Run `tk next` and start executing the first task of the new iteration

## Phase 0.5: Establish Base Branch

The base branch for the current increment is persisted in `<increment-dir>/base-branch` (a plain text file containing just the branch name). This is the **single source of truth** for which branch feature branches are created from, PRs target, and the I&A cycle runs on.

1. Read `.devmeta/current-increment.md` to find the active increment directory.
2. Check if `<increment-dir>/base-branch` exists:

**If the file exists:** Read it. That's the base branch. Verify it exists locally with `git rev-parse --verify <branch>`. If the branch doesn't exist, error and ask the user.

**If the file does NOT exist (first run for this increment):**

This is the ONE exception to "never ask permission" — you MUST ask which branch to use as base:

1. Detect the current branch: `git branch --show-current`
2. Ask the user:
   > Current branch is `<branch>`. Do you want to:
   > 1. Use `<branch>` as the base branch for this increment
   > 2. Create a new branch from `<branch>` to use as base (suggested name: `YYYY-MM-DD-<increment-name>`)
3. If option 2: create the branch (`git checkout -b <name>`), push with `-u origin`
4. Write the chosen branch name to `<increment-dir>/base-branch`

After this phase, the base branch is established. All subsequent operations read it from the file.

## Phase 1: Environment Check (iteration 1 only, or when needed)

Before doing any work, verify the development environment. **Test, don't ask.**

Run the environment checks from `.devmeta/devmeta.md > Environment` if it exists.
If no `.devmeta/devmeta.md`, skip environment checks.

## Phase 2: Execute Based on State

### If `tk next` returns a task: DO IT

Read the task description with `tk show <id>`, do the work, close the task with `tk close <id>`, then run `tk next` again.

### If `tk next` returns an execution iteration (no children): PLAN IT

1. Run `/devmeta:plan-iteration N`
2. Planning MUST create the tick structure:
   - Feature ticks for each feature (parent: iteration)
   - Task ticks for each task within features (parent: feature)
   - **A "Re-ground after Feature X" task as the last task in every feature**
   - **A "Create PR for iteration N" task (parent: iteration)**
   - **A "Merge PR and return to base branch" task (parent: iteration)**
   - **A "Commit metadata to base branch" task (parent: iteration)** — commits `.tick/` and `.devmeta/` files that were modified during orchestration
   - **A "Kick off I&A Cycle NR" task as the last task (parent: iteration)**
3. Also create the I&A cycle iteration tick:
   - `Iteration NR: Inspect & Adapt on Iteration N` (epic, blocked by iteration N)
   - 2 tasks: "Run /devmeta:reflect N" and "Plan Iteration N+1: read scope, create feature tick structure, begin first task"
   - The first task invokes the full I&A cycle skill; the second is concrete work, not a handoff
4. Set dependencies between features (waves: parallel where independent, sequential where dependent)
5. Then immediately start executing (`tk next` → do the first task)

### If `tk next` returns an I&A cycle iteration (no children): CREATE ITS TASKS

Create 2 tasks: "Run /devmeta:reflect N" and "Plan Iteration N+1: read scope, create feature tick structure, begin first task". Then `tk next` to start.

### If `tk next` returns nothing: CHECK STATE

- If all current increment iterations are closed → **increment is complete → STOP.**
  - Write a short completion report (what shipped, any outstanding human-in-the-loop items such as live verification).
  - Do NOT bootstrap a new increment. Do NOT ask the user which increment to start next. The current increment was the scope of this `/devmeta:go` invocation; its end is the end of the run.
  - To start the next one, the user will either run `/devmeta:start-increment-spec` (for fresh scope) or update `.devmeta/current-increment.md` to point at a pre-spec'd increment, then re-invoke `/devmeta:go`.
- If blocked iterations exist → close the blocking iteration first
- If something is stuck → investigate and unblock
- Verify against the current increment's scope — are all items actually closed?

### If NO TICKS EXIST: BOOTSTRAP

Read `.devmeta/current-increment.md` to find the active increment, then read its `_overview.md` and create the iteration ticks. Each iteration is a top-level epic tick. The `/devmeta:plan-iteration N` command creates the features and tasks within each iteration when it's time to execute.

## Critical Rules

**Never ask permission to proceed.** Plan → execute → inspect & adapt → next iteration. That's the loop. `tk next` drives it.

**Never ask "should I continue?" or "want me to proceed?"** The tick structure tells you what to do. Do it.

**Never stop to present a summary or status update *within* an increment.** Completing an iteration, a PR merge, or an I&A cycle is NOT a stopping point. It's a waypoint. Do NOT write "here's where we are" messages. Do NOT present a list of what was accomplished. `tk next` tells you what to do next — do it immediately. The agent stays in "doing work" mode at all times. Completing a large body of work triggers the instinct to summarize and defer to the user — resist this. The tick structure eliminates the decision point.

**The exception: completing an increment IS a stopping point.** Iteration and I&A boundaries are waypoints; increment boundaries are not. When `tk next` returns nothing and all current-increment iterations are closed, stop, write a short completion report, and exit. Do NOT create a "bootstrap next increment" task, do NOT ask which increment to start next, do NOT attempt to pick one from the NOT STARTED list. Increment selection is a human priority call and often requires `/devmeta:start-increment-spec` (interactive) anyway. The user will re-invoke `/devmeta:go` when they're ready for the next one. Structure the final iteration's I&A cycle so its last task is "Close increment N" (update metadata, PR, merge) — nothing after that.

**Test before asking.** If you think something might not work, try it first.

**Tests are autonomous and must pass before moving on.** After every task, run the relevant tests (from `.devmeta/devmeta.md > Testing` or `package.json`). If they fail, fix the code and re-run. This is a loop — implement → test → fail → debug → fix → test → repeat until green. An iteration CANNOT close with failing tests. A task CANNOT close with failing tests. There is no "known failure" state. If a test requires infrastructure, set it up or ask the human for the specific missing resource — do NOT skip the test. Each iteration's "Verify on screen" section is the acceptance test — actually run those commands and verify the output.

**Scope cannot shrink.** You may split, merge, reorder, or inject iterations. You may NOT remove scope items. If something is hard, work harder or ask for help. If something takes longer than expected, it takes longer. Only the human can cut scope. Scope can grow (bugs, discovered gaps) but never shrink.

**Work continues until it succeeds.** A failing test is not a stopping point — it is a problem to solve. A blocked task is not a reason to skip — it is a problem to unblock. The only reasons to stop: missing API keys, missing hardware, or genuinely ambiguous spec. "I couldn't figure it out" is never valid — try a different approach.

**Commit and push regularly.** Commit per task, PR per iteration. After CI passes on the PR, merge it into the base branch (stored in `<increment-dir>/base-branch` — written during Phase 0.5). The I&A cycle iteration runs on the base branch. **Do NOT assume the base branch is `main`** — read it from `<increment-dir>/base-branch`. **Always use `--merge` (not `--squash` or `--rebase`) when merging PRs** so the branch history remains visible in the git graph.

**Run tests constantly.** After every meaningful code change, run the relevant tests. Tests are the heartbeat. If you haven't run tests in the last 3 tasks, something is wrong.
