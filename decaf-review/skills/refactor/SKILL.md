---
name: refactor
description: Analyze code for structural improvement opportunities and produce a prioritized refactoring plan
argument-hint: "[quick|deep] [path|glob|full] [instructions]"
---

# Refactoring Analysis

This command analyzes existing code for structural improvement opportunities and produces a prioritized, actionable refactoring plan. It focuses on high-impact opportunities, not exhaustive issue lists.

## Argument Parsing

Parse `$ARGUMENTS` to determine:
1. **Mode**: `quick` or `deep` (default when no mode keyword given)
2. **Scope**: Specific file path, glob pattern, directory, `full`, or changed files (default)
3. **Instructions**: Any additional analysis instructions

| Mode | Agents | Use Case |
|------|--------|----------|
| `quick` | structural-analyst only (1) | Fast local quality check on specific files |
| `deep` (default) | structural-analyst + coherence-analyst (2) | Full analysis including cross-cutting patterns |

### Scope Resolution

| Input | Behavior |
|-------|----------|
| (none) | Changed files from `git diff HEAD --name-only`. Fall back to `git diff HEAD~1..HEAD --name-only` if no uncommitted changes. |
| `src/Services/` | All source files in that directory (recursive) |
| `src/**/*.cs` | Files matching the glob pattern |
| `src/OrderProcessor.cs` | That single file |
| `full` | Entire project — smart-sampled (see below) |

### Smart Sampling for `full` Scope

When scope is `full`, the codebase may be too large to analyze entirely. Apply smart sampling:

1. **Exclude**: Generated files, vendored code, test files, build output, node_modules, .git
2. **Prioritize**: Files with highest complexity indicators (line count, import count)
3. **Cap at ~30 files** to keep analysis tractable
4. **Note in report**: Which files were sampled and which were excluded

To determine exclusions, check CLAUDE.md for generated/vendored file patterns. Use `.gitignore` as baseline.

## Execution Steps

### Step 1: Gather Scope

Determine which files to analyze based on scope resolution above.

```bash
# For default scope (changed files):
git diff HEAD --name-only

# For directory scope:
# Use Glob tool to find source files

# For full scope:
# Use Glob + smart sampling
```

If scope is empty (no files match), inform the user and exit:
> No files found matching the specified scope. Provide a file path, directory, or glob pattern.

### Step 2: Read Project Context

Read the project's CLAUDE.md to understand:
- Language, framework, and conventions
- Architecture and module structure
- Any documented code quality standards

### Step 3: Select Agents by Mode

#### `quick` mode

1 agent — no cross-file analysis:
- `decaf-review:structural-analyst`

#### `deep` mode (default)

2 agents in parallel:
- `decaf-review:structural-analyst`
- `decaf-review:coherence-analyst`

### Step 4: Launch Agents in Parallel

**CRITICAL**: In deep mode, both agents MUST be launched in a single message with multiple Agent tool calls. This ensures true parallel execution.

#### Agent Prompts

**structural-analyst prompt:**
```
Analyze the following files for per-file structural improvement opportunities.
Focus on your area of expertise. Follow your own output format instructions.

## Files to Analyze
<list each file path, and paste file contents>

## Project Context
<relevant CLAUDE.md excerpts — language, conventions, architecture>

## Additional Instructions
<any user-provided instructions from $ARGUMENTS>
```

**coherence-analyst prompt (deep mode only):**
```
Analyze the following files for cross-file structural patterns and improvement opportunities.
Focus on your area of expertise. Follow your own output format instructions.

## Files to Analyze
<list each file path>

## Project Context
<relevant CLAUDE.md excerpts — language, conventions, architecture, module structure>

## Additional Instructions
<any user-provided instructions from $ARGUMENTS>

Note: You have access to Grep and Glob tools to search the broader codebase
for patterns beyond the listed files. Use them to verify cross-file patterns.
```

### Step 5: Collect Results

Wait for all agents to complete. Each agent returns opportunities in JSON format.

### Step 6: Consolidate and Prioritize

Apply the consolidation rules:

@../../../conventions/refactoring.md

1. **Normalize categories** across agents using the category mapping
2. **Deduplicate** opportunities with overlapping files + same category + same root cause
3. **Merge descriptions** from multiple finders
4. **Assign star ratings** using the value matrix (impact × effort)
5. **Filter**: Discard items below inclusion threshold (★ or —)
6. **Group** related opportunities into refactoring units
7. **Order** by star rating → dependencies → file overlap

### Step 6.5: Review "Considered But Not Flagged" Items

For each agent's "Considered But Not Flagged" section:

1. **Cross-reference**: If agent A dismissed something that agent B flagged, include it
2. **Re-evaluate**: For items no agent flagged, verify dismissal reasoning is sound
3. **Promote** any dismissed items with weak reasoning that match High/Medium impact criteria

### Step 7: Generate Refactoring Plan

Create a timestamped plan file in `.refactoring-plans/` at the repo root. **Never overwrite existing plans.**

```bash
mkdir -p .refactoring-plans
FILENAME=".refactoring-plans/REFACTOR_PLAN_$(date '+%Y-%m-%d_%H-%M-%S').md"
```

**Plan format:**

```markdown
# Refactoring Plan

**Mode**: <mode> | **Analysts**: <agent list> | **Date**: <YYYY-MM-DD>
**Scope**: N files analyzed

## Value Matrix

| Rating | Count |
|--------|-------|
| ★★★ | X |
| ★★ | X |

**Total opportunities:** N (grouped into M refactoring units)

---

## Refactoring Units

### #1 ★★★ Extract PaymentValidation domain service

| | |
|---|---|
| **Impact** | High |
| **Effort** | Medium |
| **Files** | `src/OrderProcessor.cs`, `src/PaymentService.cs`, `src/RefundHandler.cs` |
| **Category** | validation-scattering |
| **Found by** | coherence-analyst (High), structural-analyst (Medium) |
| **Confidence** | 88/100 |

**Problem:** Payment validation logic is duplicated across 3 services with subtly different implementations. The OrderProcessor validates card expiry differently than PaymentService, creating inconsistent behavior.

**Before:**
```csharp
// OrderProcessor.cs:45
if (card.ExpiryDate < DateTime.Now) ...

// PaymentService.cs:72
if (card.ExpiryDate <= DateTime.UtcNow) ...
```

**After:**
```csharp
// PaymentValidation.cs
public static bool IsCardExpired(Card card)
    => card.ExpiryDate <= DateTime.UtcNow;
```

**Steps:**
1. Create `PaymentValidation` service with consolidated rules
2. Replace inline validation in OrderProcessor
3. Replace inline validation in PaymentService
4. Replace inline validation in RefundHandler
5. Add unit tests for consolidated validation

---

### #2 ★★★ Simplify OrderProcessor.ProcessOrder()

| | |
|---|---|
| **Impact** | High |
| **Effort** | Small |
| **Files** | `src/OrderProcessor.cs` |
| **Category** | god-function |
| **Found by** | structural-analyst |
| **Confidence** | 92/100 |

**Problem:** ProcessOrder() is 85 lines mixing validation, persistence, and notification concerns at different abstraction levels.

**Before:**
```csharp
public async Task ProcessOrder(Order order)
{
    // 85 lines mixing validation, DB calls, email sending
}
```

**After:**
```csharp
public async Task ProcessOrder(Order order)
{
    Validate(order);
    await Persist(order);
    await NotifyCustomer(order);
}
```

**Steps:**
1. Extract Validate() method
2. Extract Persist() method
3. Extract NotifyCustomer() method

---

### #3 ★★ ...
...

---

## Considered But Not Flagged

[Items examined but below inclusion threshold or determined to be acceptable design,
grouped by agent with rationale.]

---

## Analysis Notes

**Scope**: [Description of what was analyzed]
**Sampling**: [If full mode, note which files were sampled/excluded]
**Limitations**: [What cross-cutting patterns may have been missed due to scope]
```

### Severity Icons for Star Ratings

- ★★★ — High-value: address first
- ★★ — Worthwhile: address when nearby
- ★ — Low-value (not included in main plan)

**Always use literal Unicode star characters (★), never `:shortcode:` syntax.**

### Output Notification

After creating the plan file, inform the user:

```
✅ Refactoring plan complete: .refactoring-plans/REFACTOR_PLAN_2026-03-03_14-30-45.md

★★★ High-value: X opportunities
★★  Worthwhile:  Y opportunities
Total: Z refactoring units

Run /decaf-review:handle-refactoring to walk through opportunities interactively.
```

## Example Usage

```
/decaf-review:refactor                                # deep mode, changed files
/decaf-review:refactor quick                          # quick mode (structural only)
/decaf-review:refactor src/Services/                  # deep mode, specific directory
/decaf-review:refactor src/**/*.cs                    # deep mode, glob pattern
/decaf-review:refactor src/OrderProcessor.cs          # deep mode, single file
/decaf-review:refactor full                           # deep mode, entire project (sampled)
/decaf-review:refactor quick src/OrderProcessor.cs    # quick mode, single file
/decaf-review:refactor focus on error handling         # deep mode with instructions
```
