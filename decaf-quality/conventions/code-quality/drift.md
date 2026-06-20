# Drift Code Quality

Quality concerns that are ONLY detectable through codebase-wide analysis. These have no meaningful local variant -- the problem is inherently about relationships between files, modules, or components.

Requires periodic review or tooling that sees the whole codebase.

## 1. Module Structure

<principle>
Modules should have clear boundaries with minimal coupling. When changes ripple across unrelated modules, the boundaries are wrong.
</principle>

Detect: Do changes ripple to unrelated modules? Can a module be modified without understanding its dependents?

<grep-hints>
Structural indicators (starting points, not definitive):
Import graphs, dependency declarations, module boundaries
</grep-hints>

<violations>
Illustrative patterns (not exhaustive -- similar violations exist):

[high] Structural violations

- Circular dependencies (e.g., A imports B imports A)
- Layer violations (e.g., domain importing infrastructure)
- Any dependency causing compilation order issues or domain corruption

[medium] Cohesion problems

- Wrong cohesion (unrelated things grouped in same module)
- Missing facades (module internals exposed directly)

[low] Scope creep

- God modules (too many responsibilities in one module)
  </violations>

<exceptions>
Circular deps within same bounded context. Infrastructure adapters importing domain. Shared kernel patterns.
</exceptions>

<threshold>
Flag when dependency causes compilation order issues OR when layer violation allows infrastructure to corrupt domain.
</threshold>

## 2. Architecture

<principle>
Architecture should align with change patterns. When adding a feature requires touching many unrelated components, the architecture fights the domain.
</principle>

Detect: Would adding a feature require touching many components? Do cross-cutting changes indicate misaligned boundaries?

<grep-hints>
Structural indicators (starting points, not definitive):
Component boundaries, service interfaces, configuration locations
</grep-hints>

<violations>
Illustrative patterns (not exhaustive -- similar violations exist):

[high] Boundary misalignment

- Wrong component boundaries (features awkwardly split)
- Single points of failure (no fallback, no retry paths)
- Any architecture forcing cross-cutting changes for single-domain features

[medium] Scaling issues

- Scaling bottlenecks (synchronous where async needed)
- Monolith patterns in distributed code (or vice versa)

[low] Missing structure

- Missing abstraction layers (everything directly coupled)
- Configuration scattered (no central policy, settings in many places)
  </violations>

<exceptions>
Intentional coupling for simplicity. Early-stage monolith. Bounded contexts with shared kernel.
</exceptions>

<threshold>
Flag when architecture forces cross-cutting changes for single-domain features.
</threshold>

## 3. Cross-File Comprehension

<principle>
Understanding a flow should not require reading the entire codebase. When grasping one operation requires 5+ files with no guide, comprehension is broken.
</principle>

Detect: How many files must I read to understand this flow? Is there documentation or an orchestrator that explains the big picture?

<grep-hints>
Structural indicators (starting points, not definitive):
Call chains, event handlers, callback registrations
</grep-hints>

<violations>
Illustrative patterns (not exhaustive -- similar violations exist):

[high] Implicit contracts

- Implicit contracts between files (caller must know callee internals)
- Any flow requiring undocumented assumptions to understand

[medium] Hidden dependencies

- Hidden dependencies (file A assumes file B ran first)

[low] Scattered flow

- Scattered control flow (one operation spans 5+ files with no orchestrator)
  </violations>

<exceptions>
Well-documented module boundaries. Plugin architectures. Event-driven designs with clear event contracts.
</exceptions>

<threshold>
Flag when understanding a single operation requires reading 5+ files with no documentation of the flow.
</threshold>

## 4. Abstraction Opportunities

<principle>
Repeated patterns across files indicate missing abstractions. When you see the same transformation in 3+ places, a concept is trying to emerge.
</principle>

Detect: What domain concept is hiding across these repeated patterns? Would extracting a shared abstraction reduce duplication?

<grep-hints>
Structural indicators (starting points, not definitive):
Parallel implementations, similar transformation chains, repeated configuration shapes
</grep-hints>

<violations>
Illustrative patterns (not exhaustive -- similar violations exist):

[high] Missed abstractions

- Same transformation applied in multiple files (3+ occurrences)
- Any pattern appearing across implementations that should be shared

[medium] Structural duplication

- Parallel class hierarchies doing similar things differently
- Copy-paste inheritance (similar classes with minor variations)

[low] Configuration patterns

- Data transformation pipelines with identical structure
- Configuration patterns repeated without abstraction
  </violations>

<exceptions>
Intentionally similar but independent implementations. Domain-specific variations. Templates/generators producing similar code.
</exceptions>

<threshold>
Flag when pattern appears in 3+ implementations AND the fix is extracting shared abstraction. These become visible only after seeing multiple implementations.
</threshold>

## 5. Feature Flag Sprawl

<principle>
Feature flags should be checked consistently. When the same flag is evaluated with different logic in different places, behavior becomes unpredictable.
</principle>

Detect: How are feature flags checked across the codebase? Is the same flag evaluated consistently everywhere?

<grep-hints>
Structural indicators (starting points, not definitive):
Feature flag checks, toggle patterns, conditional feature code
</grep-hints>

<violations>
Illustrative patterns (not exhaustive -- similar violations exist):

[high] Inconsistent evaluation

- Feature flags checked inconsistently (different conditions for same flag)
- Any flag with divergent evaluation logic across locations

[medium] Undocumented dependencies

- Flag dependencies not documented (flag A requires flag B)
  </violations>

<exceptions>
Flags with intentionally different behavior per context. A/B test variations. Gradual rollout logic.
</exceptions>

<threshold>
Flag when same feature flag is checked with different logic in different places AND the difference is unintentional.
</threshold>

Note: Dead flags (feature shipped, never removed) are covered in coherence.md Zombie Code.
