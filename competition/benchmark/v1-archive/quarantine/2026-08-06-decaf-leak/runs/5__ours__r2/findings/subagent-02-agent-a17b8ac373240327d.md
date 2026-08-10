# subagent agent-a17b8ac373240327d

```json
{
  "finding": "#7",
  "verdict": "confirmed",
  "reason": "All three load-bearing claims independently verify: (1) BYOK local/self-hosted providers (e.g. OllamaLMProvider) route through AbstractOpenAICompatibleLMProvider -> OpenAIEndpoint (extends ChatEndpoint) -> ChatEndpoint.processResponseFromChatEndpoint (chatEndpoint.ts:359-378), which for non-Responses/non-Messages models falls to defaultChatResponseProcessor -> SSEProcessor.processSSE, which calls withStreamIdleTimeout at stream.ts:323 — one of the three cited wrapped call sites, so the Ollama TTFT-kill scenario is real and not something a separate SDK path bypasses; (2) grep across the repo shows no config key, experiment flag, or per-endpoint override for SSE_FIRST_CHUNK_TIMEOUT_MS/SSE_IDLE_TIMEOUT_MS, and withStreamIdleTimeout's signature (fetcherService.ts:328-330) is exactly `(stream: DestroyableStream<T>): AsyncGenerator<T>` with no options parameter, confirming zero configurability; (3) ConfigKey.TeamInternal.RetryNetworkErrors is a genuine ExperimentBased setting (configurationService.ts:855) consumed via getExperimentBasedConfig in chatMLFetcher.ts:575, confirming the cited adjacent convention is real, not fabricated.",
  "corrections": null
}
```
