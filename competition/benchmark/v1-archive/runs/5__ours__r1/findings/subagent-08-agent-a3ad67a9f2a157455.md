# subagent agent-a3ad67a9f2a157455

## System Design Review: PR #308517 "Support timing out hung streams"

### System Model

- **Boundary**: The watchdog lives in the transport-common layer (`extensions/copilot/src/platform/networking/common/fetcherService.ts`) next to `DestroyableStream`, which is the right home — it operates on transport chunks, so SSE keep-alive comments count as activity.
- **Contract**: `IChatEndpoint.processResponseFromChatEndpoint` has five concrete streaming implementations over the same `Response`/`DestroyableStream` infrastructure: the responsesApi, messagesApi, and SSEProcessor paths (all three wrapped by this PR), plus `StreamingPassThroughEndpoint` and `ClaudeStreamingPassThroughEndpoint` (not wrapped).
- **Error flow**: All three wrapped paths funnel through `chatMLFetcher._doFetchViaHttp`, whose stream-consumption wrapper tags every thrown error with `err.fetcherId` (chatMLFetcher.ts:1294-1298), then `processError` (chatMLFetcher.ts:1949) classifies it. `fetcherServiceImpl.isFetcherError` returns true for any error with a `fetcherId` property (fetcherServiceImpl.ts:196).
- **Concurrency model**: A `setTimeout` macrotask races the pending `iterator.next()` microtask chain; timeout is signaled in-band by `stream.destroy()` → `reader.cancel()` → pending read resolves `{done: true}` (WHATWG `ReadableStreamCancel` closes the stream, resolving pending reads with done), disambiguated out-of-band by the `timedOut` flag. I traced the race windows (chunk-at-deadline, natural-close-at-deadline, external-destroy-vs-timer, consumer `break`, error-during-read) and each resolves correctly — details under Considered But Not Flagged.

### Findings

```json
[
  {
    "file": "extensions/copilot/src/extension/externalAgents/node/oaiLanguageModelServer.ts",
    "line": 472,
    "severity": "Medium",
    "category": "design",
    "issue": "[CROSS_CUTTING_DRIFT] The idle-timeout watchdog was applied to 3 of the 5 implementations of the same processResponseFromChatEndpoint streaming pattern. StreamingPassThroughEndpoint (here) and ClaudeStreamingPassThroughEndpoint (claudeLanguageModelServer.ts:690) run identical `for await (const chunk of body)` loops over the same Response/DestroyableStream infrastructure with no watchdog, so hung connections in external-agent and Claude pass-through sessions still hang indefinitely — the exact failure mode this PR exists to fix. The vendored completions-core copy (extension/completions-core/vscode-node/lib/src/openai/stream.ts:293) is likewise unprotected.",
    "fix": "Wrap the two pass-through endpoints' body iteration in withStreamIdleTimeout as well (they consume the same DestroyableStream type), or document why pass-through sessions are intentionally exempt. Evaluate whether the completions-core copy should carry the same protection or is synced from an upstream that must be patched there.",
    "confidence": 75,
    "pre_existing": true
  },
  {
    "file": "extensions/copilot/src/platform/networking/common/fetcherService.ts",
    "line": 312,
    "severity": "Medium",
    "category": "design",
    "issue": "[API_CONTRACT] StreamIdleTimeoutError is exported as a distinct error type but no code anywhere handles it. Its runtime classification is accidental: chatMLFetcher's generic stream-error enrichment sets err.fetcherId (chatMLFetcher.ts:1294-1298), and fetcherServiceImpl.isFetcherError treats any error carrying fetcherId as a fetcher error (fetcherServiceImpl.ts:196), so processError maps the timeout to ChatFetchResponseType.NetworkError with the fetcher-fallback message: users see 'Please check your firewall rules and network connection then try again. Error Code: SSE stream timed out after 60000ms of inactivity.' — misattributing a server-side hang to the user's network configuration. The error type's meaning thus depends on an implicit cross-layer property tag rather than an explicit contract; any future consumer of these processors outside chatMLFetcher gets a completely unclassified error.",
    "fix": "Integrate the new error into the error-classification boundary explicitly: add a StreamIdleTimeoutError (or error-name) branch in chatMLFetcher.processError that returns NetworkError with an accurate 'response stream stalled / timed out' message, so retryability and user messaging are deliberate rather than a side effect of the fetcherId tag.",
    "confidence": 75,
    "pre_existing": false
  },
  {
    "file": "extensions/copilot/src/platform/networking/common/fetcherService.ts",
    "line": 328,
    "severity": "Medium",
    "category": "design",
    "issue": "[EVOLUTION_READINESS] withStreamIdleTimeout accepts no options — the 60s idle / 2min TTFT policy is baked into the mechanism as module constants and applied identically to every model, endpoint, and transport at all three call sites, with no configuration or experimentation-service integration and no kill switch. The surrounding system routes comparable behavioral knobs through experiment config (RetryNetworkErrors, RetryServerErrorStatusCodes in chatMLFetcher.ts:502/575), so if a backend legitimately exceeds 60s of transport-level silence (e.g. long server-side tool execution without SSE keep-alive comments — messagesApi explicitly supports server tool calls), requests are killed mid-stream and the only remediation is a code change and extension release.",
    "fix": "Accept an optional { firstChunkTimeoutMs, idleTimeoutMs } parameter (defaulting to the constants) so call sites can differentiate, and consider gating the values through the existing experiment-based config machinery so the policy can be tuned or disabled without shipping code.",
    "confidence": 50,
    "pre_existing": false
  }
]
```

