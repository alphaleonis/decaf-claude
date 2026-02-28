---
name: code-review
description: Run parallel code review agents and consolidate findings into a unified report
argument-hint: "[quick|std|max] [--spec <path>] [path] [instructions]"
---

# Code Review

This command orchestrates code review agents and consolidates their findings into a unified, deduplicated report.

## Argument Parsing

Parse `$ARGUMENTS` to determine:
1. **Mode**: `quick`, `max`, or `std` (default when no mode keyword given)
2. **Spec path**: `--spec <path>` — a specification or plan document to verify compliance against
3. **Scope**: Specific file/directory path, or all uncommitted changes
4. **Instructions**: Any additional review instructions

| Mode | Agents | Use Case |
|------|--------|----------|
| `quick` | quick + broad (2) | Fast feedback from two generalists |
| `std` (default) | quick + broad + judged specialists (3-7) | Balanced: generalists + specialists selected by triage |
| `max` | All applicable agents (5-7) | Maximum coverage, all agents that apply |

## Execution Steps

### Step 1: Gather Context

Determine what code to review:
- If a specific path is provided: Review that file or directory
- Otherwise: Get uncommitted changes via `git diff HEAD` and `git diff --cached`

For file/directory scope, use:
```bash
git diff HEAD -- <path>
```

If no uncommitted changes exist and no path specified, check the last commit:
```bash
git diff HEAD~1..HEAD
```

### Step 2: Select Agents by Mode

#### `quick` mode

Always exactly 2 agents — no triage needed:
- `decaf:code-reviewer-quick`
- `decaf:code-reviewer-broad`

#### `max` mode

Include all agents, subject to guardrails:
- `decaf:code-reviewer-quick` — always
- `decaf:code-reviewer-broad` — always
- `decaf:code-reviewer-knowledge` — always
- `decaf:design-reviewer` — always
- `decaf:security-reviewer` — always
- `decaf:test-reviewer` — only if test files exist in changeset
- `decaf:spec-compliance-reviewer` — only if `--spec <path>` was provided

#### `std` mode (default) — Triage-Based Selection

**Always included:**
- `decaf:code-reviewer-quick`
- `decaf:code-reviewer-broad`

**Default-include (exclude only with stated reason):**
- `decaf:code-reviewer-knowledge` — exclude only for trivial changes (typos, formatting, single-line fixes, comment-only edits)
- `decaf:design-reviewer` — exclude only when changes are trivial or confined to a single function's internals with no API/contract/boundary implications

**Include based on triage judgement:**
- `decaf:security-reviewer` — include when changes touch anything security-adjacent: authentication, authorization, cryptography, configuration/secrets, user input handling, HTTP/network, file I/O, serialization/deserialization, privilege boundaries. Judge from the diff content, not just filenames.
- `decaf:test-reviewer` — include when test files are present in the changeset (files matching `*Test*`, `*test*`, `*spec*`, `*.test.*`, `*.spec.*`, or residing in test/tests directories)
- `decaf:spec-compliance-reviewer` — include only when `--spec <path>` was provided

**Triage process:** Before selecting agents, skim the diff to understand:
1. How many files changed and their nature
2. Whether the changes are trivial (formatting, typos) or substantial
3. Whether security-sensitive areas are touched
4. Whether test files are in the changeset
5. State your agent selection and reasoning briefly before launching

### Guardrails (apply to ALL modes)

These rules override mode selections:
- **spec-compliance-reviewer**: Never included unless `--spec <path>` is provided
- **test-reviewer**: Never included unless test files exist in the changeset

### Step 3: Launch Review Agents in Parallel

Based on selection, launch agents using the **Task tool with parallel calls in a single message**.

**CRITICAL**: All agents for the selected mode MUST be launched in a single message with multiple Task tool calls. This ensures true parallel execution.

#### Agent Prompts

Each agent receives the same base context but with agent-specific focus:

