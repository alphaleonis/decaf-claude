# subagent agent-a06829b4870b214d7

Depth: deep — external-API streaming integration; new `withStreamIdleTimeout` generator plus three SSE call sites, watchdog/teardown/cancellation seams. I traced the generator's completion semantics, the `DestroyableStream` reader/cancel interaction, and each call site's error surfacing.

I verified the mechanically load-bearing questions from the brief and they hold up:

- **Cancel-mid-await resolves, not rejects.** `destroy()` → `reader.cancel()` fulfills the pending `read()` with `{done:true}` (WHATWG streams), so the loop breaks normally, reaches the post-`finally` `throw`, and `StreamIdleTimeoutError` is not masked by a cancel rejection.
- **Post-loop `throw` is delivered on the timeout path and skipped on the consumer-return path.** Timeout ends the loop via natural `done:true` break → normal fall-through runs the `throw`. Consumer `break`/`return`/`maybeCancel` drives the generator via `.return()`, which runs `finally` then completes without reaching the throw (correct: `timedOut` is false there anyway, since the timer only runs during `await next()` and is cleared before each `yield`).
- **`isFirstChunk`/`timeoutMs` message is always consistent.** On a first-chunk timeout the `isFirstChunk=false` line is never reached (break precedes it), so the reported `timeoutMs` matches the timer that actually fired.
- **Error surfacing at call sites is intact.** `AsyncIterableObject`'s executor wrapper (`async.ts` 2031-2036) catches the throw and routes it to `reject()`, so the consumer's `next()` rethrows it — no lost/unhandled rejection. The `_onReturn` `response.body.destroy()` is not called on the error path, and a second `destroy()` is idempotent (reader already released → `stream.cancel()` no-op). No double-cancel crash.

I found no high-confidence correctness defect introduced by the change. One concrete emergent observability effect is worth flagging.

```json
[
  {
    "file": "src/platform/networking/common/fetcherService.ts",
    "line": 346,
    "severity": "Low",
    "category": "other",
    "issue": "[ADV_COMPOSITION] watchdog fires -> stream.destroy() calls reader.cancel() with no reason -> counting TransformStream cancel(undefined) -> hung-stream teardown recorded as responseStreaming outcome:'cancel', indistinguishable from a user cancel",
    "fix": "Pass a distinguishing reason through the teardown (e.g. stream.destroy(new StreamIdleTimeoutError(...)) forwarded to reader.cancel(reason)), so Response's transformer.cancel reports outcome:'error' for idle timeouts and reliability telemetry does not undercount hung endpoints as cancellations.",
    "confidence": 50,
    "pre_existing": false
  }
]
```

## Considered But Not Flagged

- **StreamIdleTimeoutError becoming an unhandled rejection at the AsyncIterableObject call sites (messagesApi/responsesApi):** Refuted. `async.ts:2031-2036` wraps the executor in try/catch → `this.reject(err)`; the consumer's `next()` rethrows `_error`. The error surfaces cleanly.

- **Cancel rejection masking the timeout error:** Refuted. Per WHATWG streams, `ReadableStreamCancel` fulfills pending reads with `{done:true}` rather than rejecting; the loop breaks and the post-`finally` throw runs. Confirmed by the passing spec `throws StreamIdleTimeoutError when first chunk never arrives`.

- **Wrong `timeoutMs`/message when timeout fires after N chunks:** Refuted. `isFirstChunk` retains the value the armed timer used because the `done:true` break precedes the `isFirstChunk=false` assignment. Spec `throws ... when a subsequent chunk stalls` asserts the `inactivity` message.

- **Race: chunk arrives exactly at the deadline, gets yielded, then a spuriously-fired timer tears the stream down and throws a false timeout:** Refuted. The `read()` resolution is a microtask and drains before the `setTimeout` macrotask, so `clearTimer()` cancels the pending timer before it can run. If the timer macrotask genuinely precedes the chunk-delivery macrotask, the timeout is legitimate (chunk not yet delivered to us).

- **`releaseLock()` throwing on a pending read when `iterator.return()` runs in `finally`:** Refuted for this environment. `iterator.return()` is only invoked from `withStreamIdleTimeout`'s `finally` when the consumer returns early — at which point the underlying `read()` has already resolved (a value was yielded), so there is no pending read. Modern Node also permits `releaseLock()` with pending reads.

- **Double `destroy()` (watchdog teardown + AsyncIterableObject `_onReturn`):** Refuted as a crash. `_onReturn` is not invoked on the error/throw path (only on consumer `.return()`), and a second `destroy()` after the reader is released falls to a no-op `stream.cancel()`.

- **Hung stream now throws where it previously hung indefinitely, and `StreamIdleTimeoutError` is not classified by `isAbortError`:** This is the intended behavior of the change (surface a specific error instead of hanging). Whether downstream retry logic treats it as retryable and could re-arm 2-minute first-chunk waits is a plausible cascade, but I could not make the retry-amplification concrete from the reviewed files (no retry decision on this error path is in reach), so it stays below the reporting bar.

### Probe Requests
None required; conclusions were reachable from the source and the passing spec. The single Low finding could be confirmed by an operator running the existing suite with a spy on `_reportEvent` to observe the `outcome:'cancel'` on an idle-timeout teardown, but that is optional given the mechanical trace.
