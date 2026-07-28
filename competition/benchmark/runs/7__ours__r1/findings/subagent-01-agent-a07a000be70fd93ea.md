# subagent agent-a07a000be70fd93ea

## Code Review Report

**Scope**: `storage/remote/read_handler.go` (PR prometheus/prometheus #13777, merged, reviewed retrospectively)
**Project documentation**: No repo-level CLAUDE.md found in this checkout; only CONTRIBUTING.md, which contains no checkable coding-convention rules. Skipping convention checks.

### Findings

```json
[
  {
    "file": "storage/remote/read_handler.go",
    "line": 247,
    "severity": "Critical",
    "category": "resource-management",
    "issue": "[BUG_CONCURRENCY] getChunkSeriesSet() closes the ChunkQuerier (via defer) before its returned lazy storage.ChunkSeriesSet is ever iterated by the caller, racing with concurrent block compaction/retention and head truncation.",
    "fix": "Keep the querier open for the full duration of the streamed iteration: return the querier alongside the ChunkSeriesSet from getChunkSeriesSet (or a wrapper/closure), and defer querier.Close() in remoteReadStreamedXORChunks only after StreamChunkedReadResponses finishes consuming it — i.e. restore the Close() span used by the pre-diff code and by the sibling remoteReadSamples path, while keeping the new extracted-function structure and the early chunks.Err() check.",
    "confidence": 100,
    "pre_existing": false
  }
]
```

**Evidence chain** (fully traced through source, not run):

1. `getChunkSeriesSet` (`storage/remote/read_handler.go:242-266`) calls `querier.Select(...)` and then, via the `defer` set up at lines 247-251, closes the querier immediately as the function returns — *before* `remoteReadStreamedXORChunks` ever iterates the returned `ChunkSeriesSet` (that happens later, inside `StreamChunkedReadResponses`, `storage/remote/codec.go:235-266`, via `ss.Next()` / `series.Iterator(iter)` / `iter.Next()`).
2. `h.queryable.ChunkQuerier` typically resolves through `storage.fanout.ChunkQuerier` (`storage/fanout.go:99-115`) → `storage.NewMergeChunkQuerier` over `tsdb.DB.ChunkQuerier` (`tsdb/db.go:2066-2073`), itself another `NewMergeChunkQuerier` over per-block `blockChunkQuerier`s and the head. `mergeGenericQuerier.Close()` (`storage/merge.go:255-263`) closes every constituent querier **synchronously**, the moment it's called.
3. For a persisted block, `blockBaseQuerier.Close()` (`tsdb/querier.go:103-115`) calls `q.chunks.Close()` → `blockChunkReader.Close()` (`tsdb/block.go:567-570`), which does **not** unmap the block's chunk file — it only calls `pb.pendingReaders.Done()`. `Block.Close()` (`tsdb/block.go:377-390`, invoked by compaction/retention) blocks on `pendingReaders.Wait()` before it actually closes the mmap'd `chunks.Reader` (`tsdb/chunks/chunks.go:656-658`).
4. Chunk bytes are read lazily: `blockChunkSeriesSet.At()` → `chunkSeriesEntry.Iterator()` → `populateWithDelGenericSeriesIterator.next()` → `p.cr.ChunkOrIterable(...)` (`tsdb/querier.go:697-748, 1173-1180`) is what actually touches the (already `Done()`-signalled) chunk reader — and this only happens when `StreamChunkedReadResponses` iterates, well after `getChunkSeriesSet` returned.
5. So the new code tells the block "this reader is finished" before the real reads happen. If a compaction/retention cycle completes `Block.Close()` in that now-unprotected window, the handler's next chunk read touches unmapped memory → crash or corrupted data.
6. The identical pattern exists for the head: `headChunkReader.Close()` (`tsdb/head_read.go:318-323`) calls `isoState.Close()` (`tsdb/isolation.go:36-41`), unlinking the isolation state that protects in-use head chunks from GC/truncation — again unlinked before the `safeHeadChunk` (`tsdb/head_read.go:385-390`) it guards is actually iterated.
7. This exact hazard is independently documented in this same repository: `tsdb/db_test.go:3487`, `TestChunkQuerier_ShouldNotPanicIfHeadChunkIsTruncatedWhileReadingQueriedChunks`, whose setup comment explicitly says to "make sure it's closed only once the test is over" before calling `db.Compact()` mid-test — precisely to keep the reader registered while chunk memory is still being read. (The test itself is currently `t.Skip`'d for an unrelated CI-crash investigation, but its design corroborates the hazard rather than undermining it.)
8. The sibling `remoteReadSamples` path (`storage/remote/read_handler.go:117-187`) does not have this problem — it still keeps `querier.Close()` deferred around the whole `Select()` + `ToQueryResult()` call, matching the shape `remoteReadStreamedXORChunks` had before this diff.

On the stated OOM-reduction goal: for the local-TSDB-backed path, `Close()` is mostly bookkeeping (decrementing a `sync.WaitGroup`, unlinking a list node) rather than an actual memory release, so the diff mainly shortens how long the read-registration is held — which is exactly what creates the race above. The genuinely safe part of this change is the early `chunks.Err()` check for `ChunkQuerier()`-construction failures (error type is preserved correctly via `storage.ErrChunkSeriesSet`, verified at `storage/interface.go:392-404`); that part is fine and worth keeping.

## Considered But Not Flagged

- **`chunks.Err()` called immediately after `Select()`, before any `Next()`** (`storage/remote/read_handler.go:206`): for block/head-backed series sets this only catches errors already known at `Select()`-construction time (e.g. bad matchers via `PostingsForMatchers` failure, or `ChunkQuerier()` creation failure wrapped via `storage.ErrChunkSeriesSet`). Errors that only manifest during iteration still surface later through the normal `StreamChunkedReadResponses` return path, same as before this diff. Not a defect — just a partial early-exit optimization. (confidence 25, not reported)
- **Error type/behavior preservation through `storage.ErrChunkSeriesSet`**: verified `errChunkSeriesSet.Err()` returns the original, unwrapped error, so the caller's `errors.As(err, &httpErr)` handling is unaffected by the refactor. No issue.
- **Double-close / defer-in-loop concerns**: `getChunkSeriesSet`'s defer fires exactly once per call (once per query in `req.Queries`), matching the original per-query querier lifecycle. No leak or double-close.

## Probe Requests

None — no existing test in `storage/remote/read_test.go` exercises `remoteReadStreamedXORChunks`'s querier-close timing, so there's nothing in-repo to nominate for execution; reproducing the race would require a new test that streams a chunked read while concurrently forcing a `db.Compact()`/head-truncation, which is new-test-authoring rather than a probe to run against existing code. The finding above is instead grounded entirely in static tracing through the storage/tsdb layers listed.
