---
name: handle-architecture-improvements
description: Walk through architecture improvement candidates interactively, designing interfaces and creating RFCs one at a time. Use after running /decaf-planning:improve-codebase-architecture.
argument-hint: "[file]"
---

# Handle Architecture Improvements

Walk through architecture improvement candidates one at a time. For each candidate: frame the problem space, design multiple interfaces via parallel sub-agents, let the user pick, and create an RFC.

## Critical Behavior Requirements

**YOU MUST FOLLOW THESE RULES:**

1. **MANDATORY STOP**: You MUST use `AskUserQuestion` to present each candidate and wait for the user's choice BEFORE taking ANY action. Do NOT design interfaces or create RFCs autonomously.

2. **ONE AT A TIME**: Process candidates ONE AT A TIME. Never batch multiple candidates together. Never present more than one candidate per response.

3. **NO AUTONOMOUS DESIGN**: Never spawn interface-design sub-agents without explicit user approval via AskUserQuestion response.

4. **STATE TRACKING**: After presenting the summary, write progress state to `.architecture-improvements/.handle-state.json`. Update this file after each candidate is processed. This enables recovery after context compaction.

## Argument Parsing

Parse `$ARGUMENTS` to determine the candidates file:

**File** (optional):
- If a file path is provided: Use that specific file
- Otherwise: Use the most recent `.architecture-improvements/CANDIDATES_*.md` file

## Execution Steps

### Step 1: Locate the Candidates File

**If `$ARGUMENTS` specifies a file:**
- Verify the file exists
- If not found, inform the user and exit

**Otherwise, find the latest candidates file:**
```bash
ls .architecture-improvements/CANDIDATES_*.md 2>/dev/null | sort -r | head -1
```

If no candidates file exists, inform the user:
> No candidates file found. Run `/decaf-planning:improve-codebase-architecture` first to explore the codebase.

### Step 2: Parse Candidates

Read the candidates file and extract:
- **Project language** and **idiomatic patterns** from the header
- **All candidates**, identified by headers matching `## #N <name>`

For each candidate, extract:
- Number, cluster name
- Modules involved
- Why coupled
- Dependency category
- Test impact
- Exploration notes

### Step 3: Check for Existing State

Check if `.architecture-improvements/.handle-state.json` exists:
- If yes and it references the same candidates file, offer to resume from where we left off
- If no or different file, start fresh

### Step 4: Present Summary and Initialize State

Show the user the overall summary:

```
## Architecture Improvement Candidates: [filename]

**Project language**: [language]
**Total candidates:** N

I'll walk through each candidate ONE AT A TIME. For each one, choose an action:
- **Explore** — frame the problem, design interfaces, create an RFC
- **Skip**, Dismiss, Defer
```

Write initial state to `.architecture-improvements/.handle-state.json`:
```json
{
  "candidatesFile": ".architecture-improvements/CANDIDATES_xxx.md",
  "totalCandidates": N,
  "currentIndex": 0,
  "processed": [],
  "actions": { "explored": 0, "skipped": 0, "dismissed": 0, "deferred": 0 },
  "deferSystem": null
}
```

### Step 5: Process Each Candidate (MANDATORY STOP POINT)

For each candidate:

**5a. Present the candidate:**
```
## Candidate #N of M: [Cluster name]

**Modules**: `path/to/A`, `path/to/B`, `path/to/C`
**Why coupled**: [explanation]
**Dependency category**: [category]
**Test impact**: [impact]

### Exploration notes
[Additional context from the exploration]
```

**5b. MANDATORY: Present options and wait for user choice.**

Build the full list of options. AskUserQuestion supports max 4 options, so use a two-step flow:

**Step 1 — top-level choice:**
```
AskUserQuestion with:
- question: "What would you like to do with this candidate?"
- header: "Action"
- options:
  - label: "Explore", description: "Frame problem, design interfaces, create RFC"
  - label: "Skip...", description: "Don't explore this now (more options)"
```

⚠️ **STOP HERE AND WAIT FOR USER RESPONSE.**

If user chose "Skip...":
```
AskUserQuestion with:
- question: "How should this candidate be tracked?"
- header: "Skip type"
- options:
  - label: "Skip", description: "Move to next candidate, no tracking"
  - label: "Dismiss", description: "Mark as not worth doing"
  - label: "Defer", description: "Create a work item for later"
```

⚠️ **STOP HERE AND WAIT FOR USER RESPONSE.**

**5c. Handle the response:**

