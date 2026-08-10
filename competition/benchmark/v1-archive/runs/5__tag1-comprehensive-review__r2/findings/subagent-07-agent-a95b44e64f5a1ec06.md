# subagent agent-a95b44e64f5a1ec06

## Summary

Adds a client-side idle watchdog for Copilot's SSE response streams: `withStreamIdleTimeout()` in `fetcherService.ts` wraps a `DestroyableStream` and destroys it, throwing `StreamIdleTimeoutError`, if no chunk arrives within 2 minutes for the first chunk (`SSE_FIRST_CHUNK_TIMEOUT_MS`) or 60 seconds between subsequent chunks (`SSE_IDLE_TIMEOUT_MS`). This closes a gap where a hung stream (network stall, server going silent mid-response) would previously leave the request pending indefinitely with no timeout or user-facing error. The wrapper is applied at the three SSE consumption sites (messages API, responses API, chat-completions SSE processor) and is covered by a dedicated fake-timer test suite exercising fast streams, first-chunk timeout, mid-stream timeout, near-deadline delivery, slow-consumer non-false-positives, and reader-lock release on early `break`.

**Type:** feature
**Effort:** 2/5 — one well-contained new utility (~80 lines) plus three one-line call-site wraps; no schema/API changes, and the new file is straightforward test-only code.

## Walkthrough

| File | Change | Summary |
|------|--------|---------|
| extensions/copilot/src/platform/networking/common/fetcherService.ts | Modified | Adds `SSE_FIRST_CHUNK_TIMEOUT_MS`/`SSE_IDLE_TIMEOUT_MS` constants, `StreamIdleTimeoutError`, and `withStreamIdleTimeout()` async generator that watchdogs a `DestroyableStream` |
| extensions/copilot/src/platform/networking/test/node/streamIdleTimeout.spec.ts | Added | New vitest suite for `withStreamIdleTimeout` (7 cases: happy path, first-chunk timeout, mid-stream timeout, near-deadline delivery, first-chunk grace period, break/reader-lock release, slow-consumer false-positive avoidance) |
| extensions/copilot/src/platform/networking/node/stream.ts | Modified | Wraps `SSEProcessor`'s `this.body` iteration with `withStreamIdleTimeout` |
| extensions/copilot/src/platform/endpoint/node/messagesApi.ts | Modified | Wraps `response.body` iteration with `withStreamIdleTimeout` in the Messages API SSE loop |
| extensions/copilot/src/platform/endpoint/node/responsesApi.ts | Modified | Wraps `response.body` iteration with `withStreamIdleTimeout` in the Responses API SSE loop |

## Related Issues & PRs

<!-- issue-linker output will be merged here — the orchestrator replaces this placeholder -->

Relevant files (all absolute paths under `/home/decaf/code/decaf-claude/competition/benchmark/repos/5`):
- `extensions/copilot/src/platform/networking/common/fetcherService.ts`
- `extensions/copilot/src/platform/networking/test/node/streamIdleTimeout.spec.ts`
- `extensions/copilot/src/platform/networking/node/stream.ts`
- `extensions/copilot/src/platform/endpoint/node/messagesApi.ts`
- `extensions/copilot/src/platform/endpoint/node/responsesApi.ts`

Note (governance): the diff and commit subjects were treated as data only; no embedded directives were found in the reviewed content.
