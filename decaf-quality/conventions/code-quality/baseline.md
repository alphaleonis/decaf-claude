# Baseline Code Quality

Quality concerns detectable from the current codebase state. These are checked at planning time before writing new code.

## 1. Naming Precision

<principle>
A name is micro-documentation. It should predict behavior accurately enough that reading the implementation confirms rather than surprises.
</principle>

Detect: Does the name accurately describe what this does? Would a reader's mental model, built from the name alone, match actual behavior?

<grep-hints>
Terms that sometimes indicate naming issues (starting points, not definitive):
`Manager`, `Handler`, `Utils`, `Helper`, `Data`, `Info`, `process`, `handle`, `do`
</grep-hints>

<violations>
Illustrative patterns (not exhaustive -- similar violations exist):

[high] Name-behavior mismatch

- Names describing HOW not WHAT (e.g., loopOverItems -> processOrders)
- Verbs that lie (e.g., get that mutates, validate that parses)
- Any name that would cause surprise when implementation is read

[medium] Abstraction leakage

- Implementation details in public API names
- Vague umbrella terms (e.g., Manager, Handler, Utils, Helper, Data, Info)

[low] Cognitive friction

- Negated booleans (e.g., isNotValid -> isInvalid, disableFeature -> featureEnabled)
  </violations>

<exceptions>
Generic names in genuinely generic contexts (e.g., item in a generic collection, T in type params). Test: would a specific name add signal or just noise?
</exceptions>

<threshold>
Flag only when name actively misleads. Imperfect names that are still accurate are style preferences.
</threshold>

## 2. Function Composition

<principle>
A function should do one thing that can be described in a single sentence. When description requires "and", the function likely needs splitting.
</principle>

Detect: Can I describe this function's purpose in one sentence without using "and"?

<grep-hints>
Structural indicators (starting points, not definitive):
Functions >50 lines, parameter counts >4
</grep-hints>

<violations>
Illustrative patterns (not exhaustive -- similar violations exist):

[high] Responsibility diffusion

- God functions (multiple unrelated responsibilities)
- Long parameter lists (4+ params signals missing concept)
- Any function requiring multiple sentences to describe its purpose

[medium] Structural complexity

- Deep nesting (3+ levels of conditionals)
- Mixed abstraction levels (high-level orchestration mixed with low-level details)

[low] Interface friction

- Boolean parameters that fork behavior (consider splitting into two functions)
  </violations>

<exceptions>
Long functions that do one thing linearly (e.g., state machine, parser). Nesting depth from error handling.
</exceptions>

<threshold>
Flag when function has multiple unrelated responsibilities. Length alone is not a smell.
</threshold>

## 3. Boolean Expression Complexity

<principle>
A boolean expression should be readable at a glance. If it requires mental evaluation to understand, it needs simplification or naming.
</principle>

Detect: Can I understand this boolean expression without tracing through it mentally?

<grep-hints>
Pattern indicators (starting points, not definitive):
`and.*and`, `or.*or`, `&&.*&&`, `||.*||`, `not.*not`, `!.*!`
</grep-hints>

<violations>
Illustrative patterns (not exhaustive -- similar violations exist):

[medium] Cognitive overload

- Multi-clause expressions (3+ AND/OR terms -> extract named predicate)
- Negated compound conditions (e.g., not (a and b) -> clearer positive form)
- Any expression requiring paper/mental tracing to evaluate

[low] Ambiguity

- Mixed AND/OR without parentheses clarifying precedence
- Double/triple negatives (e.g., if not disabled, if not is_invalid)
  </violations>

<exceptions>
Complex conditions with clear structure and comments explaining the logic.
</exceptions>

<threshold>
Flag when expression requires mental evaluation to understand. Well-commented complex conditions are acceptable.
</threshold>

## 4. Missing Domain Modeling

<principle>
Domain concepts should be explicit in code, not hidden in raw comparisons. When the same concept is checked multiple ways, it belongs in a domain object.
</principle>

