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

### 3. Determine the output target

@../../../../conventions/work-items.md

Detect the available system and confirm with the user. This can run in parallel with step 2.

### 4. Identify durable architectural decisions

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

### 5. Draft vertical slices

Break the PRD into **tracer bullet** phases. Each phase is a thin vertical slice that cuts through ALL integration layers end-to-end, NOT a horizontal slice of one layer.

<vertical-slice-rules>
- Each slice delivers a narrow but COMPLETE path through every layer identified in step 2
- A completed slice is demoable or verifiable on its own
- Prefer many thin slices over few thick ones
- Do NOT include specific file names, function names, or implementation details that are likely to change as later phases are built
- DO include durable decisions: route paths, schema shapes, data model names
</vertical-slice-rules>

### 6. Quiz the user

Present the proposed breakdown as a numbered list. For each phase show:

- **Title**: short descriptive name
- **User stories covered**: which user stories from the PRD this addresses

Ask the user:

- Does the granularity feel right? (too coarse / too fine)
- Should any phases be merged or split further?

Iterate until the user approves the breakdown.

### 7. Create the plan

Create work items using the target system from step 3 and the conventions in `work-items.md`.

**Root work item:**
- **Title**: `Plan: <Feature Name>`
- **Body**: Source PRD reference + architectural decisions from step 4 + checklist of all phases

**One child work item per phase:**
- **Title**: `Phase N: <Title>`
- **Body**: "What to build" description (end-to-end behavior, not layer-by-layer) + acceptance criteria as a checklist + user stories covered

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

---

## Phase 2: <Title>

**User stories**: <list from PRD>

### What to build

...

### Acceptance criteria

- [ ] ...

<!-- Repeat for each phase -->
</plan-template>