- **Skip**: Record as skipped, proceed to next candidate
- **Dismiss**: Record as dismissed. Store reason if user provides one via the free-form "Other" option. Otherwise record reason as `"dismissed"`.
- **Defer**: Create a work item:
  1. **Detect tracking system**: Check project CLAUDE.md for references to tracking systems (Beans, Azure DevOps, GitHub Issues, TODO comments, etc.)
  2. **First defer**: If no system detected and `deferSystem` is null in state file, ask the user which system to use via AskUserQuestion. Store the choice in state file under `"deferSystem"`.
  3. **Subsequent defers**: Reuse `deferSystem` from state file.
  4. **Create work item** with candidate details as the body, following @../../../../conventions/work-items.md
- **Explore**: Proceed to Step 5d (deep dive on this candidate)
- **Other** (free-form): Handle whatever the user describes. If user types "Stop", jump to Step 6.

**5d. Frame the problem space** (only if user chose "Explore"):

Before spawning sub-agents, write a user-facing explanation:

- The constraints any new interface would need to satisfy
- The dependencies it would need to rely on
- A rough illustrative code sketch to make the constraints concrete — this is not a proposal, just a way to ground the constraints

Show this to the user, then immediately proceed to Step 5e. The user reads and thinks about the problem while the sub-agents work in parallel. If the user objects to the framing, stop and reframe before continuing.

**5e. Design multiple interfaces:**

Spawn 3+ sub-agents in parallel using the Agent tool. Each must produce a **radically different** interface for the deepened module.

Prompt each sub-agent with a separate technical brief (file paths, coupling details, dependency category, what's being hidden, project language). This brief is independent of the user-facing explanation in Step 5d. Choose constraints that create the most interesting tension for this specific problem — don't reuse the same axes every time. Examples of constraint axes:

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
5. Dependency strategy (how deps are handled — see [REFERENCE.md](../improve-codebase-architecture/REFERENCE.md))
6. Trade-offs

Present designs sequentially, then compare them in prose.

After comparing, give your own recommendation: which design you think is strongest and why. If elements from different designs would combine well, propose a hybrid. Be opinionated — the user wants a strong read, not just a menu.

**5f. User picks an interface:**

⚠️ **STOP HERE AND WAIT FOR USER RESPONSE.** The user picks an interface or accepts the recommendation.

**5g. Determine the output target:**

@../../../../conventions/work-items.md

Detect the available system and confirm with the user.

**5h. Create refactor RFC:**

Draft the RFC using the issue template in the [reference material](../improve-codebase-architecture/REFERENCE.md).

**Work item content:**
- **Title**: descriptive name for the refactor (e.g., "Deepen PaymentProcessing module")
- **Body**: the RFC content — problem, proposed interface, dependency strategy, testing strategy, implementation recommendations

Show the draft to the user for review, then create using the conventions in `work-items.md`.

For markdown output, write to `./plans/<feature-name>-rfc.md`.

**5i. Update state file** after each candidate:
```json
{
  "currentIndex": N,
  "processed": [..., { "candidate": N, "action": "explored|skipped|dismissed|deferred", "rfc": "<work-item-ref or file path if explored>" }],
  "actions": { "explored": X, "skipped": Y, "dismissed": D, "deferred": F }
}
```
For dismissed candidates, include reason: `{ "candidate": N, "action": "dismissed", "reason": "..." }`
For deferred candidates, include work item reference: `{ "candidate": N, "action": "deferred", "workItem": "..." }`

**5j. Show progress:**
```
✅ Candidate #N addressed. (X of M remaining)
```

**5k. Return to 5a for next candidate.** Do NOT batch — present one candidate, wait, process, repeat.

### Step 6: Session Summary

When all candidates are processed or the user stops:

```
## Architecture Improvement Session Complete

| Action | Count |
|--------|-------|
| Explored (RFC created) | X |
| Skipped | X |
| Dismissed | X |
| Deferred | X |

### RFCs Created
- [List of RFCs with their work item references or file paths]

### Remaining Candidates
- [List of skipped or unprocessed candidates, if any]

### Deferred Items
- [Deferred items with their work item references]

### Dismissed
- [Dismissed items with reasons, if any]
```

Delete `.architecture-improvements/.handle-state.json` when complete.

### Step 7: Clean Up

Ask whether to delete the candidates file:

```
AskUserQuestion with:
- question: "Delete the candidates file ([filename])?"
- header: "Clean up"
- options:
  - label: "Yes", description: "Delete the candidates file"
  - label: "No", description: "Keep it for reference"
```

If the user chooses "Yes", delete the candidates file.

## Notes

- For each "Explore" action, verify the relevant source files still exist before framing the problem
- If context is compacted mid-session, read `.architecture-improvements/.handle-state.json` to resume
- Always use literal Unicode emoji characters, never `:shortcode:` syntax
- The dependency categories and RFC issue template are defined in the [reference material](../improve-codebase-architecture/REFERENCE.md)
