---
name: research
description: Explore an unfamiliar problem space through multi-phase parallel research with synthesis. Use before writing a PRD when the domain, technology, or trade-offs are not well understood. Produces a structured research document.
argument-hint: "<topic or problem description>"
---

# Research With Synthesis

Explore an unfamiliar problem space through parallel research agents, gap analysis, and synthesis. Produces a structured research document that feeds into the planning pipeline (`grill-me` → `write-a-prd` → `prd-to-plan`).

Use this skill when:
- The problem space is unfamiliar — you don't know what you don't know
- There are multiple viable approaches and you need to compare them
- The topic involves technologies, patterns, or trade-offs you haven't evaluated

Skip this skill when:
- You already understand the problem well enough to write a PRD
- The work is on a well-understood codebase with a clear path forward

## Process

### 1. Define research axes

Based on the topic, determine 3-4 research angles. These are NOT fixed roles — they adapt to the problem.

Examples:

- "Should we add real-time sync to Vestige?"
  → existing solutions, conflict resolution strategies, transport protocols, storage implications

- "Evaluate GraphQL vs REST for our new API"
  → ecosystem maturity, code generation tooling, caching strategies, team familiarity

- "Migrate from SQLite to PostgreSQL"
  → migration tooling, query compatibility, deployment complexity, performance characteristics for our access patterns

Present the proposed axes to the user. Let them adjust, add, or remove before proceeding.

### 2. Phase 1 — Broad survey

Launch one subagent per axis **in parallel in a single message**. Each agent receives:

- The topic description
- Their specific research angle
- Codebase context if relevant (explore the codebase first, or pass key context from the conversation)
- Instructions to return structured findings

**Agent prompt template:**

```
Research the following topic from the perspective of your assigned angle.

## Topic
<topic description>

## Your Research Angle
<specific angle for this agent>

## Codebase Context
<relevant context about the project, tech stack, constraints>

## Output Format

Return your findings in this structure:

### Key Facts
What you found, with specifics. Cite sources where possible.

### Options Identified
Viable approaches within your angle. For each option: brief description, pros, cons.

### Risks
Downsides, gotchas, known problems.

### Open Questions
Things you couldn't fully answer or that need deeper investigation.

### Cross-References
Flag connections to other research angles:
- "This finding likely affects [other angle] because..."
- "The [other angle] researcher should also consider..."

Be thorough but concise. Focus on findings that would inform a decision, not exhaustive background.
```

The cross-references instruction is key — it primes each researcher to flag connections to other axes even though they can't communicate directly. The coordinator uses these in the gap analysis.

### 3. Gap analysis

After all Phase 1 agents complete, read all results and identify:

- **Contradictions**: Agent A says library X supports feature Y; Agent B says it doesn't
- **Gaps**: Nobody investigated topic Z, but multiple agents flagged it in cross-references
- **Cross-cutting findings**: A's finding about constraint P changes the viability of B's recommendation Q
- **Unresolved questions**: Things agents explicitly flagged as needing more investigation

Present the gap analysis to the user. Ask: should we do a follow-up phase, or is this sufficient?

### 4. Phase 2 — Targeted follow-up (optional)

If the user wants deeper investigation:

- Launch targeted subagents for each gap or contradiction
- Each gets the **full Phase 1 findings** plus their specific investigation target
- Fewer agents, more focused than Phase 1
- These agents may use web search or documentation lookup for specific questions

After Phase 2 completes, present new findings to the user. Do NOT offer a Phase 3 — two rounds is the limit. If significant unknowns remain, note them in the synthesis as open risks.

### 5. Synthesis

Write a research document covering:

```markdown
# Research: <Topic>

**Date**: <YYYY-MM-DD>
**Research axes**: <list of angles investigated>
**Phases**: <1 or 2>

## Landscape Summary

What we now understand about the problem space. Establish the context
and constraints that shape the available options.

## Options

### Option A: <Name>

<Description>

**Pros:**
- ...

**Cons:**
- ...

**Fit for our case:** <brief assessment of how well this fits the specific project>

### Option B: <Name>
...

## Recommendation

The strongest path forward, with reasoning. Reference specific findings
that support this recommendation. If no single option is clearly best,
say so and explain what would tip the decision.

## Risks and Unknowns

What we still don't know, and whether it matters for the decision.
Distinguish between:
- **Risks we can mitigate** — known problems with known solutions
- **Unknowns that may not matter** — gaps in our knowledge that are unlikely to affect the outcome
- **Unknowns that could change the decision** — things that, if answered differently, would alter the recommendation

## Sources and References

Links, documentation, libraries, tools, and other resources discovered
during research. Group by relevance.
```

### 6. Output

@../../../../conventions/work-items.md

Detect the available system and confirm with the user.

- **Work item**: Create with title `Research: <Topic>` and the synthesis document as the body
- **Markdown fallback**: Write to `./plans/<topic-slug>-research.md`

After saving, inform the user:
```
Research complete: <path or work item reference>
Next step: /decaf-planning:grill-me or /decaf-planning:write-a-prd
```

## Example Usage

```
/decaf-planning:research Should we add real-time sync to Vestige?
/decaf-planning:research Evaluate options for replacing our REST API with GraphQL
/decaf-planning:research Migration path from SQLite to PostgreSQL for our access patterns
```
