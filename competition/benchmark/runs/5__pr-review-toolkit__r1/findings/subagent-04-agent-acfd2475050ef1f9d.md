# subagent agent-acfd2475050ef1f9d

I have all the context I need. The DestroyableStream.destroy() implementation, all three call sites, the AsyncIterableObject error propagation, and the stream.ts telemetry patterns are confirmed. Here are my findings.

---

# Error-Handling Audit — PR #308517 "Support timing out hung streams"

Scope: only the changed code. Line numbers are for the merged file at head SHA `4d10215`; diff-hunk references included. Context fetched: `DestroyableStream.destroy()`/`[Symbol.asyncIterator]`, all three call sites, and `AsyncIterableObject`'s executor error path.

Verified control-flow facts I relied on:
- `DestroyableStream.destroy()` calls `this.reader.cancel()`; per the Streams spec that resolves the in-flight `read()` with `{done:true}` (this is what makes the watchdog work). [Inference — depends on the underlying `ReadableStream` being spec-compliant; this repo has multiple fetcher backends: `baseFetchFetcher`, `nodeFetchFetcher`, `nodeFetcher`, `fetcherFallback`.]
- `AsyncIterableObject` (messagesApi/responsesApi call sites) does surface a throwing executor to consumers via `this.reject(err)` → consumer `next()` throws. So at those two sites the timeout error is not swallowed at the iterable layer.
- A repo-wide search for `StreamIdleTimeoutError` returns zero references outside the three changed files + test. Nothing anywhere does `instanceof StreamIdleTimeoutError` or logs/telemeters it specially.

---

## Finding 1 — CRITICAL (diagnosability): the timeout error is thrown but never logged or sent to telemetry; in `stream.ts` the surrounding `finally` actively logs a misleading "request done"

Location: `extensions/copilot/src/platform/networking/node/stream.ts:~322` (call site) and its enclosing `finally` at `stream.ts:302-305` (`this.logService.info("request done: requestId ...")`); mirror gap at `messagesApi.ts:~595` and `responsesApi.ts:~537`.

Issue: `withStreamIdleTimeout` throws `StreamIdleTimeoutError` and leaves it to propagate. None of the three call sites catch it to log or telemeter. This is glaring in `stream.ts` because the sibling error paths in the very same function do the right thing — malformed JSON gets `logService.error(...)` + `sendCommunicationErrorTelemetry(...)` (lines 358-359), a server error gets the same (377-378), an unexpected no-choices response gets the same (389-390). The hung-stream timeout gets none of that. Worse, the `processSSE` `finally` unconditionally runs `logService.info("request done: requestId: [...] model deployment ID: [...]")` on the way out — so a hung/aborted request emits a success-shaped "request done" log line, and then an uncategorized error bubbles up with no correlating error log or telemetry event.

Net effect: a hung stream is strictly *less* diagnosable than a single malformed SSE line. Because nothing catches `StreamIdleTimeoutError` by type anywhere in the codebase, upstream it degrades into a generic "the request failed" with no signal that a watchdog fired. The feature's entire reason for existing — making hung streams visible — is undercut at the surface where it matters.

Hidden errors / how it goes unnoticed: on-call sees a generic completion failure (or a retry storm) with a preceding "request done" info line; there is no metric to count timeouts, no way to tell a 2-minute TTFT timeout from a 60s mid-stream stall from an unrelated socket error. The timeout is invisible in aggregate telemetry.

Recommendation: at each call site (or centrally, once, right where the throw is consumed), catch `StreamIdleTimeoutError` and emit `logService.error` + `sendCommunicationErrorTelemetry` with the request id / model / deployment, before rethrowing. In `stream.ts`, do not let the `finally` log "request done" when the loop exited via a thrown timeout — or downgrade/qualify that log.

Example (stream.ts):
```ts
try {
    for await (const chunk of withStreamIdleTimeout(this.body)) { ... }
} catch (e) {
    if (e instanceof StreamIdleTimeoutError) {
        this.logService.error(`SSE idle timeout for request id ${this.requestId.headerRequestId} (model ${this.requestId.deploymentId}): ${e.message}`);
        sendCommunicationErrorTelemetry(this.telemetryService, `SSE idle timeout for request id ${this.requestId.headerRequestId}`, e.message);
    }
    throw e;
}
```

---

## Finding 2 — HIGH: if `iterator.next()` rejects on cancel, the timeout is misattributed — the `if (timedOut) throw StreamIdleTimeoutError` is bypassed

Location: `fetcherService.ts:355` (`const result = await iterator.next();`) together with the throw placed *after* the try/finally at `fetcherService.ts:371-374` (diff hunk lines 109 and 125-128).

