# subagent agent-a693ed17fb3246be8

```json
{
  "finding": "#4",
  "verdict": "confirmed",
  "reason": "All three merged facets check out against the actual code. (1) fetcherService.ts:362 sets `isFirstChunk = false` unconditionally after any successful `iterator.next()`, with no inspection of chunk content — confirmed by the wrapper's own test suite (streamIdleTimeout.spec.ts), where every `push()` call, regardless of payload, resets the watchdog. (2) stream.ts:409 literally reads \"An initial chunk is sent with an empty choices array and no id, to hold `prompt_filter_results`\" — a documented, non-model-output administrative CAPI chunk that precedes real content and would legitimately trigger the isFirstChunk flip, collapsing the intended 2-minute TTFT budget to 60s for that path exactly as claimed. (3) messagesApi.ts:687 confirms Anthropic's protocol includes an early `message_start` event type the client already special-cases, consistent with the claim that non-content administrative events arrive first on that path too (exact ~1s timing for message_start/response.created is an external, unverifiable-from-repo fact and I label it as such). (4) No configurability exists anywhere: `SSE_FIRST_CHUNK_TIMEOUT_MS`/`SSE_IDLE_TIMEOUT_MS` are plain exported constants with zero config/experiment wiring, unlike the sibling `ConfigKey.TeamInternal.RetryNetworkErrors` experiment-gated flag (configurationService.ts:855, used at chatMLFetcher.ts:575) — confirming the absence-of-kill-switch claim by direct contrast with an existing pattern in the same codebase. The security-reviewer's ping/keep-alive dissent is not refuted but also not substantiated in-repo: SSE comment lines (':' prefix) are indeed parsed and skipped by both stream.ts:336 and sseParser.ts:138, and such comment bytes would indeed arrive as raw transport chunks and reset the timer per the wrapper's content-agnostic design — but nothing in this repository shows Anthropic/OpenAI/CAPI actually emit such pings during silent reasoning phases; that is an external backend behavior outside static verification, so it narrows but does not eliminate the risk. The mechanism, the stream.ts documentation quote, and the configurability gap are all independently re-derivable from the code as cited.",
  "corrections": {
    "pre_existing": false
  }
}
```
