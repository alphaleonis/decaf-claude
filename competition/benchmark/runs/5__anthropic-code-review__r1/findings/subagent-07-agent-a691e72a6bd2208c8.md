# subagent agent-a691e72a6bd2208c8

## Summary: Support timing out hung streams (PR #308517)

**Author:** Logan Ramos  
**Merge Commit:** ba8d730bd0ebf0c6b8b65cfee3016dffbe1592c9  
**Linked Issue:** microsoft/vscode-internalbacklog#7390

### Problem Solved
Addresses hung SSE (Server-Sent Events) streams that stop receiving data due to network issues, connection hangs, or stalled servers. Without this timeout, the VS Code Copilot extension could hang indefinitely waiting for chunks from LLM APIs (Anthropic, OpenAI).

### Approach
Introduces a reusable `withStreamIdleTimeout` async generator wrapper that adds deadline-based monitoring to stream consumption:

- **Two-tier timeout strategy:** 2-minute timeout for the first chunk (accounts for model's time-to-first-token), then 60-second timeout for subsequent chunks (detects stalls mid-stream).
- **Precision timing:** Timer runs only while awaiting network data (`iterator.next()`), not while the consumer processes yielded chunks, avoiding false timeouts on slow consumers.
- **Clean failure:** Throws `StreamIdleTimeoutError` with contextual messages ("first chunk" vs "inactivity") and destroys the underlying stream on timeout.

### Files Changed (5 files, 270 additions)

| File | Change |
|------|--------|
| **fetcherService.ts** | Core implementation: `withStreamIdleTimeout` async generator, `StreamIdleTimeoutError` class, timeout constants. 84 lines added. |
| **messagesApi.ts** | Wraps `response.body` in `withStreamIdleTimeout()` within `processResponseFromMessagesEndpoint`. |
| **responsesApi.ts** | Same wrapper applied in `processResponseFromChatEndpoint` for chat endpoint streams. |
| **stream.ts** | Wraps `this.body` in `withStreamIdleTimeout()` within SSEProcessor for core stream processing. |
| **streamIdleTimeout.spec.ts** (new) | 186-line test suite covering: happy paths (fast streams), timeout scenarios (first chunk / stalled chunks), timeout boundary conditions, differentiation between timeout tiers, edge cases (slow consumers, early break). |

The implementation is defensive: timers are cleared after chunk arrival and in finally blocks to prevent dangling timeouts or reader lock issues.
