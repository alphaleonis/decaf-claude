# Coherence

Quality concerns about repetition, consistency, and dead code. These patterns indicate the same concept expressed in multiple ways, or code that should not exist.

Each pattern applies at two scopes with different thresholds:

| Scope    | Detection method                        | Typical threshold |
| -------- | --------------------------------------- | ----------------- |
| File     | Single-file review, local fix           | 2+ occurrences    |
| Codebase | Cross-file search, coordinated refactor | 3+ files          |

Use file-scope thresholds for single-file review. Use codebase-scope for architecture review or coordinated refactoring.

---

## 1. Duplication

<principle>
Code should have a single source of truth. When the same logic exists in multiple places, bugs must be fixed everywhere -- and they won't be.
</principle>

Detect: If I fixed a bug here, where else would I need to fix it?

<grep-hints>
Structural indicators (starting points, not definitive):
Identical multi-line blocks, similar function bodies, function names suggesting similar purpose across modules
</grep-hints>

<scope-thresholds>
Illustrative thresholds (adjust based on context):
- File scope: 2+ occurrences of same logic in one file
- Codebase scope: 3+ files implementing same algorithm
</scope-thresholds>

<violations>
Illustrative patterns (not exhaustive -- similar violations exist):

[high] Direct duplication

- Same code block duplicated (3+ lines, logic not just boilerplate)
- Any logic that would require multi-location bug fixes

[medium] Near-duplication

- Copy-paste with minor variations

[low] Missed abstraction

- Common pattern not extracted to shared location
  </violations>

<exceptions>
Intentionally different logic serving different purposes. Test setup code. Generated/vendored code. Deliberate isolation for modularity. Similar code in different bounded contexts.
</exceptions>

<threshold>
Flag when bug fix would require changing multiple locations AND the duplication is unintentional.
</threshold>

---

## 2. Naming Consistency

<principle>
A concept should have one name throughout the codebase. Multiple names for the same thing create confusion about whether they're actually the same.
</principle>

Detect: Are there multiple names for the same concept? Would a reader wonder if user and account refer to the same entity?

<grep-hints>
Pattern indicators (starting points, not definitive):
Synonyms as variable prefixes (user/account/customer, config/settings/options, id/uid/identifier)
</grep-hints>

<scope-thresholds>
Illustrative thresholds (adjust based on context):
- File scope: 2+ names for same entity in one file
- Codebase scope: 3+ different names across modules (e.g., userId/uid/id)
</scope-thresholds>

<violations>
Illustrative patterns (not exhaustive -- similar violations exist):

[high] Semantic confusion

- Synonym drift causing confusion at integration points
- Any naming inconsistency causing doubt about identity

[medium] Inconsistent conventions

- Inconsistent abbreviations (e.g., id vs identifier)

[low] Style drift

- Style inconsistency without semantic confusion
  </violations>

<exceptions>
Different names for genuinely different concepts. External API naming conventions. Domain-specific terminology. Legacy compatibility aliases in bounded migration.
</exceptions>

<threshold>
Flag when same semantic concept has multiple names AND causes confusion about whether they refer to the same thing.
</threshold>

---

## 3. Validation Scattering

<principle>
Validation rules should live in one place. When the same validation is implemented multiple times, implementations diverge -- and some will be wrong.
</principle>

Detect: Is this validation duplicated? Would changing the validation rule require updating multiple locations?

<grep-hints>
Pattern indicators (starting points, not definitive):
Repeated regex patterns, duplicate bounds checks, email/phone/format validation across locations
</grep-hints>

<scope-thresholds>
Illustrative thresholds (adjust based on context):
- File scope: 3+ identical validations in one file
- Codebase scope: 5+ files with same validation implemented differently
</scope-thresholds>

<violations>
Illustrative patterns (not exhaustive -- similar violations exist):

[high] Diverged validation

- Validation rules diverged between implementations
- Any validation requiring multi-location updates

[medium] Repeated validation

- Same validation repeated without shared implementation

[low] Defensive re-validation

- Defensive re-validation deeper in call chain
  </violations>

<exceptions>
Validation at trust boundaries. Defense-in-depth by design. Context-specific validation rules. Service boundary validation.
</exceptions>

<threshold>
Flag when identical validation appears N+ times AND implementations have diverged or will diverge.
</threshold>

---

## 4. Business Rule Scattering

<principle>
Business rules should have a single source of truth. When the same decision is made in multiple places, they will eventually disagree.
</principle>

Detect: Where is the single source of truth for this rule? If the rule changes, how many places need updating?

<grep-hints>
Pattern indicators (starting points, not definitive):
Repeated conditional patterns, magic numbers in multiple places, pricing/permission/eligibility logic
</grep-hints>

<scope-thresholds>
Illustrative thresholds (adjust based on context):
- File scope: 2+ policy decisions in same file
- Codebase scope: 3+ files enforcing same business rule
</scope-thresholds>

<violations>
Illustrative patterns (not exhaustive -- similar violations exist):

[high] Scattered decisions

- Same business decision in multiple places that could diverge
- Any business rule without clear single source of truth

[medium] Mixed concerns

- Business logic mixed with infrastructure code

[low] Implicit rules

- Rules embedded in raw conditionals instead of named predicates
  </violations>

<exceptions>
Orchestration calling multiple rule checks. Rules intentionally duplicated for service isolation. Per-tenant/region rule variations. Caching of computed rules.
</exceptions>

<threshold>
Flag when same business decision is made in N+ places AND they have diverged or could diverge independently.
</threshold>

