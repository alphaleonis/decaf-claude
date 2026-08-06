# subagent agent-ae18794412ae3d9f0

## Design Review — PR #308517 "Support timing out hung streams"

**System model.** The new `withStreamIdleTimeout` sits in the common networking layer (`fetcherService.ts`) and wraps `DestroyableStream` iteration for three of the codebase's SSE consumers. Error flow: watchdog timer (macrotask) fires → `stream.destroy()` → `reader.cancel()` resolves the pending `read()` with `{done: true}` → wrapper breaks, runs `finally`, then throws `StreamIdleTimeoutError` → propagates through `AsyncIterableObject` rejection → `chatMLFetcher` catch (line 555) → `processError` classification → user-facing result. Cancellation flow: external `destroy()` (onReturn callbacks / `SSEProcessor.cancel`) produces the same `{done: true}` but with `timedOut === false`, so the wrapper completes cleanly — the two destroy sources are correctly disambiguated by the flag. I verified the timer/microtask interleaving statically: a resolved `read()` continuation always drains before the timer macrotask, so there is no path where `timedOut` is set yet a value is yielded, and consumer-side `break`/`return()` unwinds through `finally` without reaching the trailing throw. The core concurrency design is sound.

The findings below are about what surrounds that core: the error's contract with upstream classification, siblings left unwired, and the configurability/observability of the new kill-switch behavior.

```json
[
  {
    "file": "extensions/copilot/src/platform/networking/common/fetcherService.ts",
    "line": 312,
    "severity": "Medium",
    "category": "design",
    "issue": "[API_CONTRACT] StreamIdleTimeoutError is an exported, named error class that no upstream handler detects; its actual runtime classification rides on an incidental side channel. In chatMLFetcher.ts, any error thrown while iterating completions gets tagged `err.fetcherId = response.fetcher` (lines 1294/1301), and `isFetcherError()` returns true for any error with a truthy `fetcherId` (fetcherServiceImpl.ts:196). So the timeout classifies as ChatFetchResponseType.NetworkError only by accident of generic tagging, and the user-facing message comes from getUserMessageForFetcherError: 'Please check your firewall rules and network connection then try again. Error Code: SSE stream timed out after 60000ms...' — misattributing a server-side hang to the user's firewall. The codebase's established contract for cross-layer error identity is explicit name-based detection (isAbortError checks e.name === 'AbortError'); this PR introduces a named error precisely so it can be identified, then never wires the identification.",
    "fix": "Add explicit classification for StreamIdleTimeoutError in chatMLFetcher.processError (name-based, matching the isAbortError convention): map it to a retry-eligible category with an accurate user message ('The connection stalled while receiving the response; please try again'), instead of relying on the fetcherId tagging fallback. This also decouples the timeout's behavior from an unrelated mechanism that a future refactor could change silently.",
    "confidence": 75,
    "pre_existing": false
  },
  {
    "file": "extensions/copilot/src/extension/externalAgents/node/oaiLanguageModelServer.ts",
    "line": 472,
    "severity": "Medium",
    "category": "design",
    "issue": "[CROSS_CUTTING_DRIFT] The external-agents pass-through endpoint iterates `response.body` with a bare `for await (const chunk of body)` — structurally a near-copy of responsesApi.ts's processResponseFromChatEndpoint (same SSEParser + OpenAIResponsesProcessor pipeline) — but was not given the idle watchdog. The exact hung-stream failure mode this PR fixes remains in this fourth streaming consumer: a hung upstream connection stalls the pass-through server request indefinitely, and this path also bypasses chatMLFetcher's error tagging, so its failure behavior diverges from the three wired call sites.",
    "fix": "Wrap this iteration in withStreamIdleTimeout as well, or document why the pass-through server intentionally has no idle bound. Consider making the watchdog part of the DestroyableStream iteration contract (opt-out rather than opt-in) so new consumers cannot silently miss it.",
    "confidence": 75,
    "pre_existing": true
  },
  {
    "file": "extensions/copilot/src/platform/networking/common/fetcherService.ts",
    "line": 303,
    "severity": "Medium",
    "category": "design",
    "issue": "[EVOLUTION_READINESS] withStreamIdleTimeout takes no options: the 2min/60s budgets are fixed module-level constants shared by three different API families (Anthropic messages, OpenAI Responses, chat-completions SSE), and there is no configuration or experiment gate. This is contrary to the adjacent convention — retry-on-network-error right next door is experiment-gated (ConfigKey.TeamInternal.RetryNetworkErrors). BYOK/local-proxy endpoints flow through the same ChatEndpoint dispatch (chatEndpoint.ts:51/370) into these wrapped paths, and a large local model (e.g., Ollama on modest hardware) can legitimately exceed 2 minutes of prompt-eval before the first chunk; those users' streams are force-destroyed with no per-endpoint or remote lever — tuning requires editing shared constants that affect every consumer, or a new release.",
    "fix": "Accept an optional { firstChunkTimeoutMs, idleTimeoutMs } parameter defaulting to the current constants, and thread an endpoint-level or experiment-based override through the three call sites so BYOK/proxy endpoints and emergency tuning don't require changing a global constant.",
    "confidence": 75,
    "pre_existing": false
  },
  {
    "file": "extensions/copilot/src/extension/completions-core/vscode-node/lib/src/openai/stream.ts",
    "line": 293,
    "severity": "Medium",
    "category": "design",
    "issue": "[CROSS_CUTTING_DRIFT] The completions-core fork of SSEProcessor iterates its DestroyableStream body (`networkRead: for await (const chunk of this.body)`) with no idle watchdog, leaving the ghost-text completion path exposed to the same indefinite-hang failure mode. The two SSEProcessor variants (platform/networking/node/stream.ts vs completions-core) now diverge in resilience behavior for the identical pattern.",
    "fix": "Either wire withStreamIdleTimeout into the completions-core SSEProcessor (it already imports DestroyableStream from the same fetcherService module), or record explicitly that the fork is excluded and why, so the divergence is a decision rather than drift.",
    "confidence": 50,
    "pre_existing": true
  },
  {
    "file": "extensions/copilot/src/platform/networking/common/fetcherService.ts",
    "line": 346,
    "severity": "Low",
    "category": "design",
    "issue": "[DATA_MODEL] The watchdog kills the stream via `stream.destroy()`, which calls `reader.cancel()` with no reason; the Response's counting TransformStream classifies cancel-with-no-reason as outcome 'cancel' (fetcherService.ts:104-107). So in the responseStreaming fetch-event telemetry, watchdog timeouts are recorded identically to ordinary user cancellations — the telemetry data model cannot measure how often the new timeout fires, which is exactly the signal needed to validate the thresholds this PR hardcodes (the error does still reach exception telemetry via chatMLFetcher, but the streaming-phase outcome dimension is lost).",
    "fix": "Extend DestroyableStream.destroy() to accept an optional reason and have the watchdog pass a StreamIdleTimeoutError (or a sentinel), letting the counting stream's cancel handler report a distinct outcome (e.g., 'idle-timeout') so timeout frequency is observable per fetcher/hostname.",
    "confidence": 75,
    "pre_existing": false
  }
]
```

