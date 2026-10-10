---
name: resolve-architecture-review
description: Walk through architecture-review proposals, designing the interface and writing an RFC for each — one at a time, or with "batch" triage all candidates first, explore the chosen ones together, then review the results. Use after architecture-review to turn its candidates into concrete RFCs.
argument-hint: "[batch] [file]"
---

# Resolve Architecture Review

Walk through architecture improvement candidates. For each candidate the user chooses to explore: frame the problem space, design multiple interfaces via parallel sub-agents, let the user pick, and create an RFC.

**Two modes:**
- **Interactive** (default): one candidate at a time — choose an action, explore, pick, RFC, next.
- **Batch** (`batch` argument): triage every candidate up front, approve all framings at once, explore the chosen candidates together while the user is free, then review the explored candidates one at a time. The user makes the same decisions as in interactive mode, in a different order.

## Critical Behavior Requirements

**YOU MUST FOLLOW THESE RULES:**

### Interactive Mode (default)

1. **MANDATORY STOP**: You MUST use `AskUserQuestion` to present each candidate and wait for the user's choice BEFORE taking ANY action. Do NOT design interfaces or create RFCs autonomously.

2. **ONE AT A TIME**: Process candidates ONE AT A TIME. Never batch multiple candidates together. Never present more than one candidate per response.

3. **NO AUTONOMOUS DESIGN**: Never spawn interface-design sub-agents without explicit user approval via AskUserQuestion response.

### Batch Mode

1. **TRIAGE BEFORE DESIGN**: Every candidate gets an action from the user (Step B1) before any framing or design work starts.

2. **DESIGN ONLY WHAT PASSED THE GATE**: Spawn design sub-agents only for candidates the user marked Explore AND whose framing the user approved at the framing gate (Step B2).

3. **NO STOPS DURING THE WAVE**: Once the framing gate passes, run the exploration wave (Step B3) to completion without asking the user anything.

4. **ONE AT A TIME IN REVIEW**: The review pass (Step B4) presents one explored candidate per response and waits for the user's pick, exactly like interactive mode.

5. **DESIGNS GO TO DISK**: Design and comparison sub-agents write their output to the exploration directory and return only a short summary. Never pull every candidate's full designs into the conversation at once.

### Both Modes

- **STATE TRACKING**: After presenting the summary, write progress state to `.decaf/architecture-improvements/.handle-state.json`. Update it after each candidate changes state. This enables recovery after context compaction.

## Argument Parsing

Parse `$ARGUMENTS`:

**Mode** (positional, optional): `batch` for batch mode; omitted = interactive.

**File** (remaining argument, optional):
- If a file path is provided: Use that specific file
- Otherwise: Use the most recent `.decaf/architecture-improvements/CANDIDATES_*.md` file

Examples: `batch`, `batch .decaf/architecture-improvements/CANDIDATES_2026-10-10_14-30-45.md`.

## Execution Steps

### Step 1: Locate the Candidates File

**If `$ARGUMENTS` specifies a file:**
- Verify the file exists
- If not found, inform the user and exit

**Otherwise, find the latest candidates file:**
```bash
ls .decaf/architecture-improvements/CANDIDATES_*.md 2>/dev/null | sort -r | head -1
```

If no candidates file exists, inform the user:
> No candidates file found. Run `/decaf-plan:architecture-review` first to explore the codebase.

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

Check if `.decaf/architecture-improvements/.handle-state.json` exists:
- If yes and it references the same candidates file, offer to resume from where we left off. Resume in the mode recorded in the state file, regardless of the current argument.
- If no or different file, start fresh

**Resuming batch mode:** continue from the earliest phase any candidate is still in. A candidate recorded as `framed` whose `comparison.md` already exists in its exploration directory finished exploring before the state was written — treat it as `explored`. A `framed` candidate with only some design files gets its wave rerun from scratch.

### Step 4: Present Summary and Initialize State

Show the user the overall summary:

```
## Architecture Improvement Candidates: [filename]

**Project language**: [language]
**Total candidates:** N
**Mode:** [interactive | batch]

[interactive] I'll walk through each candidate ONE AT A TIME. For each one, choose an action:
[batch] First you choose an action for every candidate; then I frame and explore the ones you picked, all together; then we review them one at a time.
- **Explore** — frame the problem, design interfaces, create an RFC
- **Skip**, Dismiss, Defer
```

