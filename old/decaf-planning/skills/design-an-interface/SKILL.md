---
name: design-an-interface
description: Generate multiple radically different interface designs for a module using parallel sub-agents. Use when user wants to design an API, explore interface options, compare module shapes, or mentions "design it twice".
---

# Design an Interface

Based on "Design It Twice" from "A Philosophy of Software Design": your first idea is unlikely to be the best. Generate multiple radically different designs, then compare.

## Workflow

### 1. Gather Requirements

Before designing, understand:

- [ ] What problem does this module solve?
- [ ] Who are the callers? (other modules, external users, tests)
- [ ] What are the key operations?
- [ ] Any constraints? (performance, compatibility, existing patterns)
- [ ] What should be hidden inside vs exposed?

Ask: "What does this module need to do? Who will use it?"

### 2. Explore the Codebase

If this module lives in an existing project, explore the codebase to understand:

- Existing interface patterns and conventions
- Similar modules and how they're shaped
- The project language and its idiomatic interface style

The designs produced must be consistent with the project's language. Interface shape is language-dependent — a Go interface with 1-2 methods is idiomatic, a C# interface with a richer contract is normal, Rust traits have associated types and lifetime considerations. Express all designs in the project's language.

### 3. Generate Designs (Parallel Sub-Agents)

Spawn sub-agents simultaneously using the **Agent tool**. Default to 3 agents; the user can request more or fewer.

Each agent must produce a **radically different** approach. Choose constraints that are most revealing for the specific module being designed — don't reuse the same axes every time. Examples of constraint axes (pick the ones that create the most interesting tension for this problem):

- Minimize method count (1-3 methods max)
- Maximize flexibility / support many use cases
- Optimize for the most common case
- Take inspiration from a specific paradigm or library
- Prioritize composability
- Prioritize safety / make misuse impossible
- Minimize ceremony for the caller

```
Prompt template for each sub-agent:

Design an interface for: [module description]

Requirements: [gathered requirements]
Language: [project language]
Existing patterns: [relevant patterns from codebase exploration]

Design constraint: [one specific constraint chosen for this agent]

Output format:
1. Interface signature (types/methods in the project language)
2. Usage example (how caller uses it)
3. What this design hides internally
4. Brief sketch of internal structure (enough to evaluate feasibility, not a full implementation)
5. Trade-offs of this approach
```

### 4. Present Designs

Show each design with:

1. **Interface signature** - types, methods, params
2. **Usage examples** - how callers actually use it in practice
3. **What it hides** - complexity kept internal
4. **Internal sketch** - enough to judge if the interface can be implemented efficiently

Present designs sequentially so user can absorb each approach before comparison.

### 5. Compare Designs

After showing all designs, compare them on:

- **Interface simplicity**: fewer methods, simpler params
- **General-purpose vs specialized**: flexibility vs focus
- **Implementation efficiency**: does shape allow efficient internals?
- **Depth**: small interface hiding significant complexity (good) vs large interface with thin implementation (bad)
- **Ease of correct use** vs **ease of misuse**

Discuss trade-offs in prose, not tables. Highlight where designs diverge most.

### 6. Synthesize

Often the best design combines insights from multiple options. Ask:

- "Which design best fits your primary use case?"
- "Any elements from other designs worth incorporating?"

Once the user has chosen, offer to write the final interface design to a file for reference.

## Evaluation Criteria

From "A Philosophy of Software Design":

**Interface simplicity**: Fewer methods, simpler params = easier to learn and use correctly.

**General-purpose**: Can handle future use cases without changes. But beware over-generalization.

**Implementation efficiency**: Does interface shape allow efficient implementation? Or force awkward internals?

**Depth**: Small interface hiding significant complexity = deep module (good). Large interface with thin implementation = shallow module (avoid).

## Anti-Patterns

- Don't let sub-agents produce similar designs - enforce radical difference
- Don't skip comparison - the value is in contrast
- Don't fully implement - sketch internals enough to evaluate feasibility, but this is about interface shape
- Don't evaluate based on implementation effort
