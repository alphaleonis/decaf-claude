---
name: auto-tdd
description: TDD-first development with automated review. Runs a TDD session (plan → red-green-refactor) then auto-review on the result. Use when building features test-first with quality gates.
argument-hint: "<feature description> [--review quick|std|max] [--max-iterations N] [--spec <path>]"
---

# Auto TDD

Build a feature with TDD, then auto-review the result: **plan → TDD → review-fix loop**.

- **Step 1** plans the TDD session in the main context and gets user approval
- **Step 2** executes the approved TDD plan via subagent (context isolation)
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

- Identify the project language and idiomatic test patterns
- Identify the test framework in use (or the standard one for the language)
- Identify the **test command** (e.g., `dotnet test`, `go test ./...`, `cargo test`, `npm test`)
- Note existing test structure and naming conventions
- Explore the codebase to understand existing modules, patterns, and similar features

Apply idiomatic patterns for the detected language:

- **C#**: xUnit/NUnit/MSTest. Interfaces for DI. `async Task` for async tests.
- **Go**: Built-in `testing` package. Table-driven tests with `t.Run()`. Implicit interfaces.
- **Rust**: Built-in `#[test]` in `#[cfg(test)]`. Traits + generics for DI. Integration tests in `tests/`.

Follow whatever conventions the project already uses.

**1b. Design the TDD plan:**

Based on the feature description and codebase exploration:

- Identify the public interface (new types, methods, functions)
- List behaviors to test — ordered by priority, described as user-facing outcomes (not implementation steps)
- Identify opportunities for deep modules (small interface, deep implementation)
- Design interfaces for testability
- Identify the first tracer bullet (the one behavior that proves the path works end-to-end)

**1c. Present plan and ask for approval:**

```
## Auto TDD Plan

**Feature**: {feature description}
**Language**: {language} | **Test framework**: {framework} | **Test command**: {command}

### Interface

{Proposed public interface — types, methods, signatures}

### Behaviors (in TDD order)

1. 🎯 {tracer bullet behavior} ← tracer bullet
2. {next behavior}
3. {next behavior}
...

### Deep Module Opportunities

{Any identified opportunities, or "None identified"}

After TDD completes, `/auto-review` will run in **{reviewMode}** mode (max {maxIterations} iterations).
```

Ask via `AskUserQuestion`:
```
question: "Review the TDD plan above. Approve, adjust behaviors, or change the interface?"
```

Wait for user response. Apply adjustments if any.

### Step 2: TDD Execution (Subagent)

Launch a **general-purpose subagent** using the Agent tool to execute the approved plan. The subagent runs `/decaf-dev:tdd` with the plan baked into the prompt so it skips its own planning step.

**Subagent prompt template:**

> Run `/decaf-dev:tdd` using the Skill tool, with the following arguments containing the pre-approved plan.
>
> **IMPORTANT**: The planning phase (Step 1) has already been completed and approved by the user. Do NOT ask the user for plan approval — go directly to execution (Step 2: Tracer Bullet).
>
> **Feature**: {feature description}
>
> **Language**: {language} | **Test framework**: {framework} | **Test command**: {testCommand}
>
> **Approved interface**:
> {interface from approved plan}
>
> **Approved behaviors (in TDD order)**:
> 1. 🎯 {tracer bullet} ← start here
> 2. {behavior 2}
> 3. {behavior 3}
> ...
>
> Execute the full red-green-refactor loop for each behavior. When complete, report:
> 1. Summary of behaviors implemented (which passed, which had issues)
> 2. List of all files created or modified
> 3. Final test results (pass/fail counts)

Wait for the subagent to complete. Record results.

Report to the user:

```
## TDD Complete

**Behaviors implemented**: {X}/{total}
**Files modified**: {list}
**Tests**: {pass count} passing

Starting auto-review...
```

If the TDD subagent reports that it could not implement any behaviors (total failure), ask the user whether to proceed with auto-review anyway or stop.

### Step 3: Auto Review

Run `/decaf-review:auto-review` using the Skill tool, passing through the review arguments:

```
/decaf-review:auto-review {reviewMode} --max-iterations {maxIterations} {--spec specPath if provided}
```

Auto-review will automatically detect the scope from uncommitted changes (which includes everything the TDD subagent produced).

The auto-review skill manages its own subagent lifecycle — let it run to completion.

### Step 4: Final Summary

After auto-review completes, present a combined summary:

```
## Auto TDD Complete

### TDD Phase
**Behaviors**: {X}/{total} implemented
**Files**: {list of files created/modified}
**Tests**: {pass count} passing

### Review Phase
{Summary from auto-review — iterations, findings fixed, deferred, skipped}

### Result
{One-line overall assessment: e.g., "Feature implemented with N behaviors, M review findings addressed."}
```

## Notes

- The TDD subagent gets a fresh context window — this allows complex features without exhausting the main context
- The planning step stays in the main context so the user can interact naturally
- Auto-review runs in the main context because it manages its own subagent lifecycle
- If the user didn't specify `--review`, default to `std` mode — TDD-produced code benefits from a standard review pass
- The subagent should follow all TDD conventions from the `/tdd` skill (vertical slices, behavior-focused tests, no horizontal slicing)