## Considered But Not Flagged

- **Timer × generator × destroy concurrency** (`fetcherService.ts:342-374`): I examined what `iterator.next()` resolves to after `destroy()`. Web-spec `reader.cancel()` resolves pending reads with `{done: true}`, and because promise continuations (microtasks) always drain before timer callbacks (macrotasks), there is no interleaving where `timedOut` is set but the wrapper resumes with a value, nor where the timer fires between `next()` resolution and `clearTimer()`. The flag-then-throw-after-loop design is sound. [Inference from spec semantics; not runnable in this checkout.]
- **`.return()` bypassing the trailing throw**: consumer `break`/`return` (e.g., `[DONE]` handling in stream.ts:344, `maybeCancel` early return) unwinds via generator-return semantics — `finally` runs, the `if (timedOut)` throw does not. Since the timer is never armed while suspended at `yield`, `timedOut` cannot be true on that path. Correct by construction.
- **External-cancellation composition**: all three call sites' existing destroy paths (`onReturn` → `response.body.destroy()` in messagesApi/responsesApi; `SSEProcessor.cancel()` → `response.body.destroy()` forwarding through `pipedHead` to the TextDecoder-piped stream) converge on the same reader the wrapper iterates, produce `{done: true}` with `timedOut === false`, and end the wrapper cleanly. Composition is correct, including double-destroy (reader-vs-unlocked-stream branches in `destroy()`).
- **Underlying stream error racing the timeout**: if the stream is already errored when the watchdog fires, `next()` rejects with the real error and the wrapper propagates it instead of `StreamIdleTimeoutError`, with the destroy rejection swallowed. Propagating the true error is the better outcome; not a defect.
- **Chunk-in-flight loss at the timeout boundary**: a chunk arriving in the same event-loop turn after the timer callback is discarded by `cancel()`. Inherent to any timeout design at millisecond scale against a 60s budget; not actionable.
- **No total-duration cap**: a server trickling one byte per 59s keeps the stream alive indefinitely. That is a different failure mode (slow-loris, not hang) and out of the PR's stated scope; a per-chunk idle watchdog is the standard design here.
- **`instanceof` robustness of `StreamIdleTimeoutError`**: no prototype restoration, but with modern compile targets and same-realm usage this is moot — and the codebase convention is name-based detection anyway (folded into finding 1).
- **Passing a `pipeThrough`'d-then-abandoned original stream to the wrapper** would throw immediately on `getReader()` (stream locked) — loud failure, and no current caller does it.
- **`Response.text()` (`fetcherService.ts:134`) iterates the body with no timeout** — non-streaming responses can still hang; pre-existing, different consumption model (body-at-once with other HTTP-level timeouts plausible), and not Critical/High, so per my pre-existing-gap threshold not reported.

### Probe Requests

None — all findings were verified statically (error-classification chain traced end-to-end through `chatMLFetcher.processError`, `fetcherServiceImpl.isFetcherError`, and the `err.fetcherId` tagging); no dynamic probe would add signal given dependencies are not installed.

Key files: `/home/decaf/code/decaf-claude/competition/benchmark/repos/5/extensions/copilot/src/platform/networking/common/fetcherService.ts`, `/home/decaf/code/decaf-claude/competition/benchmark/repos/5/extensions/copilot/src/extension/prompt/node/chatMLFetcher.ts`, `/home/decaf/code/decaf-claude/competition/benchmark/repos/5/extensions/copilot/src/extension/externalAgents/node/oaiLanguageModelServer.ts`, `/home/decaf/code/decaf-claude/competition/benchmark/repos/5/extensions/copilot/src/extension/completions-core/vscode-node/lib/src/openai/stream.ts`.
