---
name: prd-to-plan
description: Turn a PRD into a multi-phase implementation plan using tracer-bullet vertical slices, then create work items (GitHub Issues, Azure DevOps, Beans) or save as a local Markdown file. Use when user wants to break down a PRD, create an implementation plan, plan phases from a PRD, or mentions "tracer bullets".
---

# PRD to Plan

Break a PRD into a phased implementation plan using vertical slices (tracer bullets). Output work items to a tracking system or fall back to a Markdown file.

## Process

### 1. Confirm the PRD is in context

The PRD should already be in the conversation. If it isn't, ask the user to paste it or point you to the file.

### 2. Explore the codebase

If you have not already explored the codebase, do so to understand:

- Current architecture and module boundaries
- Tech stack and project language
- Existing test patterns and infrastructure
- Deployment shape (what layers a vertical slice must cut through)

### 3. Check for deviation rules

Check the project's CLAUDE.md for a "When Executing Plans" section (or similar deviation rules). If none exists, offer to add one. This defines what the AI can decide autonomously vs. what requires human input during plan execution.

<deviation-rules-template>
## When Executing Plans

When working from a plan or work item:

- **Auto-fix without asking:** bug fixes, type errors, missing imports, broken references, missing null checks, obvious error handling gaps
- **Auto-add without asking:** necessary validation, missing error handling on external calls, required interface implementations
- **Ask before doing:** new dependencies/packages, schema or data model changes, architectural decisions not covered in the plan, changes to public APIs or contracts, anything that affects other projects or services
- **Never without explicit approval:** delete or restructure files not mentioned in the plan, change build/CI configuration, modify security boundaries
</deviation-rules-template>

Present the template to the user and let them adjust the boundaries before adding it. If the user declines, proceed without it.

This step can run in parallel with steps 2 and 4.

### 4. Determine the output target

@../../../../conventions/work-items.md

Detect the available system and confirm with the user. This can run in parallel with steps 2 and 3.

### 5. Identify durable architectural decisions

Before slicing, identify high-level decisions that are unlikely to change throughout implementation. Examples (adapt to the project type):

- Route structures / URL patterns (web apps)
- Database schema shape
- Key data models / domain types
- Authentication / authorization approach
- Third-party service boundaries
- CLI command structure (CLI tools)
- Public API surface (libraries)

Express these using the project's language idioms (e.g., structs for Go, records/classes for C#, structs/enums for Rust).

These go in the root work item body (or plan header for markdown) so every phase can reference them.

### 6. Draft vertical slices

Break the PRD into **tracer bullet** phases. Each phase is a thin vertical slice that cuts through ALL integration layers end-to-end, NOT a horizontal slice of one layer.

<vertical-slice-rules>
- Each slice delivers a narrow but COMPLETE path through every layer identified in the codebase exploration
- A completed slice is demoable or verifiable on its own
- Prefer many thin slices over few thick ones
- Do NOT include specific file names, function names, or implementation details that are likely to change as later phases are built
- DO include durable decisions: route paths, schema shapes, data model names
- DO include scope boundaries per phase (see below)
</vertical-slice-rules>

**Scope boundaries per phase:** Each phase should include a brief "Touches" and "Off limits" section. This prevents scope creep during implementation — Claude won't "helpfully" refactor adjacent code or add features that belong to a different phase.

- **Touches**: Areas of the codebase this phase modifies (modules, layers, subsystems — not specific file names)
- **Off limits**: Areas that are explicitly out of scope for this phase, even if they seem related

### 7. Quiz the user

Present the proposed breakdown as a numbered list. For each phase show:

- **Title**: short descriptive name
- **User stories covered**: which user stories from the PRD this addresses

Ask the user:

- Does the granularity feel right? (too coarse / too fine)
- Should any phases be merged or split further?

Iterate until the user approves the breakdown.

### 8. Create the plan

Create work items using the target system from step 4 and the conventions in `work-items.md`.

**Root work item:**
- **Title**: `Plan: <Feature Name>`
- **Body**: Source PRD reference + architectural decisions from step 5 + checklist of all phases

**One child work item per phase:**
- **Title**: `Phase N: <Title>`
- **Body**: "What to build" description (end-to-end behavior, not layer-by-layer) + acceptance criteria as a checklist + user stories covered + scope boundaries (touches / off limits)

For markdown output, use the template below instead.

<plan-template>
# Plan: <Feature Name>

> Source PRD: <brief identifier or link>

## Architectural decisions

Durable decisions that apply across all phases:

- **Routes**: ...
- **Schema**: ...
- **Key models**: ...
- (add/remove sections as appropriate for the project type)

---

## Phase 1: <Title>

**User stories**: <list from PRD>

### What to build

A concise description of this vertical slice. Describe the end-to-end behavior, not layer-by-layer implementation.

### Acceptance criteria

- [ ] Criterion 1
- [ ] Criterion 2
- [ ] Criterion 3

### Scope boundaries

**Touches**: <modules, layers, or subsystems this phase modifies>
**Off limits**: <areas explicitly out of scope, even if related>

---

## Phase 2: <Title>

**User stories**: <list from PRD>

### What to build

...

### Acceptance criteria

- [ ] ...

### Scope boundaries

**Touches**: ...
**Off limits**: ...

<!-- Repeat for each phase -->
</plan-template>
