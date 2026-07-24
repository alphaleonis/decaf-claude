# subagent agent-ab67d4274da85b3be

## Adversarial Review

### Summary
This PR adds a watchdog (`withStreamIdleTimeout`) that aborts SSE streams after 120s (first chunk) / 60s (idle) and wraps it around all three chat/agent SSE call sites. The core generator logic is sound and well-tested, but the feature ships operationally blind: it introduces a new failure mode that can abort legitimate traffic with **zero telemetry, no remote configurability/kill switch, and a completely orphaned error type** that nothing downstream classifies, retries, or surfaces meaningfully.

### Findings

#### High

- **[observability]** The watchdog fires silently — no metric or event counts timeouts — `fetcherService.ts:344`
  - **What's wrong/missing:** The timer callback sets `timedOut` and calls `stream.destroy()` with no telemetry/log (`grep` confirms `withStreamIdleTimeout` emits nothing). Because `StreamIdleTimeoutError.name === 'StreamIdleTimeoutError'` (not `'AbortError'`), `isAbortError()` returns false, so it lands in generic "error" outcome telemetry indistinguishable from any other stream error.
  - **Why it matters:** The entire point of the feature is to detect and act on hung streams. Shipped this way, you cannot answer "how often does this fire?", "did the new 60s threshold start aborting valid requests after rollout?", or "which models/endpoints hang?" There is no signal to validate the rollout or to tune the thresholds.
  - **Fix:** Emit a dedicated telemetry event (with `isFirstChunk`, `timeoutMs`, model/endpoint, `bytesReceived`) at the timeout point, before destroy/throw.
  - **Confidence:** 88/100

- **[other]** Timeouts are hardcoded `export const` with no experimentation-service backing or kill switch — `fetcherService.ts:303,310`
  - **What's wrong/missing:** `SSE_FIRST_CHUNK_TIMEOUT_MS` and `SSE_IDLE_TIMEOUT_MS` are compile-time constants. The codebase already routes tunables through `getExperimentBasedConfig` / `ConfigKey` (e.g. `automodeService.ts:325`), but these are not. A 60s inter-chunk idle limit is aggressive for extended-reasoning models and long server-side tool calls, where a provider that doesn't emit keep-alive pings can legitimately pause >60s — the Anthropic messages API sends `ping` events (which reset the timer), but the Responses/CAPI path is not guaranteed to.
  - **Why it matters:** This behavior gates *all* chat + agent + Anthropic streaming. If 60s proves too tight for some model, there is no remote override and no way to disable — mitigation requires a full extension release. No staged rollout or per-model tuning is possible.
  - **Fix:** Back both values with experiment-based config keys (with the current values as defaults) and add a disable path.
  - **Rejected alternative:** Keeping constants but adding only a global on/off flag — rejected because it doesn't allow per-model tuning, which is where the 60s risk actually bites.
  - **Confidence:** 80/100

#### Medium

- **[other]** `StreamIdleTimeoutError` is orphaned — nothing downstream classifies, retries, or user-messages it — `fetcherService.ts:312`
  - **What's wrong/missing:** `grep` confirms the type is referenced only at its definition, the throw, the three wrap sites, and tests — never in error-handling code. It's thrown mid-stream, *after* the fetch promise resolved, so `canRetryOnceNetworkError` (which only guards the initial `fetch()` call, `networking.ts:452`) never sees it — a hung connection, the textbook transient failure, gets no retry. The raw developer-facing message ("SSE stream timed out after 60000ms of inactivity") flows to whatever generic error rendering exists, with no graceful degradation.
  - **Why it matters:** A transient hang becomes a hard, non-retried failure with a non-actionable message. The new distinct error type buys nothing because no consumer branches on it.
  - **Fix:** Decide the contract — either map it to a retryable class so an idle timeout retries once, or explicitly classify it and produce a user-facing message; either way, add a handler that references the type.
  - **Confidence:** 78/100

#### Low

- **[other]** Parallel inline-completions SSE loop was not given the same protection — `extension/completions-core/vscode-node/lib/src/openai/stream.ts:293`
  - **What's wrong/missing:** `networkRead: for await (const chunk of this.body)` iterates a `DestroyableStream` (it calls `this.body.destroy()` at line 613) with the identical shape as the wrapped sites, but was left unwrapped. The inline-completion path remains vulnerable to the exact hang this PR fixes.
  - **Why it matters:** Incomplete coverage of the stated goal; ghost-text requests can still hang indefinitely. May be intentional (inline completions have aggressive request-level timeouts, and the file carries a "can we switch to the shared impl" TODO) — worth confirming, not assuming.
  - **Fix:** Wrap it too, or document why inline completions are exempt.
  - **Confidence:** 76/100