Write initial state to `.decaf/architecture-improvements/.handle-state.json`:
```json
{
  "candidatesFile": ".decaf/architecture-improvements/CANDIDATES_xxx.md",
  "mode": "interactive|batch",
  "totalCandidates": N,
  "currentIndex": 0,
  "processed": [],
  "actions": { "explored": 0, "skipped": 0, "dismissed": 0, "deferred": 0 },
  "deferSystem": null,
  "outputTarget": null,
  "batch": {}
}
```

`batch` stays empty in interactive mode. In batch mode it maps each candidate number to `{ "phase": "...", "explorationDir": "..." }`; see Step B1.

**Batch mode:** go to [Batch Mode Steps](#batch-mode-steps). **Interactive mode:** continue with Step 5.

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
  1. **Detect tracking system**: Check project CLAUDE.md for references to tracking systems (Nibs, Azure DevOps, GitHub Issues, TODO comments, etc.)
  2. **First defer**: If no system detected and `deferSystem` is null in state file, ask the user which system to use via AskUserQuestion. Store the choice in state file under `"deferSystem"`.
  3. **Subsequent defers**: Reuse `deferSystem` from state file.
  4. **Create work item** with candidate details as the body, following @../../conventions/work-items.md
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
5. Dependency strategy (how deps are handled — see [REFERENCE.md](../architecture-review/REFERENCE.md))
6. Trade-offs

Present designs sequentially, then compare them in prose.

After comparing, give your own recommendation: which design you think is strongest and why. If elements from different designs would combine well, propose a hybrid. Be opinionated — the user wants a strong read, not just a menu.

**5f. User picks an interface:**

⚠️ **STOP HERE AND WAIT FOR USER RESPONSE.** The user picks an interface or accepts the recommendation.

**5g. Determine the output target:**

@../../conventions/work-items.md

Detect the available system and confirm with the user.

**5h. Create refactor RFC:**

Draft the RFC using the issue template in the [reference material](../architecture-review/REFERENCE.md).

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

### Batch Mode Steps

Each candidate's exploration artifacts live in `.decaf/architecture-improvements/explorations/<candidates-file-stem>/<N>/` (the stem is the candidates filename without `.md`), so explorations from different review runs don't collide:

```
<N>/
├── framing.md       # the Step 5d framing, as approved at the gate
├── design-1.md      # one per design sub-agent
├── design-2.md
├── design-3.md
└── comparison.md    # prose comparison + recommendation (+ hybrid, if any)
```

Candidate phases in `state.batch`: `triaged` → `framed` → `explored` → `resolved`.

**B1. Triage every candidate.**

Show all candidates as one compact table: number, cluster name, modules (abbreviated), dependency category. The full details stay in the candidates file; the user can ask for any candidate's details before answering.

Then collect one action per candidate with AskUserQuestion: one question per candidate, up to 4 questions per call, so each call triages 4 candidates. Make as many calls as needed, in candidate order.

```
AskUserQuestion with, per candidate:
- question: "#N [Cluster name] — what should happen with it?"
- header: "#N"
- options:
  - label: "Explore", description: "Frame and design it in the exploration wave"
  - label: "Skip", description: "Leave it, no tracking"
  - label: "Dismiss", description: "Mark as not worth doing"
  - label: "Defer", description: "Create a work item for later"
```

⚠️ **STOP HERE AND WAIT FOR USER RESPONSE** after each call.

Free-form "Other" answers: a reason given there marks the candidate dismissed with that reason; "Stop" ends triage — candidates not yet triaged count as unprocessed, and the session continues with the ones already marked Explore.

After triage:
- Handle Skip, Dismiss and Defer exactly as in Step 5c, and record them in `processed` and `actions`.
- If any candidate is marked Explore, determine the output target now (as in Step 5g) and store it as `outputTarget`, so the review pass doesn't stop for it.
- Record each Explore candidate in `state.batch` as `{ "phase": "triaged", "explorationDir": "<path>" }`.
- If nothing is marked Explore, go to Step 6.

**B2. Framing gate.**

For each Explore candidate, first verify its source files still exist. A candidate whose code is gone or already deepened is reported to the user with the evidence and offered for dismissal at the gate.

Write the Step 5d framing for each remaining candidate to its `framing.md`, then show all framings together, one section per candidate.

```
AskUserQuestion with:
- question: "Launch the exploration wave with these framings?"
- header: "Framings"
- options:
  - label: "Launch", description: "Explore all framed candidates"
  - label: "Revise...", description: "Reframe or drop some first"
```

⚠️ **STOP HERE AND WAIT FOR USER RESPONSE.**

On "Revise...", ask which candidates to reframe or drop and what to change, apply it, show only the revised framings, and ask again. A dropped candidate is recorded as skipped (or dismissed, if the user gives a reason). On "Launch", set every framed candidate's phase to `framed`.

**B3. Exploration wave (no stops).**

Process framed candidates in waves of up to 3 candidates. For each candidate in a wave, spawn its 3+ design sub-agents exactly as in Step 5e (radically different constraint axes, chosen for that candidate), all in one message so the whole wave runs concurrently. Add to each brief:

- Write the full design (the six outputs in Step 5e) to `<explorationDir>/design-<k>.md`.
- Return only a summary of at most 5 lines: the interface's name, its core idea, and its main trade-off.

When a candidate's design sub-agents have all finished, spawn one comparison sub-agent for it. Give it the paths to `framing.md` and the design files, and the instructions from Step 5e for the comparison: compare the designs in prose, give an opinionated recommendation, and propose a hybrid if elements combine well. It writes `<explorationDir>/comparison.md` and returns a one-line recommendation. Then set that candidate's phase to `explored`.

Show one progress line per finished candidate:
```
🔬 #N [Cluster name] explored — recommends [design name]. (X of Y explored)
```

If a design sub-agent fails, rerun it once; if it fails again, proceed with the designs that exist (at least 2) and note the gap in `comparison.md`. With fewer than 2, leave the candidate `framed` and report it in the review pass.

**B4. Review pass (MANDATORY STOP POINT per candidate).**

Walk the `explored` candidates in candidate order, ONE AT A TIME. For each one:

1. Read its `framing.md`, design files and `comparison.md`. Present a short recap of the framing, then the designs sequentially, then the comparison and recommendation.
2. ⚠️ **STOP HERE AND WAIT FOR USER RESPONSE.** The user picks an interface or accepts the recommendation, as in Step 5f. A free-form answer may instead dismiss or defer the candidate — handle it as in Step 5c.
3. Draft and create the RFC as in Step 5h, using the stored `outputTarget`.
4. Set the candidate's phase to `resolved` and record it in `processed` as in Step 5i, then show progress as in Step 5j.

If the user types "Stop", go to Step 6; candidates still `explored` stay listed as remaining, and their exploration files are kept so a resumed session can review them.

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
- [List of skipped or unprocessed candidates, if any — in batch mode, include explored candidates not yet reviewed]

### Deferred Items
- [Deferred items with their work item references]

### Dismissed
- [Dismissed items with reasons, if any]
```

Delete `.decaf/architecture-improvements/.handle-state.json` when complete. If the user stopped with explored candidates not yet reviewed, keep the state file so the session can resume.

### Step 7: Clean Up

Skip this step if the state file was kept for a resumed session.

Ask whether to delete the candidates file:

```
AskUserQuestion with:
- question: "Delete the candidates file ([filename])?"
- header: "Clean up"
- options:
  - label: "Yes", description: "Delete the candidates file"
  - label: "No", description: "Keep it for reference"
```

If the user chooses "Yes", delete the candidates file, and in batch mode also its exploration directory `.decaf/architecture-improvements/explorations/<candidates-file-stem>/`. The RFCs already hold the chosen designs.

## Notes

- For each "Explore" action, verify the relevant source files still exist before framing the problem
- If context is compacted mid-session, read `.decaf/architecture-improvements/.handle-state.json` to resume
- Always use literal Unicode emoji characters, never `:shortcode:` syntax
- The dependency categories and RFC issue template are defined in the [reference material](../architecture-review/REFERENCE.md)
