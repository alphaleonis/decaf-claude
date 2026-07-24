# subagent agent-ac86284f1e73a7a75

## Summary

I researched the real GitHub history (via `gh api`/`gh pr`) of the four files this PR touches, in both `microsoft/vscode` and their upstream source repo `microsoft/vscode-copilot-chat`.

**Headline finding: this is a re-run of a change that was already tried and reverted.** PR #308517 itself was merged on 2026-04-08 and reverted the very next day by PR #308779 (https://github.com/microsoft/vscode/pull/308779), fixing https://github.com/microsoft/vscode/issues/308627. The PR author, lramos15, explained in the issue thread that Claude models buffer large tool-call arguments before flushing any bytes, and the new idle-timeout watchdog was "too aggressive" and killed those legitimate long gaps. The current diff reintroduces `withStreamIdleTimeout` in `fetcherService.ts` with the exact same `SSE_FIRST_CHUNK_TIMEOUT_MS`/`SSE_IDLE_TIMEOUT_MS` values and destroy-on-timeout mechanism as the reverted version, with no visible accommodation for that buffering scenario. I confirmed via search that no follow-up issue or re-land PR referencing #308517 exists on GitHub, so this root cause was never addressed before this reintroduction.

**Secondary findings (already resolved in the current code, included for traceability):** the original review of PR #308517 received three inline bot comments on `fetcherService.ts` — (1) the idle timer originally measured consumer processing time rather than network wait time, (2) `stream.destroy()`'s promise wasn't handled, and (3) early consumer termination didn't call `iterator.return()` on the underlying stream, leaking the reader lock. All three are already fixed in the current code (timer cleared before yield, `void stream.destroy().catch(...)`, and `await iterator.return?.()` in the `finally` block), each with dedicated test coverage in `streamIdleTimeout.spec.ts`.

I also checked adjacent prior PRs (#308445 "Surface network errors with proxies", vscode-copilot-chat #2914 "Fix timing issue with flags", #4533 "Log status code and request id on connection error") but their review comments (WebSocket test cleanup, telemetry PII sanitization, flag-reset ambiguity) don't meaningfully apply to this specific timeout change, so I did not report them as findings.

Files referenced: `extensions/copilot/src/platform/networking/common/fetcherService.ts`, `extensions/copilot/src/platform/networking/node/stream.ts`, `extensions/copilot/src/platform/endpoint/node/messagesApi.ts`, `extensions/copilot/src/platform/endpoint/node/responsesApi.ts`.
