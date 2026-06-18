# DevMeta — Development Metadata Framework (Global: devmeta)

> **Note:** This is the **global** (`devmeta`) version of the DevMeta commands, installed at `~/.claude/commands/devmeta/`. Projects may also have a local `/devmeta:` command set in `.claude/commands/devmeta/` that takes precedence for project-specific customizations.

A Claude Code slash-command framework for autonomous, increment-driven software delivery. DevMeta manages the full lifecycle: scoping, planning, parallel execution via subagents, and structured reflection.

## Core Loop

```
/devmeta:go                         # Start here. Drives everything autonomously.
```

`/devmeta:go` reads project state, figures out what to do next, and does it — no prompting required. It loops: **Plan → Execute → Inspect & Adapt → next iteration**.

## Commands

### Normal use — only two commands

In day-to-day use you should only ever need these:

| Command | Purpose |
|---------|---------|
| `/devmeta:start-increment-spec` | Create a new increment (scope of work) via interactive dialogue |
| `/devmeta:go` | Autonomous driver — assesses state, executes next work, loops until done |

The workflow is: run `start-increment-spec` once to define the work, then run `go` and let it drive. `go` handles planning, execution, reflection, and moving between iterations on its own.

### Internal commands (invoked by `/devmeta:go`, not by the user)

These are orchestration primitives that `/devmeta:go` calls internally. You can run them manually for debugging, but in normal use you should not — calling them outside the autonomous loop breaks the flow and forces you to stitch iteration boundaries by hand.

| Command | Purpose |
|---------|---------|
| `/devmeta:plan-iteration N` | Break an iteration into features and tasks, optimized for parallel execution |
| `/devmeta:run [--all]` | Execute features — one subagent per feature, parallel across independent waves |
| `/devmeta:reflect N` | Inspect & Adapt cycle — code review, docs audit, gap verification, plan reassessment |
| `/devmeta:status` | Read-only progress report with suggested next action (safe to run anytime) |
| `/devmeta:migrate-from-adapt` | One-time migration from ADAPT (.adapt/) to DevMeta (.devmeta/) |

## Concepts

- **Increment** — A major scope of work (e.g., "Document management + audit export"). Contains multiple iterations.
- **Iteration** — A deliverable slice within an increment. Produces a PR. Followed by an I&A cycle.
- **Feature** — The unit of parallel execution. One subagent runs one feature. Tasks within are sequential.
- **I&A Cycle** — Inspect & Adapt. Runs after every iteration: reviews code quality, verifies scope, updates docs, reassesses the plan.

## Project Structure

DevMeta stores artifacts in `.devmeta/` at the project root:

```
.devmeta/
  devmeta.md                # Project-specific config (test commands, env checks, rules)
  current-increment.md      # Pointer to active increment
  project-history.md        # Narrative record of what was built
  lessons-learned.md        # Accumulated learnings
  increments/
    increment-01-abc/       # <NN>-<XXX>: integer for sorting + 3-letter random suffix
      _overview.md           # Scope, iteration map, exit criteria
      iterations/            # Per-iteration status files
      ia-cycles/             # Per-iteration I&A reports for this increment
  projects/                  # Feature specs and context logs
```

Increment directories use a numeric prefix for sorting plus a 3-letter random suffix
(e.g. `increment-76-abc/`). The suffix prevents merge conflicts when two parallel
branches/worktrees both create the next increment. Iteration numbers within an
increment are unsuffixed (`76.1`, `76.1R`) — they're already namespaced by the
unique parent directory.

Task tracking uses `tk` (tick tracker). Features are epics, work items are tasks.

## Typical Workflow

Two commands per increment, repeated.

```bash
# 1. Start a new increment (interactive scope definition)
/devmeta:start-increment-spec "My Feature"

# 2. Let the autonomous driver take this increment to completion
/devmeta:go
# It will: plan iteration 1 → execute features in parallel →
#          reflect → plan iteration 2 → execute → reflect → ...
#          → close the increment (PR, merge, update current-increment.md) → STOP
# If the loop ever stops mid-increment (interrupt, crash, end of session),
# just run /devmeta:go again — it resumes from tick state, no setup required.

# 3. When the current increment is done, pick the next one:
#    - new scope:       /devmeta:start-increment-spec "Next Feature"  →  /devmeta:go
#    - pre-spec'd one:  edit .devmeta/current-increment.md to point at it  →  /devmeta:go
```

`/devmeta:go` drives **a single increment** to completion. Increment completion is a natural stopping point — the next increment is a priority call the user owns, so the loop exits cleanly when the current one is done and waits for the user to re-invoke. Do NOT manually run `plan-iteration`, `run`, or `reflect` between iterations *within* an increment — `/devmeta:go` calls them itself and will break the autonomous loop if you pre-empt it. `/devmeta:status` is safe to run at any time for a read-only progress check.

## Per-Project Configuration

Drop a `devmeta.md` file in your project's `.devmeta/` directory to customize DevMeta's behavior for that project. Every command reads `.devmeta/devmeta.md` before acting.

Three sections are recognized:

| Section | Purpose | Example |
|---------|---------|---------|
| `## Testing` | Test commands the agent should use | `npm test`, `pnpm vitest`, surgical per-package commands |
| `## Environment` | Pre-flight checks before first iteration | `node --version`, `docker info`, required CLI tools |
| `## Additional Rules` | Project-specific constraints | "Use the `fc` CLI for all operations", "Never modify migrations directly" |

If no `.devmeta/devmeta.md` exists, DevMeta falls back to `package.json` scripts for testing and skips environment checks.

## Key Principles

- **Scope never shrinks.** Only the human can cut scope. The agent works harder or asks for help.
- **Tests must pass.** No task or iteration closes with failing tests.
- **Commit per task, PR per iteration.** Merge before the I&A cycle runs.
- **Self-learning.** Each I&A cycle updates docs so the next iteration is easier than the last.
- **`tk next` drives everything.** The tick structure encodes what to do — the agent follows it.
