# Refactoring Consolidation Rules

This document defines how findings from structural-analyst and coherence-analyst agents are merged into a unified, prioritized refactoring plan.

## Impact Taxonomy

| Level | Definition | Examples |
|-------|-----------|----------|
| **High** | Changes behavior correctness, prevents bugs, or eliminates a class of errors | God objects with tangled state, scattered business rules that have diverged, swallowed exceptions losing diagnostic info |
| **Medium** | Improves maintainability, readability, or developer velocity without changing behavior | Near-duplicate logic, naming inconsistencies, missing domain types at API boundaries, deep nesting |
| **Low** | Cosmetic or minor friction reduction | Style drift, outdated idioms with modern equivalents, minor naming imprecision |

## Effort Taxonomy

| Level | Definition | Indicators |
|-------|-----------|------------|
| **Small** | < 1 hour, single file, mechanical transformation | Rename, extract method, inline variable, add guard clause |
| **Medium** | 1–4 hours, 2–5 files, requires understanding of local context | Extract class, introduce interface, consolidate validation, unify error patterns |
| **Large** | 4+ hours, 5+ files, cross-cutting change requiring coordination | Module boundary redesign, domain model introduction, architecture realignment |

## Value Matrix

Impact × Effort → star rating. Stars determine inclusion and ordering.

| | Small Effort | Medium Effort | Large Effort |
|---|:---:|:---:|:---:|
| **High Impact** | ★★★ | ★★★ | ★★ |
| **Medium Impact** | ★★★ | ★★ | ★ |
| **Low Impact** | ★★ | — | — |

**Inclusion threshold**: ★★ or higher. Items rated ★ or — go in "Considered But Not Flagged" with brief rationale.

## Deduplication Rules

Two opportunities are considered **duplicates** if ALL of the following match:

1. **Same file(s)** (at least one overlapping file)
2. **Same category** (exact match or semantic equivalence — see category mapping below)
3. **Same root cause** (both describe the same underlying structural problem)

### Category Mapping

| Standard Category | Aliases (from either agent) |
|-------------------|----------------------------|
| `god-object` | responsibility-diffusion, mixed-concerns, large-class |
| `god-function` | long-method, deep-nesting, mixed-abstraction-levels |
| `duplication` | near-duplication, copy-paste, missed-abstraction |
| `naming` | naming-inconsistency, synonym-drift, name-behavior-mismatch |
| `domain-modeling` | primitive-obsession, missing-value-object, hidden-domain-logic |
| `validation-scattering` | scattered-validation, diverged-validation |
| `business-rule-scattering` | scattered-decisions, mixed-concerns |
| `error-handling` | inconsistent-errors, swallowed-exceptions, information-loss |
| `zombie-code` | dead-code, unreachable, unused-exports |
| `module-boundaries` | circular-dependency, layer-violation, boundary-misalignment |
| `interface-consistency` | signature-inconsistency, api-drift |
| `type-design` | weak-typing, optional-explosion |
| `control-flow` | excessive-branching, nested-ternaries |
| `dependency-injection` | untestable-coupling, hard-coded-dependencies |
| `modern-idioms` | outdated-patterns, legacy-patterns |

### Merging Duplicates

When duplicates are found:

1. **Combine descriptions**: Include unique insights from each agent
2. **Use higher impact**: Take the more severe impact rating
3. **Use larger effort**: Take the more conservative effort estimate
4. **Record both finders**: Note which agent(s) identified the opportunity

## Grouping Into Refactoring Units

After deduplication, group related opportunities into coherent **refactoring units** — changes that should be applied together:

1. **Same root cause**: Multiple symptoms of the same structural problem → one unit
2. **Dependency chain**: Opportunity A enables opportunity B → one unit, ordered
3. **Same file cluster**: 3+ opportunities in the same 2–3 files → consider grouping

Each refactoring unit gets:
- A descriptive title (action-oriented, e.g., "Extract PaymentValidation domain service")
- Combined star rating (highest among grouped opportunities)
- Ordered execution steps within the unit
- Combined file list

## Execution Order

Sort refactoring units by:

1. **Star rating** (★★★ first)
2. **Dependencies** (prerequisite units before dependents)
3. **File overlap** (units touching the same files adjacent, to minimize context switches)

Within the same star rating and no dependency relationship, prefer:
- High-impact/small-effort (quick wins) before high-impact/large-effort
- Units with more agent agreement (found by both agents) before single-agent findings

## Consolidation Algorithm

```
1. Collect all findings from both agents
2. For each finding:
   a. Normalize category using category mapping
   b. Assign impact and effort ratings
   c. Compute star rating from value matrix
3. Filter: discard items below inclusion threshold (★ or —)
4. Group findings by (overlapping files, same category, same root cause)
5. For each group with multiple findings:
   a. Merge descriptions
   b. Take higher impact, larger effort
   c. Record all finders
6. Group related opportunities into refactoring units
7. Sort by star rating → dependencies → file overlap
8. Generate plan with numbered units and execution order
```

## Edge Cases

### No Findings
If both agents return empty results:
- Report as "No refactoring opportunities identified"
- Include note about scope analyzed

### Single Agent Mode (quick)
If only structural-analyst ran:
- Skip cross-file deduplication
- Note that coherence patterns were not analyzed

### Agent Failure
If an agent fails or times out:
- Continue with results from the successful agent
- Note the failure in the plan header
