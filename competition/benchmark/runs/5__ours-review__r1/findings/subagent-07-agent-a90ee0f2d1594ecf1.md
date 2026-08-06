# subagent agent-a90ee0f2d1594ecf1

## Findings

```json
[
  {
    "file": "extensions/copilot/src/platform/networking/common/fetcherService.ts",
    "line": 346,
    "severity": "Medium",
    "category": "async",
    "issue": "[TS_PROMISES] `void stream.destroy().catch(() => { })` swallows every destroy()/cancel() rejection with zero logging. Per WHATWG streams semantics `reader.cancel()` already marks the stream closed and unblocks any pending `read()` before invoking the underlying source's cancel algorithm, so a rejection here specifically signals that the underlying resource (socket/connection) failed to actually tear down — the one case cleanup diagnostics matter most. Because the catch is empty, a recurring destroy failure (e.g., an already-torn-down transport throwing on cancel) leaves no trace, so a slow connection leak in this fire-and-forget cleanup path is invisible in production.",
    "fix": "Log the destroy() failure at debug/warn level instead of an empty catch, e.g. `.catch(e => logService.debug('withStreamIdleTimeout: destroy failed', e))`, so a genuine cleanup failure is observable without changing the fire-and-forget control flow.",
    "confidence": 50,
    "pre_existing": false
  }
]
```

## Considered But Not Flagged

- **`void stream.destroy().catch(() => {})` — "redundant" combination**: Not redundant. `void` only discards the promise for `no-floating-promises`/type-checker purposes; it does not attach a rejection handler. `.catch()` is what actually prevents a runtime unhandled-rejection. Both serve distinct, necessary purposes.
- **`setTimeout` typed as `ReturnType<typeof setTimeout>`**: Correct idiom for a file where both DOM and Node timer typings may be in scope — avoids the `number` vs `NodeJS.Timeout` mismatch. No defect.
- **Manual iterator-protocol driving (`stream[Symbol.asyncIterator]()` + `.next()`/`.return()`)**: Traced against `DestroyableStream[Symbol.asyncIterator]`'s own try/finally (releases `reader` lock). `.return()` can only be invoked by a consumer while the outer generator is suspended at its `yield`, at which point the inner iterator is *also* suspended at its own `yield` — so `.return()` correctly resumes it as a return completion and runs its `finally` (`reader.releaseLock()`). Verified against the "consumer break releases the underlying reader lock" test (streamIdleTimeout.spec.ts:142-158). No lock leak, no double-run of cleanup (a second `.return()`/`.next()` on an already-closed generator is a documented no-op).
- **`timedOut`/`isFirstChunk` closure mutation and "stale read"**: JS is single-threaded; the timer callback's synchronous write to `timedOut` always happens-before any later read, since a macrotask (the timer) cannot interleave with a running synchronous continuation. `clearTimer()` always runs synchronously immediately after `await iterator.next()` resolves, before any queued timer macrotask can fire, so there is no window where a legitimate completion race gets misclassified as a timeout. No hazard.
- **Trailing `if (timedOut) throw` after the `try/finally` interacting with `iterator.return()`/consumer break**: When a consumer calls `.return()` (early break), the generator resumes at `yield` with a *return* completion; after the `finally` block runs, that return completion continues propagating and the function returns without reaching the trailing `if (timedOut) throw` line — this is correct: the timeout-error path should only fire when the loop exits via natural exhaustion (`result.done`), not via consumer-driven early return. Confirmed this is the only way the control flow can behave given generator return-completion semantics.
- **Timeout-triggered destroy() vs. underlying `reader.read()` rejecting**: Per spec, `reader.cancel()` resolves pending reads with `{done: true}` rather than rejecting them, which is why the implementation can rely on `result.done` (not a catch) to detect the destroy-induced unblock. Consistent with the "throws StreamIdleTimeoutError" tests.
- **Genuine network error path (`iterator.next()` rejects for a non-timeout reason)**: Propagates correctly — `finally` still runs (`iterator.return?.()` becomes a no-op since the inner generator already self-closed via its own `finally` on throw), then the original error re-throws, skipping the trailing `if (timedOut) throw`, so a real error is never masked as `StreamIdleTimeoutError`.
- **`AsyncGenerator<T>` return type vs. `DestroyableStream<T>` (`AsyncIterable<T>`) at call sites**: `withStreamIdleTimeout`'s parameter is explicitly typed `DestroyableStream<T>` (not the narrower `AsyncIterable<T>`) so it can call `.destroy()`/`[Symbol.asyncIterator]()` directly; all three call sites (`stream.ts:323`, `messagesApi.ts:596`, `responsesApi.ts:537`) pass concrete `DestroyableStream<Uint8Array>`/`DestroyableStream<string>` values with no cast. Type-sound, no `any`/`as` involved.
- **Double `destroy()`/`cancel()` calls from the caller's own cleanup path (`AsyncIterableObject`'s second callback, or `SSEProcessor`'s `finally { await this.cancel(); }`) stacking with `withStreamIdleTimeout`'s internal destroy-on-timeout**: Pre-existing double-cleanup pattern (unchanged by this diff — the diff only wraps the iterable, `for await` still triggers the same `.return()`/cleanup contract as before). `DestroyableStream.destroy()` is idempotent (second call falls through to `this.stream.cancel()` once `this.reader` is `undefined`), so no functional regression.
