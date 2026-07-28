# subagent agent-aa72465f80d3e317a

## Cost-at-Scale Review — `storage/remote/read_handler.go` (PR #13777)

### Investigation (per Additional Instructions)

Traced the actual resource-release semantics across `storage/remote/read_handler.go`, `tsdb/querier.go`, `tsdb/block.go`, `storage/merge.go`, and `tsdb/db.go`.

**Q1 — what does `querier.Close()` release?**
For an on-disk `Block`, `Block.Index()`/`Block.Chunks()` (`tsdb/block.go:428-441`) don't return the block's real `indexr`/`chunkr` — they return thin wrappers (`blockIndexReader`, `blockChunkReader`) whose `Close()` (`tsdb/block.go:534,565`) does **not** close anything; it only calls `pb.pendingReaders.Done()`, decrementing a `sync.WaitGroup`. The real `index.Close()`/`chunks.Close()` (actual mmap unmap, `tsdb/querier.go:103-115`) only run when the underlying `Block.Close()` runs (`tsdb/block.go:377-386`), which itself blocks on `pendingReaders.Wait()`. So `querier.Close()` in the read path releases **no bytes synchronously** — it only signals "this reader is done" to a refcount that gates a *different*, later close.

**Q2 — does closing early free memory, or is it a hazard?**
`blockChunkQuerier.Select()` (`tsdb/querier.go:174-196`) hands the raw `q.index`/`q.chunks` wrapper values by reference into `NewBlockChunkSeriesSet`, and `StreamChunkedReadResponses` (`storage/remote/codec.go:235-266`) lazily pulls chunk bytes from that same `ChunkReader` on each `iter.Next()` — i.e., strictly *after* `getChunkSeriesSet`'s `defer querier.Close()` has already fired (`storage/remote/read_handler.go:242-266`). Meanwhile, `tsdb/db.go`'s periodic `reloadBlocks`/`deleteBlocks` (`tsdb/db.go:1655-1662`, run roughly every minute per the code comment) closes a `Block` (real mmap unmap) and removes its directory from disk as soon as `pendingReaders` hits zero. Because this diff decrements that refcount immediately after `Select()` returns — before any chunk has been read or written — rather than after streaming completes, it opens a window, for the *entire* streaming duration, during which a concurrent retention/compaction cycle can physically unmap and delete a block whose chunks are still being read by the in-flight lazy iterator. That's a use-after-close race (SIGBUS-on-mmap or corrupted/garbage chunk data streamed to the client), not a memory win.

**Q3 — is there a genuine benefit?**
Yes, but only in the case that doesn't matter for the stated goal: if the client reads promptly, releasing `pendingReaders` right after `Select()` instead of after the full write lets retention/compaction proceed slightly sooner. In the pathological case the PR is meant to fix — a stalled/broken chunked-read client — the window during which the (still in-flight) reader is falsely reported as "done" is now the *entire* stall duration, which is exactly when a scheduled reload/retention pass is most likely to land inside that window. The fix narrows one resource-pinning problem (a querier held open by `defer` for the whole stalled request, previously blocking block deletion) while widening a more severe one (block deletion racing an in-flight read) precisely under the same trigger condition.

Net: the change does address a real pre-existing issue (a stalled chunked-read request previously pinned `pendingReaders` for the whole connection lifetime via the old single `defer querier.Close()` spanning the entire loop/stream), but the chosen mechanism — closing before the lazily-consumed `ChunkSeriesSet` is actually drained — trades that resource-pinning cost for a use-after-close race against block deletion, which is a correctness/safety regression, not a clean performance improvement.

```json
[
  {
    "file": "storage/remote/read_handler.go",
    "line": 247,
    "severity": "Critical",
    "category": "performance",
    "issue": "[PERF_MEMORY] getChunkSeriesSet's defer querier.Close() decrements the block's pendingReaders refcount (tsdb/block.go blockChunkReader/blockIndexReader.Close()) immediately after Select() returns, before StreamChunkedReadResponses has lazily read any chunk data from that same reader. This doesn't free memory synchronously (Close() here is just a refcount decrement, not a real unmap) and it widens the window during which a concurrent reloadBlocks/deleteBlocks cycle (tsdb/db.go, runs ~every minute) can see pendingReaders hit zero, physically close+unmap the block, and delete it from disk while StreamChunkedReadResponses is still iterating chunks read from it. The window is now the full stream duration instead of zero, and is largest exactly during the slow/stalled-client scenario this PR targets.",
    "fix": "Keep the querier open for the lifetime of the returned ChunkSeriesSet: close it only after StreamChunkedReadResponses has fully consumed the set (e.g. return querier and close it in the same defer scope that wraps both Select and the streaming call), rather than closing as soon as Select() returns. If the goal is bounding how long a stalled client can pin retention/compaction, bound the write itself (context/write-deadline on the stream) instead of severing the querier from the in-flight lazy read.",
    "confidence": 100,
    "pre_existing": false
  }
]
```

## Considered But Not Flagged

- Per-query allocation cost of the closure wrapping in `getChunkSeriesSet` / `remoteReadSamples` (extra function literal per query iteration) — bounded by `len(req.Queries)`, not a scale concern.
- `sortedExternalLabels` construction on every request (`ServeHTTP`) — bounded by number of configured external labels, not per-row/per-series; cold relative to series volume.
- `mergeGenericQuerier.Close()` in `storage/merge.go` closing all constituent block queriers as a batch — same premature-release mechanism as the primary finding but not a separate multiplication; folded into the one finding above rather than double-counted.
- Head-block (`headChunkReader`) early close via `isoState.Close()` — plausible analogous risk with WAL/mmap chunk truncation, but the isolation-state interaction wasn't traced far enough in this pass to state a concrete multiplication; anchor would land at 50, so suppressed per the reporting bar. Flagging for awareness only, not as a finding.

### Probe Requests
None — all analysis was read-only (`Read`/`grep`) against the working tree; no commands were run that would modify tracked files.

Files consulted (absolute paths):
- `/home/decaf/code/decaf-claude/competition/benchmark/repos/7/storage/remote/read_handler.go`
- `/home/decaf/code/decaf-claude/competition/benchmark/repos/7/storage/remote/codec.go`
- `/home/decaf/code/decaf-claude/competition/benchmark/repos/7/storage/merge.go`
- `/home/decaf/code/decaf-claude/competition/benchmark/repos/7/tsdb/querier.go`
- `/home/decaf/code/decaf-claude/competition/benchmark/repos/7/tsdb/block.go`
- `/home/decaf/code/decaf-claude/competition/benchmark/repos/7/tsdb/db.go`
- `/home/decaf/code/decaf-claude/competition/benchmark/repos/7/tsdb/chunks/chunks.go`
- `/home/decaf/code/decaf-claude/competition/benchmark/repos/7/tsdb/index/index.go`
- `/home/decaf/code/decaf-claude/competition/benchmark/repos/7/tsdb/head_read.go`
