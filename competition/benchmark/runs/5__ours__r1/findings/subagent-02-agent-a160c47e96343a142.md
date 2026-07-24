# subagent agent-a160c47e96343a142

Depth: **deep** — external-API streaming integration (high-risk domain) touching three production SSE loops; all four techniques applied, chains traced end-to-end through `DestroyableStream`, `AsyncIterableObject`, `SSEProcessor`, and `chatMLFetcher`'s error/retry machinery.

Key files read at HEAD: `/home/decaf/code/decaf-claude/competition/benchmark/repos/5/extensions/copilot/src/platform/networking/common/fetcherService.ts`, `.../platform/networking/node/stream.ts`, `.../platform/endpoint/node/messagesApi.ts`, `.../platform/endpoint/node/responsesApi.ts`, `.../extension/prompt/node/chatMLFetcher.ts`, `.../util/vs/base/common/async.ts` (AsyncIterableObject).

```json
[
  {
    "file": "extensions/copilot/src/platform/networking/common/fetcherService.ts",
    "line": 362,
    "severity": "High",
    "category": "async",
    "issue": "[ADV_ASSUMPTION] 'First chunk' means first transport bytes, not first model output: server sends an early administrative chunk (CAPI's initial empty-choices prompt_filter_results chunk — documented in-code at stream.ts:409 — or Anthropic message_start / OpenAI response.created, all arriving within ~1s) → isFirstChunk flips false → the 120s TTFT budget silently collapses to the 60s steady-state timer → a reasoning model that thinks >60s without emitting bytes (and no SSE keepalive from the proxy) → watchdog destroys a healthy stream → request fails with StreamIdleTimeoutError",
    "fix": "Decide first-chunk state on model-output bytes, not any transport chunk: either have call sites signal when real content begins (e.g. keep the long timeout until an SSE data event containing choices/deltas is seen), or keep the long timeout for the first N seconds regardless of chunk count, or raise SSE_IDLE_TIMEOUT_MS enough to cover known silent reasoning gaps",
    "confidence": 50,
    "pre_existing": false
  },
  {
    "file": "extensions/copilot/src/platform/networking/common/fetcherService.ts",
    "line": 344,
    "severity": "High",
    "category": "async",
    "issue": "[ADV_CASCADE] OS suspend mid-stream → resume: libuv updates loop time and runs the now-expired watchdog in the timers phase BEFORE the poll phase delivers socket data that survived the sleep → timedOut=true, stream.destroy() discards the queued chunks → a stream that previously resumed seamlessly after wake now deterministically fails with StreamIdleTimeoutError on any suspend >60s (>120s pre-first-chunk), and per the classification gap it surfaces as a generic non-retried failure. The codebase itself confirms suspends during streaming are common (chatMLFetcher.ts:854 suspend/resume listeners, plus a power-save-blocker experiment to fight exactly this)",
    "fix": "On resume, give the stream one grace read instead of trusting the wall-clock timer: subscribe to IPowerService.onDidResume inside withStreamIdleTimeout and restart the timer (without destroying) if a resume occurred since the timer was armed; alternatively compare Date.now() elapsed-vs-armed before destroying in the timer callback",
    "confidence": 50,
    "pre_existing": false
  },
  {
    "file": "extensions/copilot/src/extension/prompt/node/chatMLFetcher.ts",
    "line": 2008,
    "severity": "Medium",
    "category": "error-handling",
    "issue": "[ADV_COMPOSITION] StreamIdleTimeoutError composes with none of the existing error taxonomy: hung connection → watchdog throws → chatMLFetcher.processError matches neither isAbortError, isCancellationError, 'Premature close', isInternetDisconnectedError, nor isFetcherError → falls to generic ChatFetchResponseType.Failed → the RetryNetworkErrors connectivity-check-and-retry path (line 575, gated on NetworkError) never runs and the user sees 'Error on conversation request. Check the log for more details.' — the one failure mode this PR targets (dead network path mid-stream) gets neither the network-flavored message nor the automatic retry built for network failures",
    "fix": "Add an explicit `err instanceof StreamIdleTimeoutError` (or name check) branch in processError returning ChatFetchResponseType.NetworkError with a hung-connection message, so the existing connectivity-check/retry machinery applies",
    "confidence": 100,
    "pre_existing": false
  },
  {
    "file": "extensions/copilot/src/platform/networking/common/fetcherService.ts",
    "line": 346,
    "severity": "Low",
    "category": "other",
    "issue": "[ADV_COMPOSITION] Watchdog destroy is invisible in stream telemetry as a hang: timer fires → stream.destroy() → reader.cancel() with no reason → propagates to the counting TransformStream's cancel(reason=undefined) in Response's constructor (fetcherService.ts:104-106) → `reason && !isAbortError(reason)` is false → responseStreaming FetchEvent outcome recorded as 'cancel', indistinguishable from a user cancellation → the hung-stream population this PR exists to fail-fast on is systematically misfiled as user cancels in fetch telemetry",
    "fix": "Pass the StreamIdleTimeoutError as the destroy/cancel reason (extend DestroyableStream.destroy(reason?) to forward it to reader.cancel(reason)) so the transformer's cancel handler classifies it as outcome 'error'",
    "confidence": 100,
    "pre_existing": false
  }
]
```

