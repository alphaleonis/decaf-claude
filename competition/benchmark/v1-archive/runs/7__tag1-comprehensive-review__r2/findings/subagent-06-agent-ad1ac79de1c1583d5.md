# subagent agent-ad1ac79de1c1583d5

## Summary

Extracts the chunked-remote-read querier acquisition and `Select` call into a new `getChunkSeriesSet` helper so the `ChunkQuerier`'s `defer querier.Close()` fires when the helper returns, instead of at the end of the enclosing per-query closure. This closes the querier immediately after building the `ChunkSeriesSet` rather than holding it open through the full `StreamChunkedReadResponses` streaming/encoding pass, reducing memory held by misbehaving or slow chunked remote-read requests. Error handling changes accordingly: a `ChunkQuerier` creation failure now returns `storage.ErrChunkSeriesSet(err)` (checked via `chunks.Err()`) instead of an early function return.

**Type:** bugfix
**Effort:** 2/5 — single-file mechanical extraction (+32/-21 lines), no new dependencies or API surface, behavior-preserving aside from the intended earlier-close fix

## Walkthrough

| File | Change | Summary |
|------|--------|---------|
| storage/remote/read_handler.go | Modified | Moves `ChunkQuerier` acquisition + `Select` into new `getChunkSeriesSet` helper so its `defer Close()` runs before streaming begins, closing the querier earlier to curb OOM risk on broken/streamed chunked read requests |

## Related Issues & PRs

<!-- issue-linker output will be merged here — the orchestrator replaces this placeholder -->