**Base Context Template:**
```
Review the following code changes for issues. Focus on your area of expertise.
Follow your own output format instructions.

## Changes to Review
<paste git diff or file content here>

## Additional Instructions
<any user-provided instructions from $ARGUMENTS>
```

**Agent-Specific Focus:**
- `decaf:code-reviewer-quick`: Fast generalist — bugs, logic errors, null safety, security patterns, code quality, convention violations
- `decaf:code-reviewer-broad`: Comprehensive analysis — confidence scoring, knowledge preservation, production reliability, structural quality, architecture
- `decaf:code-reviewer-knowledge`: Knowledge preservation (RULE 0), undocumented decisions, implicit assumptions, comprehension risks
- `decaf:design-reviewer`: System-level design — API contracts, data models, boundary violations, concurrency design, evolution readiness
- `decaf:security-reviewer`: System-level security — threat modeling, missing controls (crypto, audit, config, dependencies, privileges)
- `decaf:test-reviewer`: Test quality — anti-patterns, silent failures, false positives, flaky patterns (test files only)
- `decaf:spec-compliance-reviewer`: Spec compliance — requirement gaps, deviations, partial implementations, scope creep (provide spec document in prompt)

**For spec-compliance-reviewer**, append the spec document content to the prompt:
```
## Specification
<contents of the --spec file>
```

### Step 4: Collect Results

Wait for all agents to complete. Each agent returns findings in JSON format.

### Step 5: Consolidate Findings

Apply the consolidation rules:

@../conventions/code-review-consolidation.md

1. **Normalize severities** across agents (MUST → Critical, SHOULD → High, etc.)
2. **Deduplicate** findings with same file + line (within 3 lines) + similar category
3. **Majority vote** for severity conflicts among duplicates
4. **Merge descriptions** from multiple finders

### Step 5.5: Review "Considered But Not Flagged" Items

**IMPORTANT**: Agents may inconsistently dismiss legitimate issues. For each agent's "Considered But Not Flagged" section:

1. **Collect all dismissed items** from all agents
2. **Cross-reference against flagged findings**: If Agent A dismissed something that Agent B flagged, include it as a finding
3. **Re-evaluate dismissed items**: For items no agent flagged, critically ask:
   - "Is the agent's reasoning for dismissal sound?"
   - "Does this match patterns that SHOULD be flagged (silent failures, knowledge loss, null safety)?"
   - "Would a user be confused or harmed by this issue?"
4. **Promote to findings** any dismissed items that:
   - Were dismissed with weak reasoning ("this is probably fine", "acceptable")
   - Match Critical/High severity criteria from any agent's guidelines
   - Involve knowledge preservation, silent failures, or null safety

This step compensates for LLM stochasticity where agents may "reason themselves out of" flagging legitimate issues.

### Step 5.6: Compute Agent Summary Statistics

After consolidation, compute per-agent statistics for the Agent Summary table:

1. **Issues Found**: For each agent, count how many consolidated findings list that agent in the "Found by" field. A shared finding (found by multiple agents) counts toward each agent that found it.
2. **Unique Issues**: For each agent, count findings where that agent is the **only** finder — i.e., no other agent reported the same issue (after deduplication).
3. **Total**: Sum of all consolidated findings (each finding counted once regardless of how many agents found it).

### Step 6: Generate Report

Create a timestamped review file in `.code-reviews/` at the repo root. **Never overwrite existing reviews.**

```bash
# Ensure directory exists
mkdir -p .code-reviews

# Creates: .code-reviews/CODE_REVIEW_2025-01-24_14-30-45.md
FILENAME=".code-reviews/CODE_REVIEW_$(date '+%Y-%m-%d_%H-%M-%S').md"
```

**Generate diffstat** from `git diff --stat` output for the reviewed changes. Summarize as file count and total insertions/deletions for the `**Scope**` line in the report header.

**Number all findings** in the report for easy reference.

