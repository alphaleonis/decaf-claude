---
name: breakdown-phase
description: Break a plan phase (epic) into implementable features with acceptance criteria. Use when user wants to decompose a phase before starting implementation, break an epic into features, or detail a vertical slice into work items.
argument-hint: "[phase reference or number]"
---

# Breakdown Phase

Break a single phase from a plan into implementable features. Each feature is an independently buildable and reviewable chunk of work. Does NOT break features further into tasks — that happens at implementation time.

## Process

### 1. Identify the phase

Locate the phase to break down. The user may provide:

- A phase number or title from a plan already in conversation context
- A path to a plan file (e.g., `./plans/feature-name.md`)
- A work item ID (beans, GitHub issue, Azure DevOps work item)

If the phase is not clear, ask the user to specify which phase they want to break down.

Also locate the **parent plan** (root work item or plan file) to pull in:
- Architectural decisions that constrain the breakdown
- The full phase list, so you understand what comes before and after this phase

### 2. Explore the codebase

Explore the codebase to understand its **current state** — not the state when the plan was created. Earlier phases may have already been implemented, changing the landscape.

Focus on:
- Modules and boundaries relevant to this phase
- Code that already exists from prior phases
- Test patterns and infrastructure available
- Integration points this phase must connect to

Skip this step if the codebase was already explored in this conversation and no implementation has happened since.

### 3. Draft features

Break the phase into features. Each feature should be:

- **Independently implementable** — can be built without the other features in this phase being complete (though ordering preferences are fine)
- **Independently reviewable** — a PR for this feature makes sense on its own
- **Vertically sliced where possible** — prefer thin end-to-end slices over horizontal layers, but pragmatism wins over dogma (a pure data-model feature is fine if the phase demands it)

For each feature, draft:

- **Title**: Short, descriptive
- **Description**: What to build — describe the end-to-end behavior, not implementation steps
- **Acceptance criteria**: Checkboxes that define "done" for this feature
- **Dependencies**: Other features in this phase that should be built first (if any)

<feature-guidelines>
- Aim for features that are each roughly a focused PR (1-3 hours of implementation work, not days)
- If a feature feels too large, split it further. If it feels trivial, merge it into a related feature
- Do NOT include specific file names, function names, or implementation details — those belong at implementation time
- DO reference architectural decisions from the parent plan where relevant
- DO note which acceptance criteria from the parent phase each feature satisfies
</feature-guidelines>

### 4. Show the breakdown to the user

Present the proposed features as a numbered list. For each feature show:

- **Title**
- **Description** (brief)
- **Dependencies** on other features in the list (if any)

Ask the user:
- Does the granularity feel right?
- Should any features be merged or split?
- Are there missing features that the phase requires?

Iterate until the user approves.

### 5. Determine the output target

@../../../../conventions/work-items.md

Detect the available system and confirm with the user. If the parent phase already exists as a work item, use the same system.

### 6. Create work items

Create one work item per feature as **children of the phase**.

**Work item type mapping:**

| System | Phase type | Feature type |
|--------|-----------|--------------|
| Beans | `epic` | `feature` |
| GitHub Issues | Issue (sub-issue of plan) | Sub-issue of phase |
| Azure DevOps | Epic or Feature | Feature or User Story |
| Markdown | Section in plan file | Subsection under phase |

**Each feature work item contains:**
- **Title**: `<Feature title>`
- **Body**: Description + acceptance criteria as checklist + dependencies (referencing sibling work item IDs where applicable)

**For markdown output**, append features under the phase section in the plan file:

<markdown-template>
### Feature N.1: <Title>

**Dependencies**: None | Feature N.2, Feature N.3

<Description of what to build — end-to-end behavior.>

#### Acceptance criteria

- [ ] Criterion 1
- [ ] Criterion 2
- [ ] Criterion 3
</markdown-template>

### 7. Update the parent phase

After creating features, update the parent phase work item (or plan section) to include a checklist of the created features with links/IDs, so progress can be tracked at the phase level.

## Example Usage

```
/decaf-experimental:breakdown-phase 2                    # Break down phase 2 from plan in context
/decaf-experimental:breakdown-phase ./plans/auth.md#3    # Phase 3 from a plan file
/decaf-experimental:breakdown-phase BEAN-42              # Break down a beans epic
```