Issue: the design assumes that when the watchdog calls `stream.destroy()`, the pending `iterator.next()` *resolves* with `{done:true}`, so control reaches `break` → `finally` → `if (timedOut) throw`. But if `reader.cancel()` instead causes the in-flight `read()` to *reject* (an aborted-socket rejection, an `AbortError`/`TypeError`, or a non-spec-compliant fetcher backend), then `await iterator.next()` throws. That exception unwinds through the `finally` and out of the generator — and the `if (timedOut) throw new StreamIdleTimeoutError(...)` block, sitting *after* the try/finally, is never executed. The caller receives the raw reject reason, not `StreamIdleTimeoutError`.

So on exactly the machines where cancel surfaces as a rejection, the watchdog fires correctly but the user/telemetry sees a generic "operation aborted"/socket error — the timeout is real but unlabeled. Combined with Finding 1, it's doubly invisible. This is race/backend-dependent, which makes it worse: it will pass the fake-timer unit tests (which drive a spec-compliant `ReadableStream`) and only misbehave against real fetcher backends.

Hidden errors: `AbortError`, `TypeError` ("Cannot read/cancel..."), node socket `ECONNRESET`/`ERR_STREAM_PREMATURE_CLOSE` — all get passed through verbatim in place of the intended timeout classification.

Recommendation: check `timedOut` inside the loop/catch, not only after the try. Wrap `await iterator.next()` so that a rejection while `timedOut` is true is converted to `StreamIdleTimeoutError`.

Example:
```ts
let result;
try {
    result = await iterator.next();
} catch (e) {
    if (timedOut) {
        throw new StreamIdleTimeoutError(isFirstChunk ? SSE_FIRST_CHUNK_TIMEOUT_MS : SSE_IDLE_TIMEOUT_MS, isFirstChunk);
    }
    throw e;
} finally {
    clearTimer();
}
```

---

## Finding 3 — HIGH: `void stream.destroy().catch(() => { })` swallows every cleanup failure — a resource leak (or a watchdog that itself hangs) becomes completely silent

Location: `fetcherService.ts:346` (diff hunk line 100).

Issue: `stream.destroy()` resolves to `reader.cancel()` / `stream.cancel()`, i.e. it aborts the underlying HTTP socket. `.catch(() => { })` discards any rejection from that abort. This is the reclaim step of a feature whose entire purpose is to reclaim resources from hung connections — swallowing the failure of the reclaim defeats the purpose and leaves zero evidence. Two concrete harms:

1. Silent resource leak: if the underlying source's cancel algorithm rejects (socket fails to abort cleanly), the connection may stay open and the empty `catch` guarantees no log, no telemetry, no trace. You will never learn that timeouts are firing but sockets aren't closing.
2. [Inference / Unverified — backend-dependent] Watchdog self-hang: the whole mechanism depends on `cancel()` resolving the pending `read()`. If a non-spec-compliant fetcher backend rejects `cancel()` *without* settling the in-flight `read()`, then `await iterator.next()` (line 355) never resolves, `withStreamIdleTimeout` hangs forever, and `StreamIdleTimeoutError` is never thrown. The `.catch(() => { })` hides the one signal that would explain why the anti-hang watchdog is itself hung. Given this repo ships several fetcher backends (`nodeFetchFetcher`, `nodeFetcher`, `fetcherFallback`), spec-perfect cancel semantics cannot be assumed for all of them.

Hidden errors: underlying-source `cancel` rejections, node `ERR_STREAM_DESTROYED`/socket-teardown errors, custom-fetcher cancel exceptions.

Recommendation: do not silently discard. At minimum log the destroy failure with context; consider a telemetry counter for "timeout cleanup failed." Don't rely on an empty catch here.

Example:
```ts
timer = setTimeout(() => {
    timedOut = true;
    void stream.destroy().catch(err =>
        this.logService.error(`Failed to destroy hung SSE stream after idle timeout: ${err}`));
}, timeoutMs);
```
(inject or thread a logger; even a module-level `console.error`/telemetry hook beats `() => { }`.)

---

## Finding 4 — MEDIUM: a throwing `iterator.return?.()` in the `finally` masks the intended `StreamIdleTimeoutError`

Location: `fetcherService.ts:366-369` (`finally { clearTimer(); await iterator.return?.(); }`) vs. the throw at `fetcherService.ts:371-374` (diff hunk lines 120-128).

Issue: because the timeout throw lives *after* the try/finally, any rejection from `await iterator.return?.()` propagates first and preempts the `StreamIdleTimeoutError`. `DestroyableStream`'s async iterator `finally` calls `reader.releaseLock()`, which throws a `TypeError` if a read is still outstanding. In the common timeout path this happens to be safe (the DestroyableStream generator has already completed by the time we reach here), but the structure is fragile: any race or backend where `return()`/`releaseLock()` rejects will replace the meaningful timeout error with an opaque "Cannot release a reader with outstanding read()" `TypeError`. Same masking class as Finding 2.