```markdown
# Code Review

**Mode**: <mode> | **Reviewers**: <agent list> | **Date**: <YYYY-MM-DD>
**Scope**: N files changed, +X/-Y lines

## Agent Selection Rationale

<Brief explanation of why each specialist was included or excluded — std mode only>

## Summary

| Severity | Count |
|----------|-------|
| 🔴 Critical | X |
| 🟠 High | X |
| 🟡 Medium | X |
| 🟢 Low | X |

**Verdict**: ❌ NEEDS_CHANGES (if any Critical/High) | ✅ APPROVED (otherwise)

---

## Findings

### #1 🔴 Critical: <issue title>

| | |
|---|---|
| **File** | `<path>:<line>` |
| **Category** | <category> |
| **Confidence** | <avg confidence>/100 |
| **Found by** | <agent1> (<severity1>), <agent2> (<severity2 or "not flagged">) |

**Issue:** <description>

**Fix:** <suggested fix>
```language
// code snippet if applicable
```

---

### #2 🟠 High: <issue title>
...

### #3 🟡 Medium: <issue title>
...

### #4 🟢 Low: <issue title>
...

---

## Agent Summary

| Agent | Issues Found | Unique Issues |
|-------|:------------:|:-------------:|
| <agent1> | X | Y |
| <agent2> | X | Y |
| ... | ... | ... |
| **Total** | **X** | |

Notes:
- **Issues Found**: Total findings attributed to this agent (including shared findings)
- **Unique Issues**: Findings reported ONLY by this agent and no other

---

## Specialist Notes

<Include per-agent appendices that provide context beyond individual findings.
Only include sections that agents actually produced.>

### Requirement Coverage Matrix (spec-compliance-reviewer)
[If spec-compliance-reviewer was used, include its coverage matrix here]

### Threat Model Notes (security-reviewer)
[If security-reviewer was used, include its threat model notes here]

### Considered But Not Flagged (all agents)
[Consolidated list of items agents examined but did not flag, with reasoning.
Group by agent for clarity.]
```

### Severity Icons (ALWAYS include in finding headers)

- 🔴 Critical - Must fix before merge
- 🟠 High - Should fix before merge
- 🟡 Medium - Consider fixing
- 🟢 Low - Minor improvement

**Always use literal Unicode emoji characters (🔴🟠🟡🟢), never `:shortcode:` syntax like `:yellow_circle:`.**

### Finding Numbering

- Number findings sequentially: #1, #2, #3, etc.
- Order by severity first (Critical → High → Medium → Low), then by file path
- Include the number in the heading: `### #1 🔴 Critical: Issue title`

### Verdict Logic

- **NEEDS_CHANGES**: Any Critical or High severity findings
- **APPROVED**: Only Medium/Low findings or no findings

### Output Notification

After creating the review file, inform the user:
```
✅ Review complete: .code-reviews/CODE_REVIEW_2025-01-24_14-30-45.md
```

### Step 7: Review History (Recurring Findings)

After writing the report, scan `.code-reviews/CODE_REVIEW_*.md` for previous reviews. If previous reviews exist, check if any findings in the current review match findings from previous reviews (same file path + same category). If recurring findings are found, append a section to the report:

```markdown
## Recurring Findings

| File | Category | Occurrences | First Seen |
|------|----------|-------------|------------|
| `path/to/file.cs` | null-safety | 3 | 2025-12-01 |
```

Keep this lightweight — match on file path + category only. Skip this step if no previous reviews exist.

## Example Usage

```
/decaf:code-review                              # std mode, uncommitted changes
/decaf:code-review quick                        # Quick mode (2 agents) - fast feedback
/decaf:code-review max                          # Max mode - all applicable agents
/decaf:code-review --spec docs/design.md        # std mode with spec compliance check
/decaf:code-review max --spec docs/design.md    # Max mode with spec compliance
/decaf:code-review src/Tools/MyTool.cs          # std mode, specific file
/decaf:code-review max src/                     # Max mode, directory
/decaf:code-review focus on null safety         # std mode with custom instructions
```