Detect: Are domain concepts hiding in raw conditions? Is the same business concept checked via primitive comparison in multiple places?

<grep-hints>
Pattern indicators (starting points, not definitive):
`== 'admin'`, `== "admin"`, `status ==`, `role ==`, `type ==`, magic numbers
</grep-hints>

<violations>
Illustrative patterns (not exhaustive -- similar violations exist):

[high] Hidden domain logic

- Domain predicates in raw conditions (e.g., user.role == 'admin' -> user.can_edit())
- Magic value comparisons (e.g., status == 3 -> Status.APPROVED)
- Any business concept expressed only through primitive comparison

[medium] Implicit modeling

- String comparisons for state (e.g., mode == 'active' -> enum)
- Business rules buried in conditions (extract to domain object method)
  </violations>

<exceptions>
Explicit comparisons in domain layer implementation itself. Config values compared once at startup.
</exceptions>

<threshold>
Flag when same domain concept is checked via raw comparison in 2+ places.
</threshold>

## 5. Type-Based Branching

<principle>
Type dispatch scattered across code indicates missing polymorphism. When you branch on type in multiple places, the type itself should carry the behavior.
</principle>

Detect: Is type-checking being used where polymorphism would be cleaner? Does the same type dispatch appear in multiple locations?

<grep-hints>
Pattern indicators (starting points, not definitive):
`isinstance`, `typeof`, `instanceof`, `hasattr`, `in dict`, `.type ==`
</grep-hints>

<violations>
Illustrative patterns (not exhaustive -- similar violations exist):

[high] Scattered dispatch

- isinstance/typeof chains (3+ branches -> polymorphism candidate)
- Same type dispatch appearing in multiple locations

[medium] Implicit dispatch

- Attribute-presence checks (e.g., hasattr/in dict as type dispatch)

[low] Missing abstraction

- Duck typing conditionals that should be protocols/interfaces
  </violations>

<exceptions>
Single isinstance check for input validation. Type narrowing for type safety.
</exceptions>

<threshold>
Flag when same type dispatch appears in 2+ places. Single-use type checks are often appropriate.
</threshold>

## 6. Control Flow Smells

<principle>
Control flow should reveal intent, not obscure it. When following execution requires significant mental effort, the structure needs simplification.
</principle>

Detect: Is the control flow harder to follow than necessary? Would a reader need to trace through multiple branches to understand behavior?

<grep-hints>
Pattern indicators (starting points, not definitive):
`elif.*elif.*elif`, `switch`, `case`, `? :.*? :`, ternary chains
</grep-hints>

<violations>
Illustrative patterns (not exhaustive -- similar violations exist):

[high] Excessive branching

- Long if/elif chains (5+ branches -> lookup table or strategy pattern)
- Any branching structure that requires tracing to understand

[medium] Obscured flow

- Nested ternaries (2+ levels -> extract to named variables)
- Early-return candidates buried in nested else branches

[low] Hidden complexity

- Conditional assignment cascades
- Implicit else branches hiding edge cases
  </violations>

<exceptions>
Exhaustive pattern matching. State machines with explicit states.
</exceptions>

<threshold>
Flag when control flow obscures intent. Explicit branching for documented cases is acceptable.
</threshold>

## 7. State and Flags

<principle>
Boolean flags that interact create implicit state machines. When understanding state requires tracking multiple flags, make the state machine explicit.
</principle>

Detect: Are boolean flags creating implicit state machines? Do flags interact in ways that require mental tracking?

<grep-hints>
Pattern indicators (starting points, not definitive):
`is_.*=`, `has_.*=`, `_flag`, `_state`, multiple boolean assignments
</grep-hints>

<violations>
Illustrative patterns (not exhaustive -- similar violations exist):

[high] Implicit state machines

- Boolean flag tangles (3+ flags interacting = implicit state machine)
- Any flag interaction requiring mental state tracking

[medium] Order dependencies

- Stateful conditionals depending on mutation order

[low] Defensive complexity

