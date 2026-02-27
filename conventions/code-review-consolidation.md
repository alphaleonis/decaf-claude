# Code Review Consolidation Rules

This document defines how findings from multiple review agents are merged into a unified report.

## Severity Normalization

Each agent uses different terminology. Normalize to standard severities:

| Agent | Critical | High | Medium | Low |
|-------|----------|------|--------|-----|
| decaf:code-reviewer-quick | Critical | High | Medium | Low |
| decaf:code-reviewer-broad | Critical (🔴) | High (🟠) | Medium (🟡) | Low (🟢) |
| decaf:code-reviewer-knowledge | MUST | SHOULD | CONSIDER | LOW, MINOR |
| decaf:security-reviewer | Critical | High | Medium | Low |
| decaf:design-reviewer | Critical | High | Medium | Low |
| decaf:spec-compliance-reviewer | Critical | High | Medium | Low |

**Mapping Rules:**
- `MUST`, `CRITICAL`, `Critical` → **Critical**
- `SHOULD`, `HIGH`, `High` → **High**
- `CONSIDER`, `MEDIUM`, `Medium` → **Medium**
- `LOW`, `MINOR`, `Low`, anything else → **Low**

## Deduplication Rules

Two findings are considered **duplicates** if ALL of the following match:

1. **Same file path** (exact match, case-insensitive on Windows)
2. **Line numbers within 3 lines** of each other (`abs(line1 - line2) <= 3`)
3. **Similar category** (exact match or semantic equivalence):
   - `null-safety` = `nullable` = `null-check`
   - `unused-code` = `dead-code` = `unreachable`
   - `security` = `vulnerability`
   - `error-handling` = `exception-handling`

### Merging Duplicates

When duplicates are found:

1. **Combine descriptions**: Include unique insights from each agent
2. **Apply majority vote** for severity (see below)
3. **List all finders**: Record which agents found the issue and what severity each assigned
4. **Average confidence**: Calculate mean of all confidence scores

## Majority Vote Algorithm

When multiple agents report the same issue with different severities:

### 3+ Agents
- **Majority wins**: If 2+ agents agree on severity, use that severity
- Example: 2 say "Low", 1 says "Critical" → Report as **Low** with note about dissent

### 2 Agents (Tie)
- **Higher severity wins**: Use the more severe rating as tie-breaker
- Example: 1 says "High", 1 says "Medium" → Report as **High**
- Rationale: Better to over-report than miss a real issue

### 1 Agent
- Use the single agent's severity as-is

### Recording Dissent

Always note disagreements in the "Found by" field:
```
**Found by** | decaf (Critical), security (Low - dissenting), design (Low)
```

## Category Taxonomy

Standardize categories across agents:

| Standard Category | Aliases |
|-------------------|---------|
| `null-safety` | nullable, null-check, null-reference, NRE |
| `unused-code` | dead-code, unreachable-code, unused-variable |
| `security` | vulnerability, injection, authentication, authorization, THREAT_ATTACK_SURFACE, THREAT_CRYPTO, THREAT_DEPENDENCY, THREAT_TEST_COVERAGE, THREAT_CONFIG, THREAT_AUDIT, THREAT_PRIVILEGE, THREAT_COMPLIANCE |
| `error-handling` | exception-handling, try-catch, error-propagation |
| `performance` | efficiency, optimization, memory, allocation |
| `design` | architecture, pattern, coupling, cohesion, SOLID |
| `naming` | convention, identifier, readability |
| `type-safety` | casting, type-conversion, generics |
| `async` | async-await, task, concurrency, threading |
| `resource-management` | disposal, IDisposable, using-statement |
| `spec-compliance` | SPEC_UNIMPLEMENTED, SPEC_PARTIAL, SPEC_DEVIATION, SPEC_UNCOVERED, SPEC_EDGE_CASE |
| `other` | anything that doesn't fit above |

## Consolidation Algorithm

```
1. Collect all findings from all agents
2. For each finding:
   a. Normalize severity using mapping table
   b. Normalize category using taxonomy
3. Group findings by (file, approximate_line, category)
4. For each group with multiple findings:
   a. Apply majority vote for severity
   b. Merge descriptions (deduplicate similar text)
   c. Average confidence scores
   d. Record all finders with their original severities
5. Sort final findings:
   a. Primary: Severity (Critical > High > Medium > Low)
   b. Secondary: File path (alphabetical)
   c. Tertiary: Line number (ascending)
6. Generate unified report
```

## Edge Cases

### No Findings
If all agents return empty results:
- Report verdict as **APPROVED**
- Include note: "No issues found by any reviewer"

### Agent Failure
If an agent fails or times out:
- Continue with results from successful agents
- Note the failure in the report header
- Example: `**Reviewers**: decaf, security (failed), design`

### Conflicting Fixes
If agents suggest different fixes for the same issue:
- Include both suggestions
- Label each with the source agent
- Let the developer choose
