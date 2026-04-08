---
name: tdd
description: Test-driven development with red-green-refactor loop. Use when user wants to build features or fix bugs using TDD, mentions "red-green-refactor", wants integration tests, or asks for test-first development.
---

# Test-Driven Development

## Philosophy

**Core principle**: Tests should verify behavior through public interfaces, not implementation details. Code can change entirely; tests shouldn't.

**Good tests** are integration-style: they exercise real code paths through public APIs. They describe _what_ the system does, not _how_ it does it. A good test reads like a specification - "user can checkout with valid cart" tells you exactly what capability exists. These tests survive refactors because they don't care about internal structure.

**Bad tests** are coupled to implementation. They mock internal collaborators, test private methods, or verify through external means (like querying a database directly instead of using the interface). The warning sign: your test breaks when you refactor, but behavior hasn't changed. If you rename an internal function and tests fail, those tests were testing implementation, not behavior.

See [tests.md](tests.md) for examples and [mocking.md](mocking.md) for mocking guidelines.

## Anti-Pattern: Horizontal Slices

**DO NOT write all tests first, then all implementation.** This is "horizontal slicing" - treating RED as "write all tests" and GREEN as "write all code."

This produces **crap tests**:

- Tests written in bulk test _imagined_ behavior, not _actual_ behavior
- You end up testing the _shape_ of things (data structures, function signatures) rather than user-facing behavior
- Tests become insensitive to real changes - they pass when behavior breaks, fail when behavior is fine
- You outrun your headlights, committing to test structure before understanding the implementation

**Correct approach**: Vertical slices via tracer bullets. One test → one implementation → refactor → repeat. Each test responds to what you learned from the previous cycle. Because you just wrote the code, you know exactly what behavior matters and how to verify it.

```
WRONG (horizontal):
  RED:   test1, test2, test3, test4, test5
  GREEN: impl1, impl2, impl3, impl4, impl5

RIGHT (vertical):
  RED→GREEN→REFACTOR: test1→impl1→clean up
  RED→GREEN→REFACTOR: test2→impl2→clean up
  RED→GREEN→REFACTOR: test3→impl3→clean up
  ...
```

## Workflow

### 0. Detect project language, conventions, and context

Before writing anything:

- Identify the project language and its idiomatic test patterns
- Identify the test framework already in use (or the standard one for the language)
- Identify the **test command** for the project (e.g., `dotnet test`, `go test ./...`, `cargo test`, `npm test`)
- Note existing test structure and naming conventions in the project
- Explore the codebase to understand existing modules, patterns, and similar features — so you don't duplicate or conflict with what's already there

<language-idioms>
Apply idiomatic patterns for the detected language:

- **C#**: xUnit/NUnit/MSTest. Use `[Fact]`/`[Theory]` (xUnit) or equivalent. Interfaces for DI. `async Task` for async tests.
- **Go**: Built-in `testing` package. Prefer table-driven tests with `t.Run()` subtests. Interfaces are implicit — test doubles just satisfy the interface. No mocking framework needed.
- **Rust**: Built-in `#[test]` in a `#[cfg(test)]` module. Use `assert!`/`assert_eq!`/`assert_ne!`. Traits + generics for DI. Integration tests go in `tests/` directory. The compiler already catches many classes of bugs — focus tests on logic and behavior, not type safety.

Follow whatever conventions the project already uses. If the project has no tests yet, use the language's standard/most common framework.
</language-idioms>

### 1. Planning

Before writing any code:

- [ ] Confirm with user what interface changes are needed
- [ ] Confirm with user which behaviors to test (prioritize)
- [ ] Identify opportunities for [deep modules](deep-modules.md) (small interface, deep implementation)
- [ ] Design interfaces for [testability](interface-design.md)
- [ ] List the behaviors to test (not implementation steps)
- [ ] Get user approval on the plan

Ask: "What should the public interface look like? Which behaviors are most important to test?"

**You can't test everything.** Confirm with the user exactly which behaviors matter most. Focus testing effort on critical paths and complex logic, not every possible edge case.

### 2. Tracer Bullet

Write ONE test that confirms ONE thing about the system:

```
RED:   Write test for first behavior → run tests → verify it FAILS
GREEN: Write minimal code to pass → run tests → verify it PASSES
REFACTOR: Clean up while green → run tests → verify still green
```

This is your tracer bullet - proves the path works end-to-end.

**Always run the test command** to verify each state transition. Do not assume — confirm.

### 3. Incremental Loop

For each remaining behavior:

```
RED:     Write next test → run tests → verify it FAILS
GREEN:   Minimal code to pass → run tests → verify it PASSES
REFACTOR: Clean up if needed → run tests → verify still green
```

Rules:

- One test at a time
- Only enough code to pass current test
- Don't anticipate future tests
- Keep tests focused on observable behavior
- Refactor after each GREEN, not only at the end

### 4. Handling unexpected results

<unexpected-red>
**Test passes when it should fail (RED fails):**
The behavior already exists, or the test is wrong. Investigate:
- If the behavior already exists, the test is validating existing code — that's useful, but don't write new implementation. Move on to the next behavior.
- If the test is wrong (not actually testing what you intended), fix the test until it properly fails for the right reason.
</unexpected-red>

<unexpected-green>
**Test still fails after implementation (GREEN fails):**
- Read the failure message carefully — it often points directly to the issue.
- Check whether the test is asserting on the right thing (did the interface change during implementation?).
- Check whether the implementation is wired up correctly (is the test reaching the new code?).
- If the fix isn't obvious, narrow the problem: does the implementation work in isolation? Is it a test setup issue?
- Do not modify the test to make it pass unless the test itself is wrong. The test defines the behavior — the implementation must satisfy it.
</unexpected-green>

### 5. Final Review

After all behaviors are implemented, do a final review pass for [refactor candidates](refactoring.md):

- [ ] Look across all new code for duplication that only became visible after multiple cycles
- [ ] Deepen modules (move complexity behind simple interfaces)
- [ ] Consider what the new code reveals about existing code
- [ ] Run tests after each refactor step

**Never refactor while RED.** Get to GREEN first.

## Checklist Per Cycle

```
[ ] Test describes behavior, not implementation
[ ] Test uses public interface only
[ ] Test would survive internal refactor
[ ] Tests actually run and confirm RED then GREEN
[ ] Code is minimal for this test
[ ] No speculative features added
[ ] Refactored while green (if needed)
```
