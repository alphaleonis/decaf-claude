# subagent agent-a3f09c78459d9c7be

## Findings

```json
[
  {
    "file": "storage/remote/read_handler.go",
    "line": 247,
    "severity": "Critical",
    "category": "resource-management",
    "issue": "[BUG_RESOURCE] getChunkSeriesSet defers querier.Close() inside its own function body (lines 247-251) and then returns the lazily-consumed storage.ChunkSeriesSet (line 265) to the caller. The defer fires the instant getChunkSeriesSet returns — i.e. before StreamChunkedReadResponses (codec.go ~L235-261) ever calls ss.Next()/series.Iterator()/chk.Chunk.Bytes(). This is not merely a style nit: I traced the concrete data path. storage/remote/codec.go's StreamChunkedReadResponses reads chunk bytes lazily during iteration, not eagerly during Select(). For on-disk blocks, tsdb/querier.go's blockChunkQuerier.Select (L174-196) only resolves postings and returns an iterator (NewBlockChunkSeriesSet); actual chunk bytes are fetched later via tsdb/chunks/chunks.go Reader.ChunkOrIterable, which returns a slice (chkData := sgmBytes.Range(...)) directly into the block's mmap'd segment file — no copy. Each blockChunkReader.Close() (tsdb/block.go L567-568) does NOT close/unmap that shared mmap; it only calls pb.pendingReaders.Done() on a sync.WaitGroup that Block.Close() (L377-390, 'It blocks as long as there are readers reading from the block') waits on before actually closing/unmapping the chunk file during compaction or retention. By closing the querier before the ChunkSeriesSet is consumed, this refactor calls pendingReaders.Done() while the caller still holds live references into that block's mmap'd bytes and hasn't read them yet. If a compaction/retention Block.Close() runs concurrently in that window, the segment file gets unmapped while StreamChunkedReadResponses is still dereferencing chk.Chunk.Bytes() from it — a use-after-unmap that can crash the process or (less deterministically) return corrupted bytes to the remote-read client. This defeats the exact safety mechanism (pendingReaders WaitGroup) the on-disk block implementation relies on for safe unmapping, and does so specifically for the multi-block, longer-running chunked remote-read path this PR targets. The passing test suite doesn't catch it because promql.LoadedStorage only exercises the in-memory head (headChunkReader.Close() at tsdb/head_read.go L318-323 is nearly a no-op with no mmap to unmap), not a persisted/compacted block.",
    "fix": "Do not close the querier inside getChunkSeriesSet before the ChunkSeriesSet is consumed. Either (a) have getChunkSeriesSet return both the querier and the ChunkSeriesSet, and defer querier.Close() in remoteReadStreamedXORChunks after StreamChunkedReadResponses returns (restoring the original lifetime), or (b) fully materialize/copy the chunk data before returning from getChunkSeriesSet so nothing downstream depends on the querier's mmap after Close(). Simply moving `defer querier.Close()` into a helper that returns a still-to-be-iterated ChunkSeriesSet cannot safely shorten the querier's lifetime for this lazy-iteration API.",
    "confidence": 100,
    "pre_existing": false
  }
]
```

## Considered But Not Flagged

- **Duplication of the SelectHints-building block** between `remoteReadSamples` (lines 147-158) and the new `getChunkSeriesSet` (lines 253-264): this duplication already existed between `remoteReadSamples` and the old inline code in `remoteReadStreamedXORChunks` before this PR; the refactor only relocated it, it didn't introduce new duplication. Out of scope as a bug, and not a new convention violation.
- **`storage.ErrChunkSeriesSet(err)` on `ChunkQuerier` failure** (line 245): correctly propagates the error through `chunks.Err()` at the call site (line 206) instead of returning early with a raw error as before — verified this preserves equivalent behavior (the outer `errors.As(err, &httpErr)` / `http.Error` handling downstream is unchanged), not a regression.
- **Loss of the explicit early return on `ChunkQuerier` error**: previously the code did `return err` immediately from the outer closure on `ChunkQuerier` failure; now it flows through `chunks.Err()`. Checked that `storage.ErrChunkSeriesSet(err).Err()` returns the same `err`, so the resulting HTTP error behavior is identical — no behavior change.
- **Whether `Select()` itself eagerly loads chunk data** (which would have made the early Close safe): verified via `blockChunkQuerier.Select` (tsdb/querier.go L174-196) that it does not — it only expands postings and returns a lazy iterator, confirming the premature-close finding rather than dismissing it.
- **Head/WAL isolation-state release timing** (`headChunkReader.Close()` closing `isoState` early): plausible related concern (isolation state also gates visibility/truncation), but I could not fully verify from the code within scope whether head-chunk mmap truncation is similarly gated by open isolation states versus time-based retention, so I did not raise it as a separate finding to avoid diluting the confirmed block-querier defect above.
