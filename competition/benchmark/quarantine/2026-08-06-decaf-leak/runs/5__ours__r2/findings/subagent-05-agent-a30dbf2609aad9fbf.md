# subagent agent-a30dbf2609aad9fbf

## Sibling-Consistency Review — PR #308517 (Support timing out hung streams)

Repo root: `/home/decaf/code/decaf-claude/competition/benchmark/repos/5`

### Method
Built a sibling census across: `platform/networking/common/fetcherService.ts` (`DestroyableStream`, error classes), the three wired-up consumers (`messagesApi.ts`, `responsesApi.ts`, `stream.ts`), every other `for await (const ... of ...body/stream)` consumer in the extension (grepped repo-wide), the async-timeout helpers in `util/vs/base/common/async.ts`, and the sibling spec files under `platform/networking/test/node/`.

### Findings

**1. [CONS_SYMMETRY] High / confidence 100 — `extensions/copilot/src/extension/completions-core/vscode-node/lib/src/openai/stream.ts:293`**
This file's `SSEProcessor` class is a near-duplicate of `platform/networking/node/stream.ts`'s `SSEProcessor`: identical class name, identical JSDoc ("Processes an HTTP request containing what is assumed to be an SSE stream of OpenAI API data..."), identical `private readonly body: DestroyableStream<string>` field, identical "Iterate over arbitrarily sized chunks coming in from the network" comment on the loop. The PR wrapped the twin's loop at `platform/networking/node/stream.ts:323` with `withStreamIdleTimeout(this.body)`, but left this sibling's `for await (const chunk of this.body)` untouched — no independent timeout mechanism exists in this file or its `fetch.ts` companion either. Ghost-text/inline-completion streams remain exposed to the same hang class this PR fixes for chat.
Fix: import `withStreamIdleTimeout` and wrap the loop the same way.

**2. [CONS_HELPER] Medium / confidence 100 — `extensions/copilot/src/platform/networking/common/fetcherService.ts:328-347`**
`withStreamIdleTimeout` hand-rolls a `setTimeout`/`clearTimeout` + boolean-flag state machine to race `iterator.next()` against a deadline, instead of using the codebase's established `raceTimeout<T>(promise, timeout, onTimeout)` helper (`util/vs/base/common/async.ts:152`), used the same way at `extension/tools/node/scmChangesTool.ts:116-119` and `platform/workspaceChunkSearch/node/codeSearch/codeSearchChunkSearch.ts:549`.
Fix: `const result = await raceTimeout(iterator.next(), timeoutMs, () => { timedOut = true; void stream.destroy().catch(() => {}); });` branching on `result === undefined` for the timeout path.

### Considered But Not Flagged
- `platform/nesFetch/node/completionsFetchServiceImpl.ts` / `responseStream.ts` also consume a `DestroyableStream`-backed `Response.body` via `streamWithCleanup` (a different generator wrapper, different feature area — NES prefetch, not chat). No duplicated class/comment like the completions-core case, so confidence for a targeted convention claim is below the reporting bar — noted but not flagged.
- `extension/byok/vscode-node/{geminiNativeProvider,anthropicProvider}.ts` iterate their own provider SDK streams, not `DestroyableStream`/`fetcherService`-based — no sibling relationship to the new wrapper.
- `util/common/asyncIterableUtils.ts` generator wrappers (`map`, `filter`, etc.) rely on the JS spec's automatic `.return()` propagation via `for await`; `withStreamIdleTimeout` must manually drive `iterator.next()`/`iterator.return?.()` to race per-iteration — a necessary structural difference, not drift.
- Test suite naming (`suite('withStreamIdleTimeout', () => {...})`) matches `headerContributors.spec.ts`'s bare-name style; siblings disagree with each other (`fetcherFallback.spec.ts`/`networking.spec.ts` append "Test Suite"), so no uniform convention exists to cite.
- `SSE_FIRST_CHUNK_TIMEOUT_MS`/`SSE_IDLE_TIMEOUT_MS` naming and inline `N * 60 * 1000` literal style match the codebase-wide pattern (`GATEWAY_IDLE_TIMEOUT_MS`, `RELEASE_DELAY_MS`, `CLEANUP_TIMEOUT_MS`, etc.) — consistent, no finding.
- "TTFT" abbreviation in the new doc comment matches existing usage in `chatMLFetcher.ts` and `xtabProvider.ts` — consistent, no finding.
- `void stream.destroy().catch(() => {})` matches the established swallow-error idiom already used at `platform/networking/node/nodeFetchFetcher.ts:82`.
- `StreamIdleTimeoutError extends Error` lacks a static `.is()` type guard (unlike `PendingMigrationError`), but sibling error classes in `errors.ts` disagree among themselves (`NotImplementedError`/`NotSupportedError`/`ExpectedError` have no such guard either) — not a uniform convention, not flagged.
- `withStreamIdleTimeout` naming matches the established `with*`-prefixed wrapper-function convention (`withHookOTelSpan`, `withAsyncBody`) — consistent, no finding.

### Probe Requests
None — both findings are static comparisons of existing code; no runnable probe would add signal given dependencies aren't installed in this checkout.
