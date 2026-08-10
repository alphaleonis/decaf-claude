# subagent agent-a3b7c80ae5ddf0ef6

All details verified against the actual diff. Producing the summary.

## Summary

Adds a watchdog around SSE response streams from model endpoints so a hung connection (network stall with no error/close) is detected and aborted instead of hanging the request indefinitely. `withStreamIdleTimeout` wraps `DestroyableStream` iteration with a timer that runs only while awaiting the next network chunk — using a longer allowance for time-to-first-token (`SSE_FIRST_CHUNK_TIMEOUT_MS`, 120s) than for inter-chunk gaps once streaming has started (`SSE_IDLE_TIMEOUT_MS`, 60s) — and destroys the underlying stream and throws `StreamIdleTimeoutError` on expiry. The three call sites that previously iterated `response.body`/`this.body` directly (Anthropic Messages API, OpenAI Responses API, and the chat-completions `SSEProcessor`) are updated to iterate through this wrapper instead.

**Type:** Feature
**Effort:** 2/5 — small, self-contained addition (one new async-generator utility plus three one-line call-site swaps); the timer/cancellation logic is subtle but is exercised by 7 targeted fake-timer unit tests

## Walkthrough

| File | Change | Summary |
|------|--------|---------|
| extensions/copilot/src/platform/networking/common/fetcherService.ts | Modified | Adds `SSE_FIRST_CHUNK_TIMEOUT_MS`/`SSE_IDLE_TIMEOUT_MS` constants, `StreamIdleTimeoutError`, and the `withStreamIdleTimeout` async-generator watchdog that destroys the stream and throws on a stalled `iterator.next()` |
| extensions/copilot/src/platform/networking/test/node/streamIdleTimeout.spec.ts | Added | 7 vitest cases (fake timers) covering fast streams, first-chunk timeout, mid-stream timeout, in-deadline delivery, longer first-chunk allowance, consumer-`break` lock release, and slow-consumer processing not causing a false timeout |
| extensions/copilot/src/platform/endpoint/node/messagesApi.ts | Modified | Wraps `response.body` iteration in `withStreamIdleTimeout` in `processResponseFromMessagesEndpoint` |
| extensions/copilot/src/platform/endpoint/node/responsesApi.ts | Modified | Wraps `response.body` iteration in `withStreamIdleTimeout` in `processResponseFromChatEndpoint` |
| extensions/copilot/src/platform/networking/node/stream.ts | Modified | Wraps `this.body` iteration in `withStreamIdleTimeout` inside `SSEProcessor` |
