# subagent agent-aa3b8a3f7a5b14608

## Summary

**PR Title & Author:** "Support timing out hung streams" by Logan Ramos (lramos15)

**What the change does:**

This PR adds timeout protection for Server-Sent Event (SSE) streams used in VS Code's Copilot extension. The change implements an idle watchdog that monitors stream activity and destroys hung connections. It uses a longer timeout (2 minutes) for the first chunk to account for model latency, then switches to a shorter timeout (1 minute) for subsequent chunks. If no chunk arrives within the active timeout, the stream is destroyed and a `StreamIdleTimeoutError` is thrown. This prevents the extension from hanging indefinitely when a network connection stalls without closing.

**Files changed:**

| File | Change |
|------|--------|
| `extensions/copilot/src/platform/networking/common/fetcherService.ts` | Added `withStreamIdleTimeout()` async generator, timeout constants (`SSE_FIRST_CHUNK_TIMEOUT_MS`, `SSE_IDLE_TIMEOUT_MS`), and `StreamIdleTimeoutError` class |
| `extensions/copilot/src/platform/endpoint/node/messagesApi.ts` | Wrapped `response.body` with `withStreamIdleTimeout()` in stream iteration |
| `extensions/copilot/src/platform/endpoint/node/responsesApi.ts` | Wrapped `response.body` with `withStreamIdleTimeout()` in stream iteration |
| `extensions/copilot/src/platform/networking/node/stream.ts` | Wrapped `this.body` with `withStreamIdleTimeout()` in SSE processor |
| `extensions/copilot/src/platform/networking/test/node/streamIdleTimeout.spec.ts` | New test suite with 7 test cases covering timeout behavior, consumer processing, and edge cases |

**Head commit SHA:** `4d10215261da24a7e07984df4a4ce8916bae87ba`
