# subagent agent-aa6a47d6b522e7726

## Summary

Extracts the `ChunkQuerier` creation and `Select()` call out of `remoteReadStreamedXORChunks` into a new helper, `getChunkSeriesSet`. Because the `defer querier.Close()` now lives inside the helper instead of the outer streaming function, the querier is closed as soon as the `ChunkSeriesSet` is obtained, rather than being held open for the lifetime of the entire chunked-response write. The author reports this is a response to Prometheus instances misbehaving (OOMs) on broken chunked remote-read requests, where the querier previously stayed open for the full duration of the write.

**Type:** Bugfix
**Effort:** 2/5 — single-file, mechanical extract-method refactor (+32/-21) with no new tests or API surface change

## Walkthrough

| File | Change | Summary |
|------|--------|---------|
| storage/remote/read_handler.go | Modified | Extracted querier creation/`Select()` into new `getChunkSeriesSet` helper so the `ChunkQuerier` is `defer`-closed immediately on return from the helper instead of at the end of `remoteReadStreamedXORChunks`, releasing querier resources earlier during chunked remote-read streaming |

## Related Issues & PRs

<!-- issue-linker output will be merged here — the orchestrator replaces this placeholder -->
