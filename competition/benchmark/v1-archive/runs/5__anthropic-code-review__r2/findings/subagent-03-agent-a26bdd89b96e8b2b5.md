# subagent agent-a26bdd89b96e8b2b5

I now have all the evidence needed. Here is the report.

## Findings: PR #308517 "Support timing out hung streams"

### Issue 1 (critical, confirmed by revert): Fixed 60s/120s idle timeouts kill healthy streams during known model-buffering pauses

- **File/line**: `extensions/copilot/src/platform/networking/common/fetcherService.ts:303-373` (`SSE_FIRST_CHUNK_TIMEOUT_MS = 120000`, `SSE_IDLE_TIMEOUT_MS = 60000`, `withStreamIdleTimeout`), consumed at `networking/node/stream.ts:323`, `endpoint/node/messagesApi.ts:596`, `endpoint/node/responsesApi.ts:537`.
- **Description**: `withStreamIdleTimeout` arms a plain `setTimeout` while awaiting `iterator.next()` and unconditionally calls `stream.destroy()` when it fires, treating "no chunk delivered within N ms" as equivalent to "connection is dead." But `DestroyableStream`'s iterator just forwards whatever chunks the underlying HTTP fetch produces — if the upstream/model server buffers a large amount of content (e.g. a big tool-call argument spanning thousands of lines) and doesn't flush any bytes for over a minute even though the connection is perfectly healthy and the model is still working, the watchdog cannot distinguish that from a truly hung socket. It destroys the live connection mid-response.
- **Historical reason (confirmed, not inference)**: This is exactly what happened. The PR was merged as `ba8d730b` on 2026-04-08, and reverted the very next day in `5a67f67236` / PR #308779 ("Revert 'Support timing out hung streams (#308517)'"), which fixes issue #308627. The PR author (lramos15, same author as #308517) commented directly on that issue:
  > "We've noticed Claude models tend to buffer large tool arguments before sending them back to us... you can have the model buffer this all and then return it in one big hunk at the end... The second error is because I pushed a change to try and prevent the model from hanging but it seems like it is too aggressive. I'm reverting that now."
  
  In other words, the author's own post-mortem confirms the mechanism I identified above.

### Issue 2 (systemic, confirmed by second revert): The same failure mode recurred in a later, more conservative attempt and was flagged pre-merge

- **Description**: This is not a one-off tuning mistake — it's a structural mismatch between "gap between chunk deliveries" and "stream health" that this codebase hit twice. Months later, issue #321432 documented that the underlying hung-stream problem was real and unaddressed (Anthropic Messages API stalling mid-stream with HTTP 200 headers already sent, causing full eval-harness-timeout hangs — ~18/30 errored instances in one eval run). A second, narrower fix (PR #321671, "Add stream-stall telemetry to Anthropic Messages streaming", merged 2026-06-17 as `f8574878be`) added a similar idle watchdog (this time 120s) scoped to just `messagesApi.ts`. Before merge, the automated PR reviewer explicitly warned:
  > "The new watchdog timeout handler can false-trigger due to event-loop timing unless it re-checks idleness before aborting, which can cause unnecessary stream aborts."
  
  It was merged anyway and reverted the same day, ~6 hours later, in PR #321842 ("Revert 'Add stream-stall telemetry to Anthropic Messages streaming (#321432)'", commit `f1339a4faf`).
- **Relevance to this PR**: The exact same structural weakness exists in `withStreamIdleTimeout` here: the timer is armed via `setTimeout` and fires unconditionally in its callback (`timedOut = true; void stream.destroy()...`) with no re-check of whether a chunk has actually just arrived or is imminent — precisely the "false-trigger due to event-loop timing" pattern the later reviewer called out. The unit tests added in `streamIdleTimeout.spec.ts` all use `vi.useFakeTimers()`, so they cannot exercise this real-event-loop race at all — they only validate the logical timer/next() ordering, not actual scheduling races between socket data-ready callbacks and timer callbacks under load.

### Net assessment

Both attempts to add this exact kind of client-side idle watchdog around these SSE bodies (this PR, and the later #321671) were merged and then reverted within 1 day due to false positives destroying live streams — the first because of documented large-buffer/TTFT-like stalls from the model provider, the second flagged pre-merge for the identical event-loop-race risk. A reviewer with access to this history would flag the same root problem in the current diff: a hard, provider-behavior-agnostic timeout value with no secondary confirmation step before destroying the stream is a known-bad approach in this exact codepath, and the PR should either not exist in this form or should be informed by why the two prior/later attempts failed (e.g., needs longer/adaptive thresholds informed by known model buffering behavior, and/or an idleness re-check before destroying, and/or should ship as observe-only telemetry first as #321671 initially — though notably even that "observe-only" framing didn't survive, since the actual merged commit for #321671 says it "rejects the iterator and cancels the underlying reader" despite the PR description claiming no behavior change).

No issues found regarding ordering/duplication of existing abort/cancel semantics in `SSEProcessor.cancel()`/`maybeCancel()` (`stream.ts:672-682`) — the pre-existing unconditional `this.cancel()` in `processSSE`'s `finally` block composes safely (if redundantly) with `withStreamIdleTimeout`'s own cleanup, since `DestroyableStream.destroy()` is idempotent once the reader lock has been released.