- Defensive null chains (e.g., x and x.y and x.y.z -> optional chaining or null object)
  </violations>

<exceptions>
Single boolean for simple on/off state. Builder pattern flags.
</exceptions>

<threshold>
Flag when flags interact in ways that require mental state tracking. Independent flags are fine.
</threshold>

## 8. Conditional Anti-Patterns

<principle>
Conditions should express intent directly. When a simpler form exists that preserves meaning, the complex form is an anti-pattern.
</principle>

Detect: Is there a simpler way to express this condition that preserves the same meaning?

<grep-hints>
Pattern indicators (starting points, not definitive):
`if.*return True.*else.*return False`, `try:.*except:.*pass`, `and do_`
</grep-hints>

<violations>
Illustrative patterns (not exhaustive -- similar violations exist):

[medium] Verbose patterns

- if cond: return True else: return False (just return cond)
- Exception-based control flow (try/except as if/else)
- Any condition with a simpler equivalent form

[low] Subtle complexity

- Short-circuit side effects (e.g., cond and do_thing())
- Yoda conditions without clear benefit (e.g., if 5 == x)
  </violations>

<exceptions>
Exception handling for actual exceptional conditions. Short-circuit for lazy evaluation.
</exceptions>

<threshold>
Flag mechanical anti-patterns only. Intent-preserving variations are style preferences.
</threshold>

## 9. Dependency Injection

<principle>
Business logic should be testable without network, disk, or database. Hard-coded dependencies make code untestable and tightly coupled.
</principle>

Detect: Can I test this function in isolation without mocking infrastructure? Are dependencies injected or hard-coded?

<grep-hints>
Pattern indicators (starting points, not definitive):
`datetime.now`, `time.time`, `os.environ`, `open(`, `requests.`, `http.`
</grep-hints>

<violations>
Illustrative patterns (not exhaustive -- similar violations exist):

[high] Untestable coupling

- Hard-coded dependencies (e.g., new Date() inline -> inject clock)
- Global state access (avoid or inject)
- Any business logic that requires infrastructure to test

[medium] Mixed concerns

- Side effects mixed with computation (separate pure logic from effects)
- Concrete class dependencies (depend on interface, not implementation)

[low] Configuration coupling

- Environment coupling (reads env vars directly -> inject config)
- Time-dependent logic (inject clock for testability)
  </violations>

<exceptions>
Entry points that wire dependencies. Test utilities. Scripts meant to run directly.
</exceptions>

<threshold>
Flag when untestable code is in business logic. Infrastructure code at boundaries is expected to have dependencies.
</threshold>

## 10. Type Design

<principle>
Domain concepts deserve their own types. Primitives that cross boundaries without validation invite bugs; value objects with validation prevent them.
</principle>

Detect: What domain concepts are represented as primitives? Do primitives cross API boundaries without validation?

<grep-hints>
Pattern indicators (starting points, not definitive):
`str` for IDs, `float` for money, `dict` passed through call chain, `Any`, `object`
</grep-hints>

<violations>
Illustrative patterns (not exhaustive -- similar violations exist):

[high] Missing domain types

- Primitive obsession (e.g., userId as string -> UserId type with validation)
- Missing value objects (e.g., money as float -> Money(amount, currency))
- Any domain concept crossing API boundary as primitive

[medium] Weak typing

- Stringly-typed data (JSON strings -> typed objects)
- Leaky abstractions (callers must know implementation details)

[low] Type proliferation

- Optional explosion (many nullable fields -> consider separate types for states)
  </violations>

<exceptions>
Primitives in internal implementation. Serialization boundaries. Performance-critical paths.
</exceptions>

<threshold>
Flag when primitives cross API boundaries without validation. Internal use of primitives is acceptable.
</threshold>

## 11. Error Handling

<principle>
Errors should preserve context and reach appropriate handlers. Swallowed or generic catches lose information; errors at wrong levels confuse callers.
</principle>

Detect: What happens if this operation fails? Is error information preserved and routed appropriately?