Hidden errors: `TypeError` from `releaseLock()` with outstanding reads; rejections from a piped-stream `return()`.

Recommendation: guard the cleanup so it cannot overwrite the pending timeout classification — capture the timeout decision before the finally, or wrap `iterator.return()` in its own try/catch that only logs.

Example:
```ts
} finally {
    clearTimer();
    try { await iterator.return?.(); }
    catch (e) { this.logService?.error(`iterator.return during idle-timeout cleanup failed: ${e}`); }
}
```

---

## Finding 5 — MEDIUM: `StreamIdleTimeoutError` carries no request/model/deployment context, so even when surfaced it can't be correlated

Location: `fetcherService.ts:312-319` (the class) and the throw at `fetcherService.ts:373`.

Issue: the message ("SSE stream timed out after 60000ms of inactivity" / "waiting 120000ms for the first chunk") states duration and phase but not *which* request timed out. Every neighboring log/telemetry call in `stream.ts` is keyed on `requestId.headerRequestId` and `deploymentId`; this error has neither. When it lands in aggregate telemetry it can't be tied to an endpoint, model, or request id — you can count that *something* timed out but not attribute it. It also can't distinguish first-chunk vs mid-stream cause without string-matching the message.

Recommendation: give the error structured fields (`isFirstChunk`, `timeoutMs`, and an optional `requestId`/`model` passed in by the caller) so consumers can telemeter without parsing the message. `withStreamIdleTimeout` should accept an optional context object to embed.

---

## Finding 6 — LOW / VERIFY-UPSTREAM: partial data already delivered before the throw may be accepted as a complete response downstream

Location: consumers of the wrapped loop — `stream.ts:~322` (deltas already pushed via `finishedCb`), `messagesApi.ts:~595` / `responsesApi.ts:~537` (completions already `feed.emitOne`'d).

Issue: by the time the timeout throws, earlier chunks have already been fed to the SSE parser and side-effected: `finishedCb('...text...')` progress callbacks fired in `stream.ts`, and `feed.emitOne(completion)` ran in the two API processors. The wrapper correctly turns the *stream* into an error, and `AsyncIterableObject.next()` does prioritize the error over buffered-but-unconsumed results — so at those two sites a not-yet-consumed partial is dropped in favor of the error (good). The residual risk is entirely in unchanged upstream code: any top-level handler that catches the thrown error but keeps the already-accumulated partial text (e.g. treats a streamed-so-far response as usable) would present a truncated answer as complete. This PR doesn't introduce that, but it also doesn't emit a marker (e.g. a `FinishedCompletionReason`-style truncation signal) that would let downstream distinguish "timed-out partial" from "clean finish." Worth confirming the completion consumers treat a thrown `StreamIdleTimeoutError` as a hard failure and discard accumulated partial text rather than returning it.

Recommendation: verify the top-level completion consumers discard partial output on this error; if any accumulate-and-return, add an explicit truncation reason so a timed-out partial can't masquerade as a complete response.

---

### Summary ranking
1. Finding 1 (CRITICAL) — no logging/telemetry on timeout; misleading "request done"; less diagnosable than a bad JSON line — `stream.ts:302-305,~322`, `messagesApi.ts:~595`, `responsesApi.ts:~537`
2. Finding 2 (HIGH) — reject-on-cancel bypasses the timeout throw; timeout misattributed as a generic socket/abort error — `fetcherService.ts:355` + `:371-374`
3. Finding 3 (HIGH) — `void stream.destroy().catch(() => { })` silently swallows cleanup failure / potential watchdog self-hang — `fetcherService.ts:346`
4. Finding 4 (MEDIUM) — throwing `iterator.return?.()` in `finally` can mask the timeout error — `fetcherService.ts:366-369`
5. Finding 5 (MEDIUM) — error lacks request/model context; poor correlation — `fetcherService.ts:312-319,373`
6. Finding 6 (LOW/verify) — partial pre-timeout data could be accepted as complete downstream — consumer sites above

Key files: `/tmp/pr308517.diff`; and in the branch `extensions/copilot/src/platform/networking/common/fetcherService.ts`, `extensions/copilot/src/platform/networking/node/stream.ts`, `extensions/copilot/src/platform/endpoint/node/messagesApi.ts`, `extensions/copilot/src/platform/endpoint/node/responsesApi.ts`.

Note: I did not post anything to GitHub. Findings 2 and 3(item 2) are labeled [Inference/Unverified] because they depend on the concrete `ReadableStream` cancel semantics of whichever fetcher backend is in use, which I could not execute against.
