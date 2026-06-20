---
name: auto-dev
description: Direct development with automated review. Plans implementation, executes via subagent, then auto-reviews. Use for work that isn't test-driven (UI, config, styling, infrastructure, scaffolding).
argument-hint: "<feature description> [--review quick|std|max] [--max-iterations N] [--spec <path>]"
---

# Auto Dev

Build a feature directly, then auto-review the result: **plan → implement → review-fix loop**.

Same structure as `auto-tdd` but without the TDD workflow — for work where test-first development isn't practical (UI design, configuration, styling, scaffolding, infrastructure, templates, etc.).

- **Step 1** plans the implementation in the main context and gets user approval
- **Step 2** executes the approved plan via subagent (context isolation)
- **Step 3** runs `/decaf-review:auto-review` on the result

## Argument Parsing

Parse `$ARGUMENTS`:

1. **Feature description** (required): Everything that isn't a flag — describes what to build
2. **Review mode**: `--review quick|std|max` (default: `std`) — passed to auto-review
3. **Max review iterations**: `--max-iterations N` (default: 3) — passed to auto-review
4. **Spec path**: `--spec <path>` — passed to auto-review for spec compliance checking

## Execution Steps

### Step 1: Plan (Main Context)

This step runs in the main context so the user can interact with the plan.

**1a. Detect project context:**

- Identify the project language(s), framework(s), and build system
- Identify the **build/verify command** if applicable (e.g., `dotnet build`, `npm run build`, `go build ./...`, `cargo build`)
- Explore the codebase to understand existing modules, patterns, conventions, and similar features
- Note project structure, naming conventions, and existing patterns to follow

**1b. Design the implementation plan:**

Based on the feature description and codebase exploration:

- Identify the files to create or modify
- List implementation steps — ordered so each step builds on the last and produces a working (or at least compilable) state
- Identify patterns from existing code that should be followed
- Identify the first tracer bullet (the one step that proves the approach works end-to-end)
- Note any dependencies, prerequisites, or setup needed

**1c. Present plan and ask for approval:**

```
## Auto Dev Plan

**Feature**: {feature description}
**Language**: {language} | **Framework**: {framework} | **Build command**: {command or "N/A"}

### Implementation Steps

1. 🎯 {tracer bullet step} ← tracer bullet
2. {next step}
3. {next step}
...

### Files

| Action | File | Purpose |
|--------|------|---------|
| Create | src/components/Foo.tsx | New component |
| Modify | src/routes.ts | Register new route |
| ... | ... | ... |

### Patterns to Follow

{Existing conventions and patterns identified in the codebase, or "None — new area"}

After implementation, `/auto-review` will run in **{reviewMode}** mode (max {maxIterations} iterations).
```

Ask via `AskUserQuestion`:
```
question: "Review the plan above. Approve, adjust steps, or change the approach?"
```

Wait for user response. Apply adjustments if any.

### Step 2: Implementation (Subagent)

Launch a **general-purpose subagent** using the Agent tool to execute the approved plan.

**Subagent prompt template:**

> Implement the following pre-approved plan. The user has already reviewed and approved it — do NOT ask for confirmation. Just implement.
>
> **Feature**: {feature description}
>
> **Language**: {language} | **Framework**: {framework} | **Build command**: {buildCommand or "N/A"}
>
> **Approved implementation steps:**
> 1. 🎯 {tracer bullet step} ← start here
> 2. {step 2}
> 3. {step 3}
> ...
>
> **Files to create/modify:**
> {files table from approved plan}
>
> **Patterns to follow:**
> {patterns from approved plan}
>
> **Execution rules:**
> - Implement each step in order
> - After each step, verify the project still builds/compiles (run `{buildCommand}` if available)
> - If a step fails to compile, fix the issue before moving on
> - Follow existing project conventions and the patterns listed above
> - If the code you write is testable and the project has test infrastructure, feel free to add tests — but this is not required and you do not need to follow a red-green-refactor cycle
> - Do NOT refactor unrelated code
>
> When complete, report:
> 1. Summary of steps completed (which succeeded, which had issues)
> 2. List of all files created or modified
> 3. Build verification result (pass/fail)

Wait for the subagent to complete. Record results.

Report to the user:

```
## Implementation Complete

**Steps completed**: {X}/{total}
**Files modified**: {list}
**Build**: {passing / N/A}

Starting auto-review...
```

If the subagent reports that it could not complete any steps (total failure), ask the user whether to proceed with auto-review anyway or stop.

### Step 3: Auto Review

Run `/decaf-review:auto-review` using the Skill tool, passing through the review arguments:

```
/decaf-review:auto-review {reviewMode} --max-iterations {maxIterations} {--spec specPath if provided}
```

Auto-review will automatically detect the scope from uncommitted changes (which includes everything the implementation subagent produced).

The auto-review skill manages its own subagent lifecycle — let it run to completion.

### Step 4: Final Summary

After auto-review completes, present a combined summary:

```
## Auto Dev Complete

### Implementation Phase
**Steps**: {X}/{total} completed
**Files**: {list of files created/modified}
**Build**: {passing / N/A}

### Review Phase
{Summary from auto-review — iterations, findings fixed, deferred, skipped}

### Result
{One-line overall assessment: e.g., "Feature implemented in N steps, M review findings addressed."}
```

## Notes

- The implementation subagent gets a fresh context window — this allows complex features without exhausting the main context
- The planning step stays in the main context so the user can interact naturally
- Auto-review runs in the main context because it manages its own subagent lifecycle
- If the user didn't specify `--review`, default to `std` mode
- This skill does not require TDD — use `/auto-tdd` when test-first development is appropriate
- Tests are welcome if the code is testable, but not mandatory — no red-green-refactor cycle is enforced
