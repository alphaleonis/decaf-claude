# subagent agent-ad6b2913c7d9e5470

```json-findings
[
  {
    "severity": "Medium",
    "confidence": 80,
    "category": "architecture-coupling",
    "file": "extensions/copilot/src/platform/networking/common/fetcherService.ts",
    "line": 312,
    "finding": "StreamIdleTimeoutError is a bare Error subclass that carries no classification metadata (no `.code`, not an abort error, no retryable flag) and is referenced nowhere outside its definition and tests. It is thrown into the SSE consumption loops at all three call sites, but the existing transient-error classifiers do not recognize it: canRetryOnceNetworkError (networking.ts:452) keys on reason?.code against a fixed list; fetcher.isAbortError() checks abort-ness; the network-process-crash/network-changed retry (chatMLFetcher.ts:756) keys on `net::` message substrings and ChatFetchResponseType.NetworkError. A hung-stream timeout matches none of these, so it falls through to generic fatal-error handling (chatMLFetcher.ts:1754-1768 logs code='' and surfaces the message). The watchdog thus converts an infinite hang into a hard, non-retryable, user-visible failure — yet a hung stream is exactly the transient condition retry logic exists for. The retry/fatal decision is made by omission rather than intent.",
    "remediation": "Give the error a stable classification hook the existing taxonomy already reads (e.g. a `.code` such as 'ETIMEDOUT'/'ERR_STREAM_IDLE_TIMEOUT' so canRetryOnceNetworkError can match, or route it through ChatFetchResponseType.NetworkError) and make an explicit, tested decision about whether a hung-stream timeout is retryable-once. At minimum document why it is intentionally fatal.",
    "source": "architecture-reviewer"
  },
  {
    "severity": "Medium",
    "confidence": 76,
    "category": "other",
    "file": "extensions/copilot/src/platform/networking/common/fetcherService.ts",
    "line": 303,
    "finding": "SSE_FIRST_CHUNK_TIMEOUT_MS (120s) and SSE_IDLE_TIMEOUT_MS (60s) are hard-coded module constants with no experiment/config gate and no kill switch. This is a behavior change that can abort a legitimately slow in-flight model stream, and the only way to tune the thresholds or disable the watchdog if it produces false positives is shipping a new build. This diverges from the established convention in this exact code path: networking/endpoint gate risky behavior with getExperimentBasedConfig (18 usages under src/platform/networking + src/platform/endpoint; e.g. the adjacent NetworkProcessCrash fallback at chatMLFetcher.ts:760). The watchdog is precisely the class of change that pattern exists to de-risk.",
    "remediation": "Back the two thresholds (and an enable/disable flag) with an experiment-based ConfigKey like the sibling networking behaviors, so the timeout can be tuned per-model/region and disabled remotely without a redeploy. Counter-argument to weigh: the values are conservative and a seam can be added when the first false-positive report lands — but for a user-request-aborting reliability feature the kill switch is cheap insurance at rollout.",
    "source": "architecture-reviewer"
  }
]
```

### Architectural Insights

Overall this is a clean, well-scoped change. The async-generator watchdog is a good pattern choice: it drives the timer purely from `iterator.next()` timing, clears it before `yield` so consumer processing is not counted (explicitly tested), and defers the throw until after the `finally` cleanup because you cannot throw out of a `setTimeout` callback into a generator. The `timedOut` latch + break-then-throw sequencing is the correct idiom for this. Cleanup (`clearTimer` + `iterator.return?.()` in `finally`) correctly releases the `DestroyableStream` reader lock, and the test suite covers the meaningful states.

Two points that did **not** warrant findings, for the record:

- **Three call sites do not duplicate logic.** `messagesApi.ts:596`, `responsesApi.ts:537`, and `stream.ts:322` each wrap with the single shared `withStreamIdleTimeout(...)` helper — one-line, no copy-paste of timer machinery. This is the right amount of abstraction, and with three callers the helper earns its cost. No shared-helper extraction is needed.

- **Cohesion nit (Low, not filed):** the `SSE_*` constants encode LLM-domain TTFT knowledge (`fetcherService.ts:299-310`) and an `SSE`-named error inside a generic `networking/common` module, while the function itself is generic over `DestroyableStream<T>`. Minor policy-in-mechanism leak; the file already hosts `DestroyableStream`, so severity is low. If the retry-integration finding is addressed, consider co-locating the SSE policy with the SSE-consuming layer instead.

- **Narrow race (very low confidence, not filed):** `timedOut` is a latch that is never reset. In standard `ReadableStream` semantics this is safe because `destroy()` → `reader.cancel()` forces the pending `read()` to resolve `{done:true}`, so no value can be yielded after the latch is set. The design holds only under that guarantee; if a fetcher-backed stream's `cancel()` did not promptly settle the in-flight read, the watchdog could itself block. Runtime-dependent and outside the diff, so noted only.

The single most consequential decision here is that the new error is a fatal, unclassified terminal — the two findings above both trace back to it. Address the taxonomy integration first.
