# subagent agent-ac811d5095d37a3bb

Based on my thorough investigation of the code, I can now provide my assessment:

SCORE: 75

The issue is verified as real. I confirmed:

1. **StreamIdleTimeoutError is not handled in processError**: Grep confirms it's never referenced in chatMLFetcher.ts, and reading processError (lines 1949-2016) shows it only checks for isAbortError, isCancellationError, 'Premature close'/ERR_STREAM_PREMATURE_CLOSE, isInternetDisconnectedError, and isFetcherError.

2. **It falls to the generic failure path**: Since StreamIdleTimeoutError extends plain Error (not one of the recognized types), it hits the else clause (line 2007-2014) and returns ChatFetchResponseType.Failed.

3. **Retry logic is not triggered**: Line 575 shows retry only fires for ChatFetchResponseType.NetworkError; StreamIdleTimeoutError (classified as Failed) only gets retried in the WebSocket-to-HTTP fallback path (line 576), not for normal HTTP streaming.

4. **Historical precedent exists**: GitHub API confirmed commit 4922ed10342130a5b1d6864b5e8906a42523fb00 ("handle ERR_STREAM_PREMATURE_CLOSE as cancellation, not error") which established that new stream-termination modes must be added to processError.

5. **The timeout is transient**: SSE_FIRST_CHUNK_TIMEOUT_MS=2min and SSE_IDLE_TIMEOUT_MS=60sec are detection mechanisms for hung servers, clearly transient conditions warranting retry.

The defect is an omission: the PR's new error type bypasses the error-classification chain entirely, causing timeouts to be misclassified as unrecoverable hard failures when they should be retried automatically or at least handled like ERR_STREAM_PREMATURE_CLOSE.
