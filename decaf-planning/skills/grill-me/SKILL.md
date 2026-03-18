---
name: grill-me
description: Interview the user relentlessly about a plan or design until reaching shared understanding, resolving each branch of the decision tree. Use when user wants to stress-test a plan, get grilled on their design, or mentions "grill me".
---

Interview the user relentlessly about every aspect of their plan until reaching a shared understanding. Walk down each branch of the design tree, resolving dependencies between decisions one-by-one.

If a question can be answered by exploring the codebase, explore the codebase instead.

## Before starting

If no plan or design is present in the conversation, stop and ask the user to provide one before proceeding.

## Approach

Prefer depth-first: exhaust a branch before moving to the next. Use judgement — sometimes a lateral question is needed to establish context before diving deeper, but always return to finish the current branch.

## Tracking progress

Maintain a running summary in a local file (`./.grill-me/<short-descriptive-name>.md`) with two sections:

- **Resolved** — decisions that have been settled, with the conclusion
- **Open** — branches still to explore

Update this file as decisions are reached. Before asking the next question, check the file to avoid revisiting settled topics.

## When to stop

After each branch is resolved, explicitly ask the user whether to continue to the next open branch or wrap up. When no open branches remain, present the final summary of all resolved decisions and confirm with the user.