---

## 5. Condition Pattern Repetition

<principle>
Repeated boolean expressions should be named predicates. When the same condition appears everywhere, changing it requires finding all occurrences.
</principle>

Detect: Should this condition be a named predicate? Does extracting it reduce the bug surface area?

<grep-hints>
Pattern indicators (starting points, not definitive):
Identical boolean expressions, repeated guard clauses, permission/feature-flag check patterns
</grep-hints>

<scope-thresholds>
Illustrative thresholds (adjust based on context):
- File scope: 3+ identical conditions in one file
- Codebase scope: 5+ files with same permission/feature check
</scope-thresholds>

<violations>
Illustrative patterns (not exhaustive -- similar violations exist):

[high] High-frequency repetition

- Identical condition in N+ places (extracting reduces bug surface)
- Any condition requiring multi-location updates when logic changes

[medium] Pattern repetition

- Repeated feature flag conditions

[low] Guard repetition

- Same guard clause pattern across related functions
  </violations>

<exceptions>
Standard guard clauses (null checks, bounds checks). Framework-required patterns. Simple conditions that read clearly inline.
</exceptions>

<threshold>
Flag when identical condition appears N+ times AND extracting to named predicate would reduce bug surface area.
</threshold>

---

## 6. Error Pattern Consistency

<principle>
Error handling should be consistent within an abstraction level. Mixed patterns create confusion about how errors propagate and should be handled.
</principle>

Detect: Is error handling consistent? Would a caller know what to expect from similar operations?

<grep-hints>
Pattern indicators (starting points, not definitive):
Mixed exception/return-code patterns, inconsistent error message formats, varying error context
</grep-hints>

<scope-thresholds>
Illustrative thresholds (adjust based on context):
- File scope: 2+ error handling styles in same class
- Codebase scope: 3+ different error patterns at same abstraction level
</scope-thresholds>

<violations>
Illustrative patterns (not exhaustive -- similar violations exist):

[high] Incompatible patterns

- Incompatible error patterns for similar operations
- Any error handling creating caller confusion

[medium] Inconsistent hierarchy

- Inconsistent exception hierarchies

[low] Missing convention

- No standard for error context/wrapping
  </violations>

<exceptions>
Different patterns for different abstraction levels (domain vs API vs infra). Wrapper functions translating between error styles. Legacy code under active migration.
</exceptions>

<threshold>
Flag when same abstraction level uses N+ incompatible error patterns for similar operations AND no migration plan exists.
</threshold>

---

## 7. Interface Consistency

<principle>
Similar APIs should have consistent signatures. When similar functions surprise users with different conventions, they cause bugs.
</principle>

Detect: Would a user of these APIs be surprised by inconsistency? Do similar operations have incompatible signatures?

<grep-hints>
Pattern indicators (starting points, not definitive):
Similar function signatures with different parameter orders, CRUD operation patterns, service method signatures
</grep-hints>

<scope-thresholds>
Illustrative thresholds (adjust based on context):
- File scope: 2+ similar functions with different parameter orders
- Codebase scope: 3+ APIs with incompatible signatures for similar operations
</scope-thresholds>

<violations>
Illustrative patterns (not exhaustive -- similar violations exist):

[high] Signature inconsistency

- APIs with similar purposes have incompatible signatures AND share consumers
- Any API inconsistency causing caller confusion

[medium] Naming inconsistency

- Inconsistent naming conventions across related functions

[low] Pattern inconsistency

- Mixed sync/async for similar operations without clear reason
  </violations>

<exceptions>
Intentional API differences. Domain-specific conventions. Versioned APIs. Overloads with clear distinct purpose.
</exceptions>

<threshold>
Flag when APIs with similar purposes have inconsistent signatures AND confusion impacts consumers.
</threshold>

---

## 8. Zombie Code

<principle>
Dead code is noise that misleads readers. Code that cannot execute or is never called should be removed, not left to confuse future maintainers.
</principle>

Detect: If I deleted this, would any test fail or behavior change?

<grep-hints>
Pattern indicators (starting points, not definitive):
Commented blocks, `#if 0`, unreachable branches, unused variables, exported symbols with 0 callers, feature flags
</grep-hints>

<scope-thresholds>
Illustrative thresholds (adjust based on context):
- File scope: Presence of >5 lines commented code, unreachable branches, unused locals
- Codebase scope: 0 references to exported function, dead feature flags
</scope-thresholds>

<violations>
Illustrative patterns (not exhaustive -- similar violations exist):

File-scope patterns:

[high] Dead code blocks

- Commented-out code blocks (>5 lines of code, not documentation)
- Unreachable branches (e.g., else after unconditional return, dead switch cases)
- Any code that cannot execute

[medium] Unused declarations

- Unused local variables or parameters

[low] Orphaned functions

- Functions defined but never called within file

Codebase-scope patterns:

[high] Dead exports

- Exported functions with 0 callers anywhere in codebase
- Feature flags always true/false (never toggled in any environment)
- Any publicly accessible code with no consumers

[medium] Stale flags

- Dead flags (feature shipped, flag never removed)

[low] Orphaned configuration

- Configuration options never read
- Dead modules (no imports from any live code path)
  </violations>

<exceptions>
Commented code with explanation (debugging aid). Unused params required by interface contract. Public API entry points. Plugin interfaces. Feature flags controlled externally.
</exceptions>

<threshold>
Flag when code is demonstrably unreachable/unused AND is not a public API entry point, plugin interface, or documented debugging aid.
</threshold>
