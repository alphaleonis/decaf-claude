# subagent agent-afd2382cbcfd38579

## Summary

**Contradiction found: `storage/remote/read_handler.go:239-266` (`getChunkSeriesSet`)**

The new `getChunkSeriesSet` closes the `ChunkQuerier` via `defer querier.Close()` (line 247-251) as soon as it returns from `Select(...)` (line 265). The returned `storage.ChunkSeriesSet` is then handed to `StreamChunkedReadResponses` at line 210-218 in `remoteReadStreamedXORChunks`, which is where iteration (`Next()`/`At()`/chunk `Iterator()`) actually happens — *after* the querier has already been closed.

This contradicts the querier-lifetime guidance documented in `storage/interface.go`:
- Line 171: `// Close releases the resources of the Querier.`
- Line 161 (sibling method on the same `LabelQuerier` interface embedded by `ChunkQuerier`): `// It is not safe to use the strings beyond the lifetime of the querier.`

For the default production path (`web/api/v1/api.go:277` → `tsdb.DB.ChunkQuerier`), `Select()` does not eagerly materialize results — verified in `tsdb/querier.go`: `blockBaseSeriesSet.Next()` (line 558) reads lazily via `b.index.Series(...)`, and `chunkSeriesEntry.Iterator()` (line 773) reads chunk bytes lazily via the querier-owned `ChunkReader`. `blockBaseQuerier.Close()` (lines 103-115) closes both `q.index` and `q.chunks`, and `chunks.Reader.Close()` (`tsdb/chunks/chunks.go:656`) munmaps the underlying block files. So by the time `StreamChunkedReadResponses` iterates, it's reading from resources the querier already released.

This isn't speculative — the PR was reverted upstream in commit `6e89250a5d` ("Revert 'Chunked remote read: close the querier earlier'"), with the message: *"Believed to trigger segmentation faults due to memory-mapped block data still being accessed by iterators after the querier is closed."* The revert corroborates the exact contradiction identified from the comments.

Filed as a single finding via `ReportFindings` (verdict: CONFIRMED).
