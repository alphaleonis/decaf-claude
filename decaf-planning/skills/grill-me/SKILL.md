---
name: grill-me
description: Interview the user relentlessly about a plan or design until reaching shared understanding, resolving each branch of the decision tree. Use when user wants to stress-test a plan, get grilled on their design, or mentions "grill me".
---

Interview the user relentlessly about every aspect of their plan until reaching a shared understanding. Walk down each branch of the design tree, resolving dependencies between decisions one-by-one.

If a question can be answered by exploring the codebase, explore the codebase instead.

## Before starting

If no plan or design is present in the conversation, stop and ask the user to provide one before proceeding.

## Phase 1: Scope Assessment

Before diving deep, map the full design space with a breadth-first pass.

**1a. Identify areas.** Read the plan and identify all major areas, subsystems, or concerns that need decisions. An "area" is a cluster of related decisions — e.g., "auth model", "data migration", "API surface", "UI flow", "error handling", "deployment".

**1b. Present the map.** Show the user the areas you've identified:

```
## Design Space

I see N major areas to explore:

1. **Area name** — brief description of what needs to be decided
2. **Area name** — brief description
...
```

Ask 1-2 clarifying questions per area if needed to confirm you've understood the scope correctly. Add any areas the user identifies that you missed.

**1c. Assess scope.** If there are **5 or more areas**, acknowledge the scope is large and ask the user how to proceed:

```
AskUserQuestion with:
- question: "This is a broad design space. How would you like to proceed?"
- options:
  - label: "Drill into all", description: "Work through every area depth-first (long session)"
  - label: "Prioritize", description: "Pick the highest-risk areas to explore now, defer the rest"
  - label: "Split sessions", description: "Group areas and tackle each group in a separate session"
```

If the user chooses **"Prioritize"**, ask them which areas to focus on. Mark the rest as deferred in the progress file.

If the user chooses **"Split sessions"**, ask how to group the areas, then proceed with the first group only. Record the other groups in the progress file as planned follow-up sessions.

If fewer than 5 areas, proceed directly — no need to ask.

## Phase 2: Depth-First Exploration

For each area (in the order agreed with the user, or by priority if not specified):

1. Announce which area you're starting: `### Exploring: [Area Name]`
2. Exhaust all branches within the area depth-first before moving on
3. Use judgement — sometimes a lateral question is needed to establish context before diving deeper, but always return to finish the current branch
4. When the area is fully resolved, update the progress file and move to the next area

## Tracking Progress

Maintain a running summary in a local file (`./.grill-me/<short-descriptive-name>.md`) with this structure:

```markdown
# Grill Session: <topic>

## Areas

| # | Area | Status | Branches |
|---|------|--------|----------|
| 1 | Auth model | ✅ Done | 4/4 resolved |
| 2 | API surface | 🔄 In progress | 2/5 resolved |
| 3 | Data migration | ⏳ Pending | 0/3 resolved |
| 4 | Deployment | 📋 Deferred | — |

## Resolved Decisions

### 1. Auth model

- **1.1 Token format**: JWT with short-lived access tokens (15min) + refresh tokens
- **1.2 Session storage**: Redis, not database — latency matters more than durability here
- ...

### 2. API surface

- **2.1 Versioning**: URL path prefix (/v1/, /v2/)
- ...

## Open Branches

### 2. API surface
- 2.3 Pagination strategy — cursor vs offset?
- 2.4 Rate limiting approach
- 2.5 Error response format

### 3. Data migration
- 3.1 Migration strategy — big bang vs incremental?
- 3.2 Rollback approach
- 3.3 Data validation during migration

## Deferred Areas

### 4. Deployment
- Reason: Lower risk, can be decided after API surface is stable
```

Update this file as decisions are reached. Before asking the next question, check the file to avoid revisiting settled topics.

## When to stop

After each **area** is fully resolved, ask the user whether to continue to the next area or wrap up.

When all areas are resolved (or the user chooses to wrap up with deferred areas remaining):

1. Present the final summary of all resolved decisions
2. List any deferred areas with their reasons
3. Ask the user whether to create follow-up work items for deferred areas:

```
AskUserQuestion with:
- question: "Create follow-up work items for the N deferred areas?"
- options:
  - label: "Yes", description: "Create work items for deferred areas"
  - label: "No", description: "Just keep them noted in the session file"
```

If the user chooses **"Yes"**:

@../../conventions/work-items.md

Detect the available tracking system and create one work item per deferred area, with the area description, known context, and open questions as the body. Title format: `Investigate: <area name>`.

4. Confirm with the user that the session file is complete and accurate.
