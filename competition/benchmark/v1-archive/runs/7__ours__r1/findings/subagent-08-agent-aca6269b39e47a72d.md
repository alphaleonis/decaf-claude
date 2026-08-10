# subagent agent-aca6269b39e47a72d

All three sub-questions are independently verified from the actual code:

1. **Iteration happens after Close**: `remoteReadStreamedXORChunks` (read_handler.go:205-214) calls `h.getChunkSeriesSet(...)` (which returns after its `defer querier.Close()` has already fired) and only afterward passes the resulting `chunks` set into `StreamChunkedReadResponses`.
2. **Chunk reads are lazy and touch closed resources**: `StreamChunkedReadResponses` (codec.go:235-266) calls `ss.At()` → `series.Iterator(iter)` → `iter.Next()`/`iter.At()` during streaming — all after the querier (and its embedded `ChunkReader`) was closed. Traced through `blockChunkQuerier.Select` → `NewBlockChunkSeriesSet` (querier.go:174-196, 1158-1180), the returned `chunkSeriesEntry` holds `b.chunks` (the same `blockChunkReader` instance closed by `blockBaseQuerier.Close()` at querier.go:103-115). `blockChunkReader.Close()` (block.go:567-569) calls `r.b.pendingReaders.Done()` on the parent `Block`, and `Block.Close()` (block.go:378-390, used by compaction/retention) calls `pendingReaders.Wait()` before closing/unmapping `pb.chunkr`. Since `Done()` already fired at `getChunkSeriesSet` return time, the pending-readers guard is defeated well before the lazy iteration in `StreamChunkedReadResponses` actually touches the mmap'd chunk data.
3. **Sibling `remoteReadSamples` is unaffected**: read_handler.go:117-187 fully materializes results via `ToQueryResult(querier.Select(...))` at line 161, inside the same function scope as its `defer querier.Close()` (line 141-145) — no lazy iteration escapes the deferred-close scope.

The resource-lifecycle contract violation is fully re-derivable from the code, independent of the exact crash signature (SIGSEGV/SIGBUS vs. corrupted data), which the finding itself correctly labels as inference.

```json
{
  "finding": "#1",
  "verdict": "confirmed",
  "reason": "Traced the full chain in code: getChunkSeriesSet (read_handler.go:242-266) closes the querier via defer before returning the lazy ChunkSeriesSet; StreamChunkedReadResponses (codec.go:235-266) iterates it afterward, calling series.Iterator()/iter.Next() which reads through blockChunkQuerier's ChunkReader (querier.go:174-196, 1158-1180) — the same reader instance closed by blockBaseQuerier.Close() (querier.go:103-115). blockChunkReader.Close() (tsdb/block.go:567-569) calls pendingReaders.Done() prematurely, defeating the guard that Block.Close() (block.go:378-390, used by compaction/retention) relies on via pendingReaders.Wait() before unmapping segment files. Sibling remoteReadSamples (read_handler.go:117-187) is confirmed unaffected — it fully materializes via ToQueryResult inside the same deferred-close scope.",
  "corrections": {
    "pre_existing": false
  }
}
```
