---
name: improve-codebase-architecture
description: Explore a codebase to find opportunities for architectural improvement, focusing on making the codebase more testable by deepening shallow modules. Use when user wants to improve architecture, find refactoring opportunities, consolidate tightly-coupled modules, or make a codebase more AI-navigable.
---

# Improve Codebase Architecture

Explore a codebase like an AI would, surface architectural friction, discover opportunities for improving testability, and propose module-deepening refactors.

A **deep module** (John Ousterhout, "A Philosophy of Software Design") has a small interface hiding a large implementation. Deep modules are more testable, more AI-navigable, and let you test at the boundary instead of inside.

## Process

### 1. Explore the codebase

Use the Agent tool with subagent_type=Explore to navigate the codebase naturally. Do NOT follow rigid heuristics — explore organically and note where you experience friction:

- Where does understanding one concept require bouncing between many small files?
- Where are modules so shallow that the interface is nearly as complex as the implementation?
- Where have pure functions been extracted just for testability, but the real bugs hide in how they're called?
- Where do tightly-coupled modules create integration risk in the seams between them?
- Which parts of the codebase are untested, or hard to test?

The friction you encounter IS the signal.

Also identify the project language and its idiomatic interface patterns — designs produced later must be expressed in this language.

### 2. Present candidates

Present a numbered list of deepening opportunities. For each candidate, show:

- **Cluster**: Which modules/concepts are involved
- **Why they're coupled**: Shared types, call patterns, co-ownership of a concept
- **Dependency category**: See [REFERENCE.md](REFERENCE.md) for the four categories
- **Test impact**: What existing tests would be replaced by boundary tests

Do NOT propose interfaces yet. Ask the user: "Which of these would you like to explore?"

### 3. User picks a candidate

Wait for the user to choose before proceeding.

### 4. Frame the problem space

Before spawning sub-agents, write a user-facing explanation of the problem space for the chosen candidate:

- The constraints any new interface would need to satisfy
- The dependencies it would need to rely on
- A rough illustrative code sketch to make the constraints concrete — this is not a proposal, just a way to ground the constraints

Show this to the user, then immediately proceed to Step 5. The user reads and thinks about the problem while the sub-agents work in parallel. If the user objects to the framing, stop and reframe before continuing.

### 5. Design multiple interfaces

Spawn 3+ sub-agents in parallel using the Agent tool. Each must produce a **radically different** interface for the deepened module.

Prompt each sub-agent with a separate technical brief (file paths, coupling details, dependency category, what's being hidden, project language). This brief is independent of the user-facing explanation in Step 4. Choose constraints that create the most interesting tension for this specific problem — don't reuse the same axes every time. Examples of constraint axes:

- Minimize the interface — aim for 1-3 entry points max
- Maximize flexibility — support many use cases and extension
- Optimize for the most common caller — make the default case trivial
- Design around the ports & adapters pattern for cross-boundary dependencies
- Prioritize composability
- Prioritize safety — make misuse impossible

Each sub-agent outputs:

1. Interface signature (types, methods, params — in the project language)
2. Usage example showing how callers use it
3. What complexity it hides internally
4. Brief sketch of internal structure (enough to evaluate feasibility)
5. Dependency strategy (how deps are handled — see [REFERENCE.md](REFERENCE.md))
6. Trade-offs

Present designs sequentially, then compare them in prose.

After comparing, give your own recommendation: which design you think is strongest and why. If elements from different designs would combine well, propose a hybrid. Be opinionated — the user wants a strong read, not just a menu.

### 6. User picks an interface (or accepts recommendation)

Wait for the user to choose before proceeding.

### 7. Determine the output target

@../../../../conventions/work-items.md

Detect the available system and confirm with the user.

### 8. Create refactor RFC

Draft the RFC using the issue template in [REFERENCE.md](REFERENCE.md).

**Work item content:**
- **Title**: descriptive name for the refactor (e.g., "Deepen PaymentProcessing module")
- **Body**: the RFC content from the REFERENCE.md template — problem, proposed interface, dependency strategy, testing strategy, implementation recommendations

Show the draft to the user for review, then create using the conventions in `work-items.md`.

For markdown output, write to `./plans/<feature-name>-rfc.md`.