## Considered But Not Flagged

- **Chunk yielded after timer fired (yield-then-throw interleave)** — attempted: timer macrotask sets `timedOut` while a resolved-but-unprocessed chunk waits. Fell apart: a `reader.read()` resolution's continuation microtasks fully drain before any timer macrotask runs, and `reader.cancel()` resolves the pending read as `done` rather than delivering the chunk. The timer can only win when no chunk continuation is queued, so the "data arrived but timeout thrown anyway" ordering is unreachable in normal event-loop operation (it only reappears in the suspend/blocked-loop scenario reported above).
- **Server holds connection open after the final SSE event** — messagesApi/responsesApi never break on `[DONE]`/`message_stop` (the parser callback just returns), they exit only on stream close; a proxy dallying >60s after the final event would convert a fully-delivered response into StreamIdleTimeoutError. Not flagged: pre-change the same scenario hung the loop indefinitely (strictly worse), and I cannot verify any real endpoint delays close that long; AsyncIterableObject's buffered completions are drained by the fast inner consumer loop long before the 60s reject, so no data is dropped by the DoneError-before-results check in `next()`.
- **User cancels while idle-waiting → timeout misclassified as Failed instead of Canceled** — requires the fetcher to *not* abort the response body when the CancellationToken fires; `postRequest` wires the cancel token to the fetchers' abort handling, which rejects the pending read with an AbortError well before the watchdog fires. One unconfirmable step too many for the failure half.
- **`stream.destroy()` (timer) vs `iterator.return()` (finally) racing on `DestroyableStream.reader`** — traced: the timer callback is synchronous within its macrotask, generator resumptions are microtasks, so `this.reader` cannot be observed mid-teardown; `releaseLock()` after a settled `cancel()` is spec-legal, double-destroy degrades to an idempotent `stream.cancel()`. No corruption path found.
- **Timer leak / false timeout during slow consumers** — the timer is provably cleared before every `yield` and in the `finally`; consumer processing time (including `finishedCb` awaits in SSEProcessor and `parser.feed` in the API files) is never on the clock. The new test suite covers this correctly.
- **completions-core `SSEProcessor` (`extension/completions-core/vscode-node/lib/src/openai/stream.ts`) not wrapped** — inline-completion streams can still hang forever. Real gap, but it is a single-category coverage/consistency issue owned by the consistency/design reviewers, not an emergent interaction.

### Probe Requests

- **F1 classification probe** (if a validator can run vitest elsewhere): a unit test in `extensions/copilot/src/platform/networking/test/node/streamIdleTimeout.spec.ts` asserting `new StreamIdleTimeoutError(1000, false)` satisfies none of: `name === 'AbortError'`, `message === 'Premature close'`, `code === 'ERR_STREAM_PREMATURE_CLOSE'` — demonstrating it cannot reach any Canceled/NetworkError branch of `chatMLFetcher.processError` (chatMLFetcher.ts:1949-2016). Expected outcome: passes, confirming the generic-Failed classification.
