---
description: Plan an iteration (global) — refine scope into feature specs, graph-partition for independence
argument-hint: [iteration-number]
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

## Context

- Today's date: !`date +%Y-%m-%d`
- Target iteration: $ARGUMENTS
- Ticks initialized: !`test -d .tick && echo "yes" || echo "no"`

## Design Philosophy

**The feature is the unit of context.** Each feature runs in one subagent session (~200k tokens). Tasks within a feature are sequential steps — not independent workers.

**Your primary job is finding feature boundaries that maximize independence.** More independence = more parallelism = faster wall-clock time.

**Workers are smart.** They have CLAUDE.md, the spec, the codebase, and docs/current/. Task descriptions guide — they don't micromanage.

**This project uses AI-agentic development.** All code is written by agents. Prioritize consistency, mainstream patterns, and well-known libraries. See `docs/current/principles-and-choices.md`.

## Your Task

### Step 0: Initialize

```bash
tk list 2>/dev/null || tk init
```

### Step 1: Read the Iteration Plan

Read the increment overview and the specific iteration plan:

```
Current increment's _overview.md (find via .devmeta/current-increment.md)
Current increment's iterations/iteration-<N>/plan.md  (if exists)
```

If no detailed plan exists yet for this iteration, read the overview's rough scope and create the iteration's `plan.md` with refined scope.

Also read:
- `CLAUDE.md` — project orientation
- `docs/current/principles-and-choices.md` — all architectural decisions
- `.devmeta/lessons-learned.md` — don't repeat past mistakes
- Any relevant spec or architecture docs referenced in the increment overview

### Step 1.5: Scope Check — Does This Iteration Still Make Sense?

Before planning in detail, evaluate the iteration's scope against what actually exists:

1. **Is the scope too large for one iteration?** If mapping the work produces 8+ features or the foundation feature alone is massive, **split the iteration.** Update the current increment's `_overview.md` directly. Renumber subsequent iterations.
2. **Has previous work already covered some of this scope?** Remove deliverables that are already done.
3. **Are there new deliverables that belong here?** Cleanup tasks from the previous reflection, discoveries during implementation, or prerequisites that weren't anticipated.
4. **Is the iteration order still right?** If this iteration depends on something from a later iteration, reorder.

If you restructure, update the current increment's `_overview.md` and note the change in `.devmeta/project-history.md`. Then continue planning.

### Step 2: Map the Work

Read the iteration plan thoroughly and explore the codebase. Build a complete picture:

1. **List all deliverables** — every feature, component, service, migration, test
2. **Map file footprints** — for each deliverable, which files will be created or modified
3. **Identify shared code** — files or modules that multiple deliverables depend on
4. **Note the test strategy** — surgical test commands per task (from `.devmeta/devmeta.md > Testing` if available)

**Output a work-to-file matrix** (internal analysis):

```
Deliverable A → creates: file1, file2 | modifies: file3
Deliverable B → creates: file4 | modifies: file3, file5
Shared files: file3 (A, B)
```

### Step 3: Find the Cuts (THE CRITICAL STEP)

Graph partitioning — group deliverables into features:

1. **Cluster by shared files.** Deliverables modifying the same files belong together.
2. **Extract shared foundations.** Schemas, types, utilities, shared components → foundation feature.
3. **Check independence.** Can each non-foundation feature run without others? If not, move more to foundation or add minimal cross-feature deps.
4. **Check sizing.** Each feature should fit in ~60-70% of context. Split if too large, merge if trivially small.
5. **Maximize the parallel frontier.** How many features run simultaneously after foundation? Optimize for this.

**General dependency ordering heuristics:**
- Shared types, interfaces, and schemas belong in foundation (they must exist before consumers)
- Config and environment loading belongs in foundation
- Storage/persistence layer belongs in foundation (other layers read/write it)
- Service layers that share a persistence layer can be parallel after foundation
- CLI/API/web layers depend on core services being functional

### Step 4: Create Feature Specs

For each feature, create a spec file:

```
.devmeta/projects/YYYY-MM-DD-<feature-name>/YYYY-MM-DD-<feature-name>-spec.md
```

Each spec contains:
- Scope (what this feature delivers)
- Architecture (files to create/modify)
- Implementation guide (ordered steps)
- Test strategy (surgical commands)
- Open questions (if any)

### Step 5: Create Shared Context Log

```
.devmeta/projects/YYYY-MM-DD-<feature-name>/context-log.md
```

```markdown
# Shared Context Log — <feature-name>

> Feature workers: read this before starting. Append your section when done.
> Captures patterns established, gotchas discovered, and decisions made.

---
```

### Step 6: Create Features and Tasks in tk

**Feature format:**
```bash
tk create "<iteration>: <phase>" -t epic -d "## Scope
<What this feature delivers>

## Spec
\`.devmeta/projects/YYYY-MM-DD-<name>/YYYY-MM-DD-<name>-spec.md\`

## Worker Instructions
- Complete tasks in order
- Read \`.devmeta/projects/YYYY-MM-DD-<name>/context-log.md\` before starting
- Read \`.devmeta/lessons-learned.md\` before starting
- Append learnings to context-log.md when done"
```

**Task format:**
```bash
tk create "<title>" \
  --parent <epic-id> \
  -d "## Objective
<what this step delivers>

## Spec Reference
\`<path>\` — Section: \"<section>\"

## Scope
**Files:** \`path/to/file\` — what changes

## Implementation
1. Step
2. Step

## Tests
Run: \`<surgical test command>\`
Do NOT close until tests pass." \
  --acceptance "<test command> passes"
```

**Cross-feature dependencies (feature level only):**
```bash
tk block <epic-B-first-task-id> <epic-A-last-task-id>
```

### Step 7: Create Iteration Status File

```
Current increment's iterations/iteration-<N>/status.md
```

```markdown
# Iteration <N> Status

**Started:** YYYY-MM-DD
**Status:** In Progress

## Features

| Feature | ID | Tasks | Status | Depends On |
|---------|----|-------|--------|-----------|
| Foundation | <id> | N | Not started | — |
| Feature X | <id> | N | Not started | Foundation |
| Feature Y | <id> | N | Not started | Foundation |

## Feature Independence Map

        [Foundation]
        /          \
  [Feature X]  [Feature Y]   ← parallel

## Notes

<Updated as iteration progresses>
```

### Step 8: Continue Immediately to Execution

**DO NOT pause, summarize, or ask the user anything.** Planning is not a stopping point — it is a waypoint inside `/devmeta:go`'s autonomous loop.

After creating the tick structure, immediately:
1. Run `tk next` to get the first task.
2. Begin executing it.

Do NOT write "here's the plan, shall I proceed?" messages. Do NOT present the feature independence map as a decision point. Do NOT offer options. The tick structure IS the plan; execution starts now.

If the human needs to intervene, they will interrupt. Your job is to keep moving.

## Quality Checklist

- [ ] No file modified by two independent features
- [ ] Shared code in foundation feature
- [ ] Each feature fits in ~60-70% of context
- [ ] Tasks ordered and building on each other within feature
- [ ] Every task has surgical test commands
- [ ] Cross-feature deps are minimal
- [ ] context-log.md created per feature
- [ ] iteration status.md created
- [ ] Parallel frontier is as wide as possible
