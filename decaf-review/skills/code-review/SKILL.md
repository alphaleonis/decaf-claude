---
name: code-review
description: Run parallel code review agents and consolidate findings into a unified report
argument-hint: "[quick|std|max] [--spec <path>] [PR#] [path] [instructions]"
---

# Code Review

This command orchestrates code review agents and consolidates their findings into a unified, deduplicated report.

## Argument Parsing

Parse `$ARGUMENTS` to determine:
1. **Mode**: `quick`, `max`, or `std` (default when no mode keyword given)
2. **Spec path**: `--spec <path>` — a specification or plan document to verify compliance against
3. **PR number**: A pull request number (e.g., `123`, `PR#123`, `#123`) — review that PR instead of local changes
4. **Scope**: Specific file/directory path, or all uncommitted changes (ignored when PR number is provided)
5. **Instructions**: Any additional review instructions

| Mode | Agents | Use Case |
|------|--------|----------|
| `quick` | quick + broad (2) | Fast feedback from two generalists |
| `std` (default) | quick + broad + judged specialists (3-7) | Balanced: generalists + specialists selected by triage |
| `max` | All applicable agents (5-7) | Maximum coverage, all agents that apply |

## Execution Steps

### Step 1: Gather Context

Determine what code to review:

#### PR mode (when a PR number is provided)

Detect the hosting platform from context (git remotes, available MCP tools, or prior conversation):

- **Azure DevOps**: Use `mcp__azure-devops__repo_get_pull_request_by_id` to fetch the PR metadata (title, description, author, source branch, **target branch**), then retrieve the diff. List changed files and their diffs via the Azure DevOps MCP tools.
- **GitHub**: Use `gh pr view <number> --json title,body,author,baseRefName,headRefName` for metadata, then `gh pr diff <number>` for the diff.

**Target branch awareness**: The PR's target (base) branch determines the true scope of the review. A PR targeting a feature branch may contain only a few incremental changes, even if the source branch is far ahead of `main`/`develop`. Always identify the target branch and ensure the diff reflects only the changes between source and target — not the cumulative distance from the default branch.

Include the PR title, description, author, source branch, and **target branch** in the context passed to agents so they can evaluate intent and scope correctly.

**IMPORTANT**: Do NOT post comments, reviews, or status updates to the PR. The review output is a local file only. If the user explicitly asks to post comments to the PR, then and only then may you do so.

#### Local mode (default — no PR number)

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
- `decaf-review:code-reviewer-quick`
- `decaf-review:code-reviewer-broad`

#### `max` mode

Include all agents, subject to guardrails:
- `decaf-review:code-reviewer-quick` — always
- `decaf-review:code-reviewer-broad` — always
- `decaf-review:code-reviewer-knowledge` — always
- `decaf-review:design-reviewer` — always
- `decaf-review:security-reviewer` — always
- `decaf-review:test-reviewer` — only if test files exist in changeset
- `decaf-review:spec-compliance-reviewer` — only if `--spec <path>` was provided

#### `std` mode (default) — Triage-Based Selection

**Always included:**
- `decaf-review:code-reviewer-quick`
- `decaf-review:code-reviewer-broad`

**Default-include (exclude only with stated reason):**
- `decaf-review:code-reviewer-knowledge` — exclude only for trivial changes (typos, formatting, single-line fixes, comment-only edits)
- `decaf-review:design-reviewer` — exclude only when changes are trivial or confined to a single function's internals with no API/contract/boundary implications

**Include based on triage judgement:**
- `decaf-review:security-reviewer` — include when changes touch anything security-adjacent: authentication, authorization, cryptography, configuration/secrets, user input handling, HTTP/network, file I/O, serialization/deserialization, privilege boundaries. Judge from the diff content, not just filenames.
- `decaf-review:test-reviewer` — include when test files are present in the changeset (files matching `*Test*`, `*test*`, `*spec*`, `*.test.*`, `*.spec.*`, or residing in test/tests directories)
- `decaf-review:spec-compliance-reviewer` — include only when `--spec <path>` was provided

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
- `decaf-review:code-reviewer-quick`: Fast generalist — bugs, logic errors, null safety, security patterns, code quality, convention violations
- `decaf-review:code-reviewer-broad`: Comprehensive analysis — confidence scoring, knowledge preservation, production reliability, structural quality, architecture
- `decaf-review:code-reviewer-knowledge`: Knowledge preservation (RULE 0), undocumented decisions, implicit assumptions, comprehension risks
- `decaf-review:design-reviewer`: System-level design — API contracts, data models, boundary violations, concurrency design, evolution readiness
- `decaf-review:security-reviewer`: System-level security — threat modeling, missing controls (crypto, audit, config, dependencies, privileges)
- `decaf-review:test-reviewer`: Test quality — anti-patterns, silent failures, false positives, flaky patterns (test files only)
- `decaf-review:spec-compliance-reviewer`: Spec compliance — requirement gaps, deviations, partial implementations, scope creep (provide spec document in prompt)

**For spec-compliance-reviewer**, append the spec document content to the prompt:
```
## Specification
<contents of the --spec file>
```

### Step 4: Collect Results

Wait for all agents to complete. Each agent returns findings in JSON format.

### Step 5: Consolidate Findings

Apply the consolidation rules:

@../../../conventions/code-review-consolidation.md

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
**Source**: <PR #N — title (platform) [source → target]> | <local changes> | <last commit>
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
/decaf-review:code-review                              # std mode, uncommitted changes
/decaf-review:code-review quick                        # Quick mode (2 agents) - fast feedback
/decaf-review:code-review max                          # Max mode - all applicable agents
/decaf-review:code-review --spec docs/design.md        # std mode with spec compliance check
/decaf-review:code-review max --spec docs/design.md    # Max mode with spec compliance
/decaf-review:code-review src/Tools/MyTool.cs          # std mode, specific file
/decaf-review:code-review max src/                     # Max mode, directory
/decaf-review:code-review focus on null safety         # std mode with custom instructions
/decaf-review:code-review 42                           # std mode, review PR #42
/decaf-review:code-review max #42                      # Max mode, review PR #42
/decaf-review:code-review quick PR#123                 # Quick mode, review PR #123
```
