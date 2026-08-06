# subagent agent-ac5485819cd526999

Depth: deep — external-API SSE streaming (model endpoints) is a high-risk integration domain; new watchdog generator + `DestroyableStream` cancel semantics + 3 call sites traced end-to-end.

I read the new `withStreamIdleTimeout` and `DestroyableStream` in `fetcherService.ts`, and all three consumers: `stream.ts` (`processSSEInner` + `maybeCancel`), `messagesApi.ts`, `responsesApi.ts`.

Assumption inventory (what the change assumes):
- Every network chunk means the model is making progress (so resetting the timer per chunk is safe).
- `reader.cancel()` from the timer makes the pending `read()` resolve `{done:true}` (not reject) — so `StreamIdleTimeoutError` is the error the consumer sees.
- The `finally` cleanup (`iterator.return()`) completes promptly after the timer is cleared.
- Early-break (`[DONE]`, `maybeCancel`) unwinds cleanly against the wrapper's own timer.

Key results of tracing: the timer races the prompt asked about are actually sound — if `read()` resolves first the timer is cleared in the same synchronous run before any macrotask can fire; if the timer fires first, `cancel()` forces the pending read to `done:true`, so a real chunk and `timedOut=true` cannot both come from one `await` (the "stuck flag yields a good chunk then spuriously throws" scenario collapses). Per WHATWG semantics `cancel()` resolves the pending read `done:true`, so `StreamIdleTimeoutError` is what surfaces. What does not hold up is the per-chunk reset against a dribbling stream, and the unprotected cleanup path.

```json
[
  {
    "file": "src/platform/networking/common/fetcherService.ts",
    "line": 354,
    "severity": "High",
    "category": "resource-management",
    "issue": "[ADV_ABUSE] Model backend/proxy emits an SSE keepalive comment byte (e.g. ':\\n') every ~30-59s but never produces completion tokens → each byte-level chunk hits clearTimer (line 356) and restarts the watchdog → the idle timeout never fires → the exact 'hung stream' the PR targets streams forever, holding the socket, the AsyncIterableObject, and the user's chat request open with no output and no error.",
    "fix": "Add an absolute wall-clock cap in addition to the per-chunk idle timer (e.g. a max total-stream deadline, or track time-since-last-*meaningful*-chunk at the SSE layer rather than raw bytes), so trickle/keepalive traffic cannot indefinitely defeat the watchdog.",
    "confidence": 75,
    "pre_existing": false
  },
  {
    "file": "src/platform/networking/common/fetcherService.ts",
    "line": 368,
    "severity": "Medium",
    "category": "async",
    "issue": "[ADV_CASCADE] Server sends [DONE] then keeps the socket open without closing → processSSEInner does `return` (stream.ts:342) → for-await calls withStreamIdleTimeout.return() → finally clears the timer THEN `await iterator.return?.()`; the DestroyableStream generator is suspended at a pending reader.read() (its finally only releaseLock()s, never cancels), and an async generator's .return() cannot interrupt an in-flight await → cleanup hangs with the watchdog already cleared → processSSE.finally/this.cancel() never runs, socket leaks, the iterable never settles (request stuck 'in progress').",
    "fix": "On abnormal/early unwind, destroy()/cancel the DestroyableStream (force the pending read to resolve) before or instead of awaiting iterator.return(), or guard the return() with a bounded timeout so cleanup cannot block on a never-closing socket.",
    "confidence": 50,
    "pre_existing": true
  }
]
```

## Considered But Not Flagged

- **Timer fires microseconds before `clearTimer` on a real chunk → stale `timedOut` yields a valid chunk then throws.** Falls apart: if `read()` resolved, its await-resumption microtask runs before the timer macrotask and clears the timer; if the timer wins, `cancel()` forces the read to `done:true` and no real chunk is yielded. A chunk and `timedOut=true` can't both come from one `await`.
- **Normal `done:true` racing the timer → spurious StreamIdleTimeoutError on a completed stream.** For the timer to fire, ≥timeout of genuine idle must have elapsed, so throwing is not actually spurious; and the `[DONE]` path exits via `.return()` (skipping the post-loop `if (timedOut) throw`), not via `break`.
- **On genuine timeout, `iterator.next()` rejects with a raw abort/cancel error, skipping `if (timedOut) throw` so consumers never see StreamIdleTimeoutError.** Under WHATWG stream semantics `reader.cancel()` resolves the pending `read()` with `{done:true}` (close steps, not error steps), so the loop breaks and throws StreamIdleTimeoutError as intended. Would only break if undici rejects in-flight reads on cancel — not confirmable from the diff and contrary to spec, so not flagged.
- **`void stream.destroy().catch(()=>{})` unhandled rejection.** Swallowed by `.catch`; already addressed by prior Copilot feedback.
- **Double destroy (maybeCancel path + processSSE.finally, and messagesApi cleanup callback).** `DestroyableStream.destroy()` is idempotent (reader undefined → `stream.cancel()` no-op), so harmless.
- **Live setTimeout keeping the event loop alive after consumer done.** Timer is cleared on every chunk (356) and in `finally` (367); only leaks if a caller drives `.next()` manually and drops the generator without `.return()`, which no call site does (all use `for await`).