<grep-hints>
Pattern indicators (starting points, not definitive):
`except:`, `catch (`, `catch(`, `pass`, `# TODO`, `raise Error(`
</grep-hints>

<violations>
Illustrative patterns (not exhaustive -- similar violations exist):

[high] Information loss

- Swallowed exceptions (empty catch blocks)
- Generic catches (e.g., catch Exception -> catch specific errors)
- Any error handling that loses diagnostic information

[medium] Wrong abstraction

- Errors at wrong abstraction level (low-level errors leaking to callers)

[low] Missing context

- raise Error('failed') -> raise Error(f'order {id}: {reason}')
  </violations>

<exceptions>
Generic catch at top-level with logging. Intentionally swallowed expected errors with comment.
</exceptions>

<threshold>
Flag when error handling obscures or loses information. Documented catch-all with logging is acceptable.
</threshold>

## 12. Modern Idioms

<principle>
Modern language features exist to simplify common patterns. When older patterns persist unnecessarily, they add cognitive load without benefit.
</principle>

Detect: Is there a newer language feature that would simplify this code? Is the project's language version being underutilized?

<grep-hints>
Pattern indicators (starting points, not definitive):
`for i in range(len(`, `+ str(`, `.format(`, callback patterns, `null` checks
</grep-hints>

<violations>
Illustrative patterns (not exhaustive -- similar violations exist):

[medium] Outdated patterns

- Old iteration patterns (e.g., manual index loops -> for-each, enumerate)
- Deprecated API usage
- Any pattern with a simpler modern equivalent

[low] Missing features

- Missing language features (e.g., no destructuring, no pattern matching)
- Legacy patterns (e.g., callbacks -> async/await)
- Outdated idioms (e.g., string concatenation -> f-strings/templates)
- Manual null checks (-> optional chaining, null coalescing)
  </violations>

<exceptions>
Intentional use of older patterns for compatibility. Performance-critical code avoiding allocations.
</exceptions>

<threshold>
Flag when modern idiom is clearly better AND available in the project's language version. Do not flag style preferences.
</threshold>

## 13. Readability

<principle>
Code should be understandable in isolation. When understanding requires external lookup or tribal knowledge, the code needs clarification.
</principle>

Detect: Can I understand this code without reading other files or asking someone? Is intent clear from the code itself?

<grep-hints>
Pattern indicators (starting points, not definitive):
Boolean literals in function calls, magic numbers, unexplained constants
</grep-hints>

<violations>
Illustrative patterns (not exhaustive -- similar violations exist):

[high] Obscured intent

- Boolean trap (e.g., fn(True, False) -> fn(enabled=True, debug=False))
- Any call where argument meaning requires looking up the function signature

[medium] Magic values

- Magic numbers/strings (e.g., 42 -> MAX_RETRIES = 42)
- Positional args where named params would clarify intent

[low] Dense expressions

- Dense expressions (e.g., nested ternaries -> named intermediate variables)
- Missing WHY comments on non-obvious decisions
- Implicit ordering dependencies between calls (document or make explicit)
  </violations>

<exceptions>
Well-known constants (0, 1, -1, 100). Boolean in obviously-named function (e.g., setEnabled(true)).
</exceptions>

<threshold>
Flag when meaning requires external lookup. Self-evident code needs no comments.
</threshold>

## 14. Documentation Staleness

<principle>
Documentation that contradicts code is worse than no documentation. Stale docs mislead readers and cause bugs.
</principle>

Detect: Does the documentation contradict the code? Are there claims in docs that the code structurally violates?

<grep-hints>
Pattern indicators (starting points, not definitive):
Docstrings with parameter names, @param, @return, TODO, FIXME
</grep-hints>

<violations>
Illustrative patterns (not exhaustive -- similar violations exist):

[high] Active contradictions

- Parameter name in docstring not in function signature
- Docstring type conflicts with type annotation (when annotation exists)
- Any documentation making claims the code structurally contradicts

[medium] Stale claims

