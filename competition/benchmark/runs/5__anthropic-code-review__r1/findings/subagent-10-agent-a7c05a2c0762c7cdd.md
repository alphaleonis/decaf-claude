# subagent agent-a7c05a2c0762c7cdd

## Audit Findings — PR #308517 ("Support timing out hung streams")

I read all three guidance files (`AGENTS.md`, root `.github/copilot-instructions.md`, `extensions/copilot/.github/copilot-instructions.md`) and the full diff (5 files: `messagesApi.ts`, `responsesApi.ts`, `fetcherService.ts`, `stream.ts`, new `streamIdleTimeout.spec.ts`). I checked indentation/tabs, naming, quote usage, brace/whitespace style, JSDoc, `any`/`unknown` usage, `readonly` usage, disposal patterns, import hygiene, and the test-assertion "Learnings" note. Most of the diff is compliant (tabs used correctly, no `any`/`unknown` introduced, no duplicated/dangling imports, correct single/double-quote usage, function-keyword export used for the new top-level export, copyright header present in the new test file, test file location matches existing `test/node/` convention for this module).

I found 2 clear violations and 1 lower-confidence one, all in newly-added code:

1. **File**: `extensions/copilot/src/platform/networking/common/fetcherService.ts`
   **Line**: 312 (`export class StreamIdleTimeoutError extends Error {`)
   **Description**: The new `StreamIdleTimeoutError` class has no JSDoc comment, unlike the `SSE_FIRST_CHUNK_TIMEOUT_MS`/`SSE_IDLE_TIMEOUT_MS` constants and the `withStreamIdleTimeout` function immediately surrounding it in the same diff, which do have JSDoc blocks.
   **Guidance violated**: "Use JSDoc style comments for functions, interfaces, enums, and classes" (`.github/copilot-instructions.md`, Comments section) — also stated as "**Comments**: Use JSDoc style for functions, interfaces, enums, and classes" in `extensions/copilot/.github/copilot-instructions.md`.
   **Category**: guidance-adherence

2. **File**: `extensions/copilot/src/platform/networking/test/node/streamIdleTimeout.spec.ts`
   **Line**: 14-18 (`interface ControllableStream<T> { stream: ...; push: ...; close: ...; }`)
   **Description**: The new `ControllableStream<T>` interface's `stream`, `push`, and `close` members are never reassigned after construction but are declared without `readonly`.
   **Guidance violated**: "Use `readonly` whenever possible." (`extensions/copilot/.github/copilot-instructions.md`, Type Management section)
   **Category**: guidance-adherence

3. **File**: `extensions/copilot/src/platform/networking/test/node/streamIdleTimeout.spec.ts`
   **Line**: 66-70 (and the same pattern repeats at 91-95)
   **Description**: The two "throws StreamIdleTimeoutError" tests each use two separate assertions (`assert.strictEqual` + `assert.ok`) inside an `assert.rejects` validator callback instead of a single snapshot-style comparison.
   **Guidance violated**: "Minimize the amount of assertions in tests. Prefer one snapshot-style `assert.deepStrictEqual` over multiple precise assertions, as they are much more difficult to understand and to update." (`.github/copilot-instructions.md`, Learnings section)
   **Category**: guidance-adherence
   (Lower confidence than the other two — only two closely-related assertions on a single error object, so this is closer to the guidance's stated concern than a clear-cut breach, but it is an explicit and directly applicable instruction.)

Things I checked and did **not** flag because they matched established codebase precedent or fell outside the scope of an explicit rule: the one-line `new ReadableStream({ start(c) { ctrl = c; } })` callback body (identical pattern pre-exists at `fetcherService.ts:110`); `SSE_FIRST_CHUNK_TIMEOUT_MS`/`SSE_IDLE_TIMEOUT_MS` naming (SCREAMING_SNAKE_CASE constants are common throughout the codebase, and the naming rules only govern types/functions/properties/locals); `void stream.destroy().catch(() => {})` (idiomatic fire-and-forget from a non-async `setTimeout` callback, not a "Promise/then" chain the async/await rule targets); custom `Error` subclasses without localization (established pattern — over a dozen similar `extends Error` classes exist elsewhere with no `nls` usage); raw `setTimeout`/`clearTimeout` usage (no timer service exists in this codebase; used raw in 21+ other files under `src/platform`). I also confirmed neither `jsdoc/require-jsdoc` nor `@typescript-eslint/prefer-readonly` are enabled in `extensions/copilot/eslint.config.mjs` (only the top-level VS Code `eslint.config.js`, which doesn't govern `extensions/copilot`, has them), so findings 1 and 2 above are not lint-catchable.
