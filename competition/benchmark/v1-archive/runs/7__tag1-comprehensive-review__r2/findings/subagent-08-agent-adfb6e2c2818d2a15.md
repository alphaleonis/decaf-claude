# subagent agent-adfb6e2c2818d2a15

## Finding

**Location:** `storage/remote/read_handler.go`, `getChunkSeriesSet` (lines 242–266), specifically the placement of the `defer querier.Close()` at lines 247–251 relative to the `return querier.Select(...)` at line 265; consuming code at lines 205–214 (`remoteReadStreamedXORChunks`).

**Severity: CRITICAL** — not a swallowed-error bug in the classic sense, but a resource-lifetime violation that can produce a failure mode *worse* than a silent failure: no error at all (data corruption) or an unrecoverable process crash that no `catch`/`defer`/logging path can intercept.

### Direct answers to the three questions

**(1) Does `chunks.Err()` reliably surface the querier-creation error?** Yes, verified. `storage.ErrChunkSeriesSet` (storage/interface.go:402-403) returns `errChunkSeriesSet{err: err}`, whose `Next()` always returns `false`, `At()` returns `nil`, and `Err()` returns the wrapped error (storage/interface.go:396-399). Since `Next()` is `false`, `StreamChunkedReadResponses`'s `for ss.Next()` loop body never runs and it falls through to `return ss.Warnings(), ss.Err()` (storage/remote/codec.go:296), which also yields the same error. Belt-and-suspenders — no regression here.

**(2) Could an error now be swallowed?** Not in the sense of a dropped Go `error` value — Select-time/lazy-iteration errors were always surfaced only via `SeriesSet.Err()` at the end of iteration (both before and after this diff; `ChunkQuerier.Select` never returned an `error` directly, even in the old code). That part is unchanged and correct.

The real defect is more severe than error swallowing: **`getChunkSeriesSet` now closes the querier via `defer` at the moment `Select()` returns — before `StreamChunkedReadResponses` ever calls `Next()`/`At()` on the returned `ChunkSeriesSet`.** I traced this through the actual TSDB implementation:

- `blockChunkQuerier.Select()` (tsdb/querier.go:174-195) builds the returned `ChunkSeriesSet` directly on top of `q.index` and `q.chunks` — i.e. `NewBlockChunkSeriesSet(q.blockID, q.index, q.chunks, ...)`. These are **lazy** references; chunk bytes are read from `q.chunks` on demand during iteration, not eagerly copied at `Select()` time.
- `q.chunks` is `blockChunkReader{ChunkReader: pb.chunkr, b: pb}` (tsdb/block.go:436-441) — a thin wrapper around the **block-level, shared** `pb.chunkr` mmap reader.
- `blockChunkReader.Close()` (tsdb/block.go, ~line 568) does **not** close `pb.chunkr`; it only calls `r.b.pendingReaders.Done()` — decrementing a `sync.WaitGroup` on the `*Block`.
- `Block.Close()` (tsdb/block.go:377-390), called during compaction/retention cleanup when a block is superseded and deleted (`tsdb/db.go` `reloadBlocks` → `deleteBlocks`), does `pb.pendingReaders.Wait()` **before** actually closing/unmapping `pb.chunkr`/`pb.indexr`. This WaitGroup exists specifically to guarantee a block's mmap isn't unmapped while any querier is still in use.

The old code deferred `querier.Close()` until after `StreamChunkedReadResponses` fully consumed the series set, so `pendingReaders` stayed non-zero for the query's entire duration — correctly blocking `Block.Close()` from proceeding. The new code decrements `pendingReaders` immediately after `Select()` returns, then hands a still-lazy `ChunkSeriesSet` — that will keep reading from `q.chunks`/`q.index` for the whole HTTP streaming response (which can run long: `StreamChunkedReadResponses` writes one frame per `stream.Write` call, blocking on a potentially slow client) — back to the caller. If Prometheus's background compaction loop (`tsdb/db.go` `run()` → periodic `reloadBlocks`) supersedes and deletes that same block *while the chunked remote-read is still streaming*, `Block.Close()` can complete `pendingReaders.Wait()` (since our early `Close()` already signaled "done"), unmap the chunk/index files, and the still-iterating `ChunkSeriesSet` then reads through a reader whose backing mmap has been released — a use-after-close on shared, mmap-backed memory. This can silently return corrupted chunk bytes to the remote-read client (no error, no log — the worst kind of silent failure) or hit a fatal, unrecoverable Go runtime memory fault that no `defer`/`recover`/logging in this file can catch.

**(3) Is `querier.Close()`'s error still observable?** Yes — the log call itself (`level.Warn(h.logger).Log("msg", "Error on chunk querier close", "err", err.Error())`) is textually unchanged and still fires via `defer`, just relocated into `getChunkSeriesSet`. No regression in *that* log path per se. But this masks the real issue: the defect isn't in whether the Close() error is logged, it's in *when* Close() runs relative to the data it protects still being read.

### Hidden failure modes introduced
- Silent data corruption served to remote-read clients (wrong/garbage chunk bytes, no error surfaced) if a block is deleted mid-stream.
- A hard process crash (SIGSEGV from accessing unmapped memory) with zero opportunity for any error handler, log statement, or Sentry-style capture to run — the ultimate silent failure.
- The race window is not a rare edge case: compaction/retention block deletion runs on a routine background timer in every live Prometheus server, and chunked remote-read of historical (non-Head) time ranges is a common, sometimes long-running, workload.

### Recommendation
Don't close the `ChunkQuerier` until the `ChunkSeriesSet` it produced has been fully iterated. Either:
- keep `querier.Close()` deferred in the outer function (as in the old code), after `StreamChunkedReadResponses` has consumed `chunks`, rather than inside `getChunkSeriesSet`; or
- if closing "earlier" for OOM-avoidance (per the commit message's stated intent) is still desired, only do so *after* `StreamChunkedReadResponses` returns, e.g. by having `getChunkSeriesSet` return `(storage.ChunkSeriesSet, func() error)` (a closer) and calling that closer immediately after the streaming call completes, instead of via a `defer` that fires before consumption starts.

Example fix (minimal, preserves the "release resources promptly" intent without breaking the pendingReaders invariant):

```go
chunks, closeQuerier := h.getChunkSeriesSet(ctx, query, filteredMatchers)
if err := chunks.Err(); err != nil {
    closeQuerier()
    return err
}
ws, err := StreamChunkedReadResponses(..., chunks, ...)
closeQuerier() // only now, after iteration is complete
if err != nil {
    return err
}
```

with `getChunkSeriesSet` returning the querier's `Close` as a separate value instead of deferring it internally.