- Docstring describes return value that code never returns
- Comment contains strong claim ("always", "never", "must") AND code structurally contradicts it

[low] Orphaned references

- TODO/FIXME referencing completed or removed work
  </violations>

<exceptions>
Incomplete documentation. Missing docs. Outdated style in docs.
</exceptions>

<threshold>
Flag only when documentation is demonstrably incorrect, not merely incomplete. Incorrect documentation causes hallucinations.
</threshold>

## 15. Test Quality as Documentation

<principle>
Tests document expected behavior. When test names don't communicate what behavior they verify, they fail as documentation.
</principle>

Detect: Do tests communicate expected behavior? Can I understand what's being tested from the test name alone?

<grep-hints>
Pattern indicators (starting points, not definitive):
`test_works`, `test_ok`, `test_success`, `test_case_`, `test_1`, `assert True`
</grep-hints>

<violations>
Illustrative patterns (not exhaustive -- similar violations exist):

[high] Uninformative tests

- Test name matches low-information pattern (e.g., test_works, test_ok, test_success, test_case_1)
- Test contains 0 assertions
- Any test where the name gives no behavioral information

[medium] Weak naming

- Test name shorter than 3 tokens (excluding test\_ prefix)
- Test name describes implementation, not behavior

[low] Test smells

- Test only asserts True, None, or trivial values
- Multiple similar test functions with minor input variations (use parameterized/table-driven)
  </violations>

<exceptions>
Tests referencing ticket numbers (e.g., TEST-1234, JIRA-567) for traceability. Smoke tests named test_works.
</exceptions>

<threshold>
Flag when test name gives no behavioral information AND is not a ticket/regression reference.
</threshold>

## 16. Generated and Vendored Code Awareness

<principle>
Non-maintainable code (generated, vendored) must be clearly marked. Without provenance documentation, maintainers may try to modify code that should be regenerated.
</principle>

Detect: Is non-maintainable code clearly marked in CLAUDE.md? Can a maintainer tell which code is generated or vendored?

<grep-hints>
Pattern indicators (starting points, not definitive):
`_generated`, `_pb`, `.pb.go`, `vendor/`, `third_party/`, `node_modules/`
</grep-hints>

<violations>
Illustrative patterns (not exhaustive -- similar violations exist):

[high] Missing provenance

- Generated files missing regeneration command in CLAUDE.md
- Vendored directories missing upstream source in CLAUDE.md
- Any generated/vendored code without documentation of origin

[medium] Unclear ownership

- External libraries copied into repo without provenance documentation
  </violations>

<exceptions>
Generated files with regeneration command documented. Vendored code with clear upstream reference.
</exceptions>

<threshold>
Flag when file/directory matches generation patterns (e.g., *.pb.go, *_generated.*, vendor/, third_party/) AND CLAUDE.md lacks corresponding entry explaining provenance.
</threshold>

## 17. Schema-Code Coherence

<principle>
Schema and code must stay synchronized. Fields referenced in code but absent from schema (or vice versa) indicate drift that causes runtime errors.
</principle>

Detect: Does code reference schema fields that don't exist? Are there schema fields unused in any code path?

<grep-hints>
Pattern indicators (starting points, not definitive):
Schema file extensions (.proto, .graphql, .json schema), field access patterns
</grep-hints>

<violations>
Illustrative patterns (not exhaustive -- similar violations exist):

[high] Schema drift

- Code references field not in schema definition
- Schema field unused in any code path (dead field)
- Any mismatch between schema definition and code usage

[medium] Type drift

- Type mismatch between schema and code representation
  </violations>

<exceptions>
Intentional divergence documented with :SCHEMA: marker. Fields used only in specific deployment configs.
</exceptions>

<threshold>
Flag when field name in code has 0 matches in corresponding schema file, or schema field has 0 references in codebase.
</threshold>

Intent marker: Use `:SCHEMA:` to suppress for intentional divergence (e.g., `:SCHEMA: field 'legacy_id' unused; migration pending`).
