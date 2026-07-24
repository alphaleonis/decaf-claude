Below is the code reviewer subagent's full report, verbatim.

---

## Code Review: "Support timing out hung streams (#308517)"

### Strengths

- **Correct, leak-free timer lifecycle.** The core design in `withStreamIdleTimeout` (`fetcherService.ts:328-375`) is sound. The timer runs *only* while awaiting `iterator.next()`, and `clearTimer()` is called immediately after each chunk resolves (line 356), so the idle window correctly excludes consumer processing time. The `finally` block (lines 366-369) clears the timer and calls `iterator.return?.()` on every exit path — normal completion, early consumer `break`, thrown error, and timeout — so there is no dangling timer or leaked reader lock. I verified `vitest --run` passes all 7 tests.

- **The timeout/completion race is actually well-handled, not just papered over.** I specifically checked whether a chunk could resolve *and* the timer fire in the same turn, producing a "yield a value then throw" bug. It can't: if `reader.read()` resolves with a value, its microtask continuation runs before any timer macrotask, so `clearTimer()` cancels the timer before it fires. When the timer *does* win, `destroy()` → `reader.cancel()` forces the next `read()` to resolve `{done:true}`, so the loop breaks cleanly and throws afterward. The `timedOut`/`isFirstChunk` flag pattern yields the right error message in both the first-chunk and mid-stream cases.

- **Abort genuinely propagates to the socket.** In `stream.ts:323`, `this.body` is the `pipeThrough(TextDecoderStream)` output; cancelling its reader propagates upstream through the transform to `response.body` and aborts the underlying fetch. This is the actual requirement (abort rather than hang), and it's wired correctly.

- **Error surfaces cleanly to consumers.** I traced the throw through `AsyncIterableObject` (`async.ts:2031-2035`): the executor rejection is caught and re-thrown from the consumer's `next()`. No unhandled rejection; the hung stream becomes a visible failed request.

- **Distinct first-chunk vs. idle timeouts** is a thoughtful touch — TTFT legitimately differs from inter-chunk latency, and both windows are covered by dedicated tests using deterministic fake timers.

- **Consistent application** across all three real SSE consumers (`messagesApi.ts:596`, `responsesApi.ts:537`, `stream.ts:323`); the non-streaming `Response.text()` path (`fetcherService.ts:134`) is correctly left unwrapped.

### Issues

#### Critical (Must Fix)
None. The timeout/abort/cleanup logic is correct and the tests pass.

#### Important (Should Fix)

1. **No runtime kill switch or configurability for the timeouts** — `fetcherService.ts:303,310`. The 60s idle and 120s first-chunk values are hardcoded module constants; `withStreamIdleTimeout` takes no override parameter and reads no config/experimentation service. This ships to every user with no way to tune or disable it without a code release. [Inference] A 60s inter-chunk gap could abort a legitimately slow stream (e.g., a reasoning model mid-`thinking` if the proxy stops emitting keep-alive SSE comments, or a long server-side tool call). Given this aborts real connections, a config/experiment gate (even just a feature flag to disable) would be the safe production posture. Recommend threading an optional overrides object through, defaulted to the constants, and reading it from the existing config/experimentation layer at the call sites.

2. **Tests never verify the stream is actually aborted on timeout** — `streamIdleTimeout.spec.ts` (whole file). The two timeout tests assert only that `StreamIdleTimeoutError` is thrown; none assert the core behavior — that `stream.destroy()` / the underlying reader cancellation actually fired. A stub `destroy` that did nothing would still pass every test here. Add a spy (e.g., `vi.spyOn` on the `DestroyableStream` instance's `destroy`, or assert the source `ReadableStream` is cancelled) so the abort — the entire point of the feature — is under test.

3. **Timeout is not classified for retry/telemetry** — a hung connection is a transient, retryable condition, but `StreamIdleTimeoutError` is referenced nowhere outside the module and its test (I grepped the whole `extensions/copilot/src` tree). It flows out as a generic stream failure with no retry handling and no dedicated telemetry counter. At minimum this should emit telemetry so the chosen 60s/120s values can be validated against real traffic; ideally it should be retryable. Confirm this omission is intentional.

#### Minor (Nice to Have)

4. **Rare false-positive on clean completion at the exact deadline** — `fetcherService.ts:371`. If a stream goes idle for ~60s and then the server's clean close arrives in the *same* event-loop tick the timer is due, Node's timers phase runs before the poll (I/O) phase, so `timedOut` gets set and a successful completion is reported as a timeout. The probability is negligible (requires completion within one tick of the boundary after a full idle window), but it's a real edge. Not worth restructuring for; noting for awareness.

5. **Test coverage gaps for lifecycle guarantees** — no test asserts the timer is cleared after normal completion (`expect(vi.getTimerCount()).toBe(0)`), and none asserts that a mid-stream *network error* (`iterator.next()` rejecting) propagates the original error rather than being masked by the timeout path. Both are cheap to add and lock in behavior the implementation currently gets right by construction.

6. **Doc nit** — `fetcherService.ts:300`: "we give it slightly more time" understates a 2x difference (120s vs 60s). Consider "twice as long."

7. **Timer is not `unref()`'d** — `fetcherService.ts:344`. Since it's always cleared promptly this doesn't hold the process open in practice, so it's purely cosmetic; mentioning only for completeness.

### Recommendations

- Thread the timeout values through as optional parameters sourced from config/experimentation, and add a telemetry event on `StreamIdleTimeoutError` before relying on the hardcoded 60s in production. These two together de-risk the rollout far more than any code-logic change.
- Strengthen the test spec with a destroy/cancel spy (issue 2) and the two lifecycle assertions (issue 5); the current suite proves the generator *throws* on time but not that it *aborts*.

### Assessment

**Ready to merge?** With fixes.

**Reasoning:** The timeout/abort/cleanup mechanism is correct, leak-free, race-safe, and cleanly integrated — no correctness blockers, and the tests pass. The gaps are production-safety concerns (no kill switch/telemetry for a feature that aborts live connections) and a test that verifies the error but not the abort itself; I'd want issues 1-3 addressed or explicitly waived before this goes broad.