### Considered But Not Flagged

- **Timer vs. iterator race windows** (`fetcherService.ts:342-374`): What happens when a chunk, a natural close, or an external destroy lands at the same instant the timer fires? Per WHATWG semantics, `reader.cancel()` resolves pending reads with `{done: true}`, and microtask continuations (which run `clearTimer()`) drain before the timer macrotask, so a false timeout requires a genuine full idle window. In the residual races (chunk settled in the same tick as the timer), the chunk is still delivered before the error, and the error is semantically justified by the real 60s gap. Sound.
- **Timeout signaled in-band as `{done: true}`**: The watchdog's destroy is indistinguishable on the wire from normal completion or user cancellation; the `timedOut` flag correctly disambiguates the watchdog's own destroy, and the post-loop throw placement means an early consumer `break` (only reachable after a chunk arrived, i.e. timer cleared) can never swallow a pending timeout. Fragile-looking but verified correct; no nameable failure.
- **External cancel racing the timer**: user cancellation and the 60s deadline firing simultaneously would report a timeout instead of a cancel — requires both conditions to be true at once; either classification is defensible.
- **`finally { await iterator.return?.() }` masking the timeout throw**: `DestroyableStream`'s generator finally only calls `releaseLock()`, which does not throw in this path.
- **Hard failure discards partial streamed content** instead of finishing gracefully with a partial completion (SSEProcessor has machinery for partial solutions). This is the PR's stated intent ("fail fast"); a product decision, not a design defect.
- **`common/`-layer `setTimeout` use**: ambient in all target environments; `ReturnType<typeof setTimeout>` keeps it portable.
- **setTimeout/clearTimeout churn per network chunk**: negligible, and performance-reviewer scope.
- **`withStreamIdleTimeout` typed against the concrete `DestroyableStream` class** (nominal due to private fields) rather than a minimal `AsyncIterable & destroyable` interface: fine for current use; trivially widenable later.
- **Timer keeps event loop alive up to 2 min without `unref()`**: irrelevant in a long-lived extension host.

Key files: `/home/decaf/code/decaf-claude/competition/benchmark/repos/5/extensions/copilot/src/platform/networking/common/fetcherService.ts`, `/home/decaf/code/decaf-claude/competition/benchmark/repos/5/extensions/copilot/src/extension/prompt/node/chatMLFetcher.ts`, `/home/decaf/code/decaf-claude/competition/benchmark/repos/5/extensions/copilot/src/extension/externalAgents/node/oaiLanguageModelServer.ts`, `/home/decaf/code/decaf-claude/competition/benchmark/repos/5/extensions/copilot/src/extension/chatSessions/claude/node/claudeLanguageModelServer.ts`.

[Inference] Confidence notes: finding 2's exact user-facing string depends on which fetcher is primary at runtime, but every implementation found (`baseFetchFetcher.ts:122`, `nodeFetcher.ts:146`) returns the "check your firewall rules" message, and the classification path itself is verifiable statically. Finding 3's impact depends on backend keep-alive behavior outside the diff, hence anchor 50. No pre-flight gates were run (dependencies not installed); all reasoning is static.