### Most Critical Gap
The single most important gap is **operational blindness combined with no remote control**: this feature can abort legitimate long-pause streams (reasoning models, long tool calls) across all chat/agent traffic, yet it emits no telemetry to detect that happening and offers no config/kill switch to tune or disable it without a full release. Ship the observability + experiment-config first, or the 60s idle threshold is an untunable, unmeasurable risk.

### Positive Observations
- The timer-only-runs-during-`next()` design correctly avoids penalizing slow consumers, and there's an explicit test for it (`streamIdleTimeout.spec.ts:160`).
- The `finally` block reliably clears the timer and returns the underlying iterator, releasing the reader lock; tested via the consumer-break case.
- On the destroy-vs-`next()` race the task flagged: microtask ordering (a resolved `read()` continuation runs and calls `clearTimer()` before the due timer's macrotask callback), plus `ReadableStream.cancel()` fulfilling pending reads with `done` rather than the queued value, means a real chunk is not yielded-then-spuriously-thrown in practice. The `timedOut` latch is never reset, but the ordering keeps it from causing partial-process-then-fail. Not flagged as a defect.

```json-findings
[{"severity":"High","confidence":88,"category":"observability","file":"extensions/copilot/src/platform/networking/common/fetcherService.ts","line":344,"finding":"The idle/first-chunk watchdog destroys the stream and throws StreamIdleTimeoutError with no telemetry or logging. Because the error name is not 'AbortError', isAbortError() is false and it lands in generic error-outcome telemetry, indistinguishable from other stream errors. There is no metric for how often hung-stream timeouts fire, so the feature's effect and threshold correctness cannot be measured after rollout.","remediation":"Emit a dedicated telemetry event at the timeout point (isFirstChunk, timeoutMs, model/endpoint, bytesReceived) before destroy/throw so timeout frequency and false-positive rate are observable.","source":"adversarial-general"},{"severity":"High","confidence":80,"category":"other","file":"extensions/copilot/src/platform/networking/common/fetcherService.ts","line":310,"finding":"SSE_FIRST_CHUNK_TIMEOUT_MS (120s) and SSE_IDLE_TIMEOUT_MS (60s) are hardcoded compile-time constants with no experimentation-service backing or kill switch, unlike other tunables in this codebase (getExperimentBasedConfig/ConfigKey). A 60s inter-chunk idle limit is aggressive for extended-reasoning models and long server-side tool calls where a provider may not send data for >60s and may not emit keep-alive pings. This gates all chat/agent/Anthropic streaming with no remote override or disable path.","remediation":"Back both thresholds with experiment-based config keys (current values as defaults) and add a disable path so the behavior can be tuned or rolled back remotely without an extension release.","source":"adversarial-general"},{"severity":"Medium","confidence":78,"category":"other","file":"extensions/copilot/src/platform/networking/common/fetcherService.ts","line":312,"finding":"StreamIdleTimeoutError is orphaned: it is referenced only at its definition, throw, the three wrap sites, and tests, never in error-handling code. It is thrown mid-stream after the fetch resolved, so canRetryOnceNetworkError (which only guards the initial fetch) never retries it, and its raw developer-facing message ('SSE stream timed out after 60000ms of inactivity') flows to generic error rendering with no user-facing handling or graceful degradation.","remediation":"Define the contract for this error: either classify it as retryable so an idle timeout retries once, or add explicit downstream handling that produces an actionable user-facing message; reference the type in a handler.","source":"adversarial-general"},{"severity":"Low","confidence":76,"category":"other","file":"extensions/copilot/src/extension/completions-core/vscode-node/lib/src/openai/stream.ts","line":293,"finding":"The inline-completions SSE loop iterates a DestroyableStream with the identical pattern as the three wrapped call sites but was left unwrapped by withStreamIdleTimeout, so the ghost-text/completions path remains vulnerable to the exact hung-stream condition this PR fixes. May be intentional (inline completions rely on request-level timeouts) but is not documented.","remediation":"Wrap this loop with withStreamIdleTimeout as well, or document why inline completions are exempt from hung-stream protection.","source":"adversarial-general"}]
```
