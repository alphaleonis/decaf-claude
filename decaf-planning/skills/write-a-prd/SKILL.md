---
name: write-a-prd
description: Create a PRD through user interview, codebase exploration, and structured requirements capture. Use when user wants to write a PRD, create a product requirements document, or plan a new feature.
---

# Write a PRD

Create a Product Requirements Document through user interview and codebase exploration. The PRD captures *what* to build and *why* — implementation planning (modules, phases, vertical slices) is handled separately by `/decaf-planning:prd-to-plan`.

## Process

### 1. Gather the problem description

Ask the user for a detailed description of the problem they want to solve and any potential ideas for solutions.

Skip this step if the user already provided a description in their prompt.

### 2. Explore the codebase

If the codebase has not already been explored in this conversation, explore it to understand the current state — existing architecture, relevant modules, tech stack, and anything related to the problem being described.

Skip this step if the codebase is already in context from prior exploration.

### 3. Interview the user

Use `/decaf-planning:grill-me` to interview the user about every aspect of the problem and proposed solution until reaching a shared understanding.

Skip this step if the user was already grilled on this topic in the current conversation (e.g., a prior `/decaf-planning:grill-me` session covered the same ground). Use judgement — if the grill-me session was on a related but different aspect, a brief follow-up interview may still be needed to fill gaps specific to the PRD.

### 4. Determine the output target

@../../../../conventions/work-items.md

Detect the available system and confirm with the user.

### 5. Write the PRD

Draft the PRD using the template below. Adapt the sections to the project type — not all projects have routes, schemas, or APIs.

Show the draft to the user for review before creating the work item. Iterate if the user has feedback.

Create the work item using the conventions in `work-items.md`:
- **Title**: `PRD: <Feature Name>`
- **Body**: the PRD content from the template below

For markdown output, write to `./plans/<feature-name>-prd.md`.

<prd-template>

## Problem Statement

The problem that the user is facing, from the user's perspective.

## Solution

The solution to the problem, from the user's perspective.

## User Stories

A numbered list of user stories. Cover all meaningful user-facing behaviors, but stay focused — don't enumerate trivial edge cases. Each user story should be in the format of:

1. As an <actor>, I want a <feature>, so that <benefit>

<user-story-example>
1. As a mobile bank customer, I want to see balance on my accounts, so that I can make better informed decisions about my spending
</user-story-example>

## Implementation Decisions

Key decisions that constrain or guide implementation. Adapt to the project type — examples include:

- Architectural decisions and trade-offs
- Schema changes or data model shapes
- API contracts or CLI command structure
- Third-party service boundaries
- Authentication / authorization approach
- Performance or compatibility constraints

Do NOT include specific file paths or code snippets — they become outdated quickly. Focus on durable decisions that will still be relevant when implementation begins.

## Testing Decisions

- Which behaviors should be tested (priorities agreed with the user)
- What constitutes a good test for this feature (test external behavior, not implementation details)
- Prior art for tests (similar types of tests already in the codebase)

## Out of Scope

Things explicitly excluded from this PRD.

## Further Notes

Any additional context, open questions, or follow-up items.

</prd-template>
