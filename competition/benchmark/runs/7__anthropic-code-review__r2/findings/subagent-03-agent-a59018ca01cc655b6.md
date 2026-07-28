# subagent agent-a59018ca01cc655b6

## Summary

**One confirmed bug**, backed by direct historical evidence from the upstream repository (I ran `git fetch --unshallow` since the local checkout only had 3 commits of history):

**Bug: querier closed before its lazily-iterated ChunkSeriesSet is consumed**
`storage/remote/read_handler.go:216` (new `getChunkSeriesSet` helper)

- The original code (going back to commit `b788986717`, which first introduced this streaming handler) wraps `querier.Select(...)` and the full `StreamChunkedReadResponses(...)` call inside the *same* per-query anonymous function that holds `defer querier.Close()`. That structure exists precisely because `Select()` returns a lazy `ChunkSeriesSet` — for TSDB's `blockChunkQuerier` (`tsdb/querier.go`), the returned set holds direct references to the querier's `IndexReader`/`ChunkReader` and only reads chunk bytes when `StreamChunkedReadResponses` calls `.Next()`/`.At()`/`.Iterator()` on it. `blockBaseQuerier.Close()` releases (mmap-unmaps) exactly those resources.
- PR #13777 splits this: `getChunkSeriesSet` calls `Select()` and then closes the querier via `defer` *before returning*, handing back an already-orphaned `ChunkSeriesSet` that `StreamChunkedReadResponses` iterates afterward in the caller.
- This is not [Speculation] — it's directly verified: the change (`53091126c2`, cherry-picked to a release branch as `47a61a126e`) was reverted five months later in commit `6e89250a5d`, whose message states: *"Believed to trigger segmentation faults due to memory-mapped block data still being accessed by iterators after the querier is closed."* The revert was itself backported to multiple release branches (`72d84f511f`, `03963b9ba0`, PR `revert-13777-remoteread2`). Checking `origin/main` today confirms the original single-scope `defer` pattern was never re-introduced — the "close earlier" optimization was abandoned entirely.

No other issues found in this diff beyond the one reported via `ReportFindings`.
