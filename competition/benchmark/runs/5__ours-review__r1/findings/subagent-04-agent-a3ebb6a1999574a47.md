# subagent agent-a3ebb6a1999574a47

I have enough to build the system model and report. Let me confirm my model before writing findings.

**System model.** `withStreamIdleTimeout` is a new exported async-generator watchdog around `DestroyableStream<T>`. On a stalled read it flips `timedOut`, calls `stream.destroy()` (which cancels the underlying reader, resolving the pending read as `done`), the loop breaks, and after the `try/finally` it throws `StreamIdleTimeoutError`. Three consumers wrap their SSE `for await` with it: `SSEProcessor.processSSE` (CAPI/completions), `processResponseFromMessagesEndpoint` (Anthropic), `processResponseFromChatEndpoint` (Responses). All three funnel through `ChatEndpoint.processResponseFromChatEndpoint` and are consumed inside `ChatMLFetcher`'s `try` block, whose `catch` routes any thrown error through `processError`.

**Traced consequence.** `processError` matches `isAbortError` (name==='AbortError'), `isCancellationError`, `'Premature close'`, `isInternetDisconnectedError`, then `isFetcherError` (which keys off `e.code` ∈ `[ECONNRESET, ETIMEDOUT, …]`). `StreamIdleTimeoutError` is a bare `Error` subclass with no `code` and `name==='StreamIdleTimeoutError'`, so it matches none of them and falls to the final `else` → `ChatFetchResponseType.Failed`. Retry then requires `NetworkError` (`retryNetworkError`) or WebSocket transport (`retryWithoutWebSocket`), so on the plain-HTTP streaming path a hung stream becomes a non-retried hard failure with the generic message "Error on conversation request. Check the log for more details."

**Concurrency composition** checks out: microtask (read resolution) ordering runs `clearTimer()` before any pending timer macrotask, and the redundant `destroy()` calls from the watchdog, `maybeCancel`, and the outer `finally` are idempotent (reader nulled/lock released → `stream.cancel()` no-op). No double-cancel crash.

```json
[
  {
    "file": "extensions/copilot/src/platform/networking/common/fetcherService.ts",
    "line": 373,
    "severity": "Medium",
    "category": "design",
    "issue": "[CROSS_CUTTING_DRIFT] StreamIdleTimeoutError is not integrated into the fetcher error taxonomy, so downstream classification treats a timed-out stream as a generic hard failure instead of a retryable network error. In ChatMLFetcher.processError the error matches none of isAbortError / isCancellationError / 'Premature close' / isInternetDisconnectedError / isFetcherError (which keys off e.code such as ETIMEDOUT/ECONNRESET), so it falls through to ChatFetchResponseType.Failed. On the HTTP streaming path Failed is not retried (retry requires NetworkError, or WebSocket transport), so a transient hung stream — exactly the condition retries exist for — surfaces to the user as 'Error on conversation request. Check the log for more details.' Whether it retries at all becomes transport-dependent (WebSocket path retries Failed, HTTP path does not).",
    "fix": "Give the timeout a place in the shared error taxonomy: either set a recognizable code (e.g. 'ETIMEDOUT'/a dedicated code) on StreamIdleTimeoutError so isFetcherError/network classification picks it up, or add an explicit branch in processError mapping StreamIdleTimeoutError to a NetworkError (retryable) outcome. Decide deliberately whether a hung stream should be retried, and make that decision transport-independent.",
    "confidence": 75,
    "pre_existing": false
  },
  {
    "file": "extensions/copilot/src/platform/networking/common/fetcherService.ts",
    "line": 303,
    "severity": "Low",
    "category": "design",
    "issue": "[EVOLUTION_READINESS] The idle/first-chunk timeouts are fixed module-level constants baked into withStreamIdleTimeout with no per-call or per-endpoint override. A single global 2-minute first-chunk budget cannot accommodate model-specific TTFT variance (a slow reasoning model whose time-to-first-token exceeds the constant is killed with a false StreamIdleTimeoutError, and there is no knob to raise it for that endpoint without globally weakening the watchdog for fast models). It also forces tests to couple to the real constants (importing them / using fake timers) rather than injecting small values.",
    "fix": "Accept an optional options object ({ firstChunkTimeoutMs?, idleTimeoutMs? }) defaulting to the constants, so call sites / endpoints can tune per model and tests can inject short timeouts without importing the production values.",
    "confidence": 50,
    "pre_existing": false
  },
  {
    "file": "extensions/copilot/src/platform/networking/common/fetcherService.ts",
    "line": 372,
    "severity": "Low",
    "category": "design",
    "issue": "[EVOLUTION_READINESS] isFirstChunk is a single mutable flag used for two distinct purposes: selecting which timeout to arm each iteration, and reconstructing the timeout value/message after the loop (line 372-373). This is correct today only because the flag flips exactly once and never during a timed-out wait, but the two uses are decoupled in the code and the post-loop reconstruction re-derives state the timer already knew. If the loop later gains any path that yields or continues without preserving this invariant (e.g. retry-in-loop, skipping empty chunks), the reported timeout and message will silently desync from the timer that actually fired.",
    "fix": "Capture the fired timeout's identity at the point the timer is created (e.g. store the active timeoutMs / phase alongside the timer, or have the timer callback record which phase timed out) rather than re-deriving from isFirstChunk after the loop, so the error message has a single authoritative source.",
    "confidence": 50,
    "pre_existing": false
  }
]
```

## Considered But Not Flagged

- **Concurrency composition of the two teardown paths (watchdog timer vs. `maybeCancel`/outer `finally` cancel).** Verified sound: JS microtask ordering guarantees `clearTimer()` runs on read-resolution before any pending timer macrotask fires (so a chunk arriving and the timer firing cannot both be honored), and the redundant `stream.destroy()` calls are idempotent — after the async-iterator `finally` releases the lock and nulls the reader, subsequent `destroy()` degrades to `stream.cancel()`, a no-op on an already-cancelled stream. No double-cancel crash or leak observed.

- **Boundary: wrapper takes concrete `DestroyableStream<T>` rather than a generic `AsyncIterable<T>`.** This coupling is justified, not a defect: the watchdog's whole mechanism is force-destroying a stream whose reader is locked by an in-flight `for await`, which a bare `AsyncIterable` cannot express (`iterator.return()` on a locked reader does not interrupt a pending `read()`). `destroy()` is the required escape hatch, and all three call sites already hold `DestroyableStream` response bodies. A generic signature would need an injected teardown callback for no current benefit.

- **"Do the three call sites handle the error consistently?"** They do — all three funnel through `ChatEndpoint.processResponseFromChatEndpoint` into `ChatMLFetcher`'s single `catch`/`processError`, so classification is uniform across CAPI, Anthropic, and Responses paths. The problem is not inconsistency between sites but the uniform mis-classification captured in finding 1.

- **New throw undocumented on the three consumer functions' own contracts** (`processSSE`, `processResponseFrom*` JSDoc don't mention they can now reject with `StreamIdleTimeoutError`). Real but this is a knowledge-preservation concern, out of design scope; deferring to knowledge-reviewer.
