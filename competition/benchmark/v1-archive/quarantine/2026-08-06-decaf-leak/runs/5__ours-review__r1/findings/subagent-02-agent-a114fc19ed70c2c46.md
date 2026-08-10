# subagent agent-a114fc19ed70c2c46

Based on my analysis, I can now provide my verdict on this finding.

## Summary of Investigation

I traced the complete error handling path for `StreamIdleTimeoutError`:

1. **Error Definition** (fetcherService.ts:312-318): `StreamIdleTimeoutError` extends `Error` with `name = 'StreamIdleTimeoutError'` but NO `code` property.

2. **Error Throw Site** (fetcherService.ts:373): Thrown from `withStreamIdleTimeout` when an SSE stream times out waiting for chunks.

3. **Error Usage** (responsesApi.ts, messagesApi.ts, stream.ts): `withStreamIdleTimeout` wraps the HTTP response body during SSE streaming.

4. **Error Classification** (chatMLFetcher.ts:1949-2016, `processError` method):
   - Line 1957: `isAbortError(err)` → FALSE (name is 'StreamIdleTimeoutError', not 'AbortError')
   - Line 1965: `isCancellationError(err)` → FALSE
   - Line 1973-1975: "Premature close" check → FALSE (message doesn't match)
   - Line 1989: `isInternetDisconnectedError(err)` → FALSE (nodeFetcher always returns false)
   - Line 1997: `isFetcherError(err)` → **FALSE** (StreamIdleTimeoutError has no `code` property; isFetcherError checks for `e.code ∈ {EADDRINUSE, ECONNREFUSED, ECONNRESET, ENOTFOUND, EPIPE, ETIMEDOUT}`)
   - Line 2007-2015: Falls through to final `else` → Returns **`ChatFetchResponseType.Failed`**

5. **Retry Logic** (chatMLFetcher.ts:575-576):
   - On HTTP path: `useWebSocket = false`, so `retryWithoutWebSocket` is always false despite the error being classified as `Failed`
   - `retryNetworkError` only triggers if error is `NetworkError` (which it's not)
   - **No retry occurs on plain-HTTP streaming path**

6. **On WebSocket Path** (by contrast): `retryWithoutWebSocket` condition includes `(processed.type === ChatFetchResponseType.NetworkError || processed.type === ChatFetchResponseType.Failed)`, so WebSocket requests with Failed errors WOULD retry via HTTP fallback.

```json
{
  "finding": "StreamIdleTimeoutError is not integrated into the fetcher error taxonomy",
  "verdict": "confirmed",
  "reason": "StreamIdleTimeoutError lacks a `code` property, fails all error-type classifiers (isAbortError, isInternetDisconnectedError, isFetcherError), and falls through to ChatFetchResponseType.Failed at line 2009. On the HTTP streaming path, Failed errors are not retried (retryWithoutWebSocket requires useWebSocket=true). The error is only retried on WebSocket transport where retry-on-fallback exists.",
  "corrections": {}
}
```
