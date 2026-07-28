# subagent agent-a3b4f33133cb849c6

## Go Idiom Review — storage/remote/read_handler.go (PR #13777)

I traced the concrete querier type behind `SampleAndChunkQueryable` in production (`web/api/v1/api.go:277` → `tsdb.DB.ChunkQuerier` → `tsdb/db.go:2066` → `storage.NewMergeChunkQuerier`) and verified this is a genuine, verifiable memory-safety/race regression, not just a style nit.

### Verified chain of evidence

- `getChunkSeriesSet` (`storage/remote/read_handler.go:242-265`) defers `querier.Close()` at line 247-251 and **returns** `querier.Select(...)` at line 265 — the classic "close before the returned value is drained" shape.
- The caller (`storage/remote/read_handler.go:205-218`) only calls `chunks.Err()` (line 206, a cheap synchronous check) before handing `chunks` to `StreamChunkedReadResponses`, which does the real work at `storage/remote/codec.go:235` (`for ss.Next() { ... iter.At() ... chk.Chunk.Bytes() ... }`) — entirely **after** the helper returned and its `defer` already ran.
- `storage.ChunkSeriesSet` (`storage/interface.go:436-444`) has no `Close()` of its own — `querier.Close()` is the only cleanup hook, and it has already fired.
- For on-disk blocks: `tsdb/querier.go:195` returns a `blockChunkSeriesSet` holding the *same* `ChunkReader`/`IndexReader` the querier wraps. `tsdb/block.go:536-539, 557-560, 567-570` show `blockIndexReader.Close()`/`blockChunkReader.Close()` merely call `pb.pendingReaders.Done()` — they don't unmap anything themselves. But `tsdb/block.go:377-390` shows `Block.Close()` (invoked by compaction/retention) does `pb.pendingReaders.Wait()` then `pb.chunkr.Close()`/`pb.indexr.Close()`, which (`tsdb/chunks/chunks.go:656-658` → `tsdb/fileutil/mmap.go:56-58`) actually `munmap`s the segment files. Calling `querier.Close()` immediately after `Select()` (instead of after the stream drains) decrements `pendingReaders` far too early, defeating the exact mechanism `pendingReaders` exists to provide. If a background compaction/retention cycle closes that same block while the streaming goroutine is still calling `ChunkOrIterable`/`Range` on its mmap'd bytes (`tsdb/chunks/chunks.go:666-684`), that is a read of unmapped memory — undefined behavior, typically a fatal SIGSEGV that Go cannot recover from (crashes the whole process, not just the request).
- For Head-backed queries: `tsdb/head_read.go:318-323` shows `headChunkReader.Close()` calls `isoState.Close()`, and `tsdb/isolation.go:36-41` unlinks this read from the active-reads doubly-linked list used to compute the low watermark for head GC/truncation. Doing this before iteration (`tsdb/head_read.go:669-725`, which uses `isoState` to decide sample visibility) has finished lets concurrent head truncation advance past this "already closed" read while it's still consuming head data — breaking the snapshot-isolation guarantee the mechanism exists to provide.
- Confirmed via `mergeGenericQuerier.Close()` (`storage/merge.go:255-263`) that `querier.Close()` fans out to every sub-querier (all blocks + head) touched by the query, so this applies broadly, not just to a single block.
- The existing tests (`storage/remote/read_handler_test.go`) use `promql.LoadedStorage`, a single-goroutine in-memory `tsdb.DB` with no concurrent compaction — so the race window is real but structurally unreachable by the current test suite, consistent with the stated "targeted tests PASS" gate.

This is a straightforward "return a resource-backed value after already deferring the resource's cleanup" mistake (same family as returning `sql.Rows` after `defer db.Close()`), except the resource here is an mmap, so the failure mode is memory corruption/crash, not just stale data.

```json
[
  {
    "file": "storage/remote/read_handler.go",
    "line": 247,
    "severity": "Critical",
    "category": "resource-management",
    "issue": "[GO_DEFER] getChunkSeriesSet defers querier.Close() and then returns querier.Select(...) (line 265) — a lazily-iterated storage.ChunkSeriesSet whose Next()/At()/Iterator() (drained later in codec.go:235 by the caller) reads through the very ChunkReader/IndexReader the querier owns. For on-disk blocks this closes each sub-reader wrapper (tsdb/block.go blockChunkReader/blockIndexReader.Close -> pb.pendingReaders.Done()) before the stream has consumed the data, prematurely releasing the refcount that Block.Close() (used by compaction/retention) waits on before munmap'ing the block's chunk/index files (tsdb/chunks/chunks.go Reader.Close -> fileutil.MmapFile.Close -> munmap).",
    "fix": "Do not defer querier.Close() before returning a value that is iterated by the caller. Keep the defer in remoteReadStreamedXORChunks wrapped around the full StreamChunkedReadResponses call (as before this refactor) — extract only the Select()/hints construction into the helper, or have the helper return the querier alongside the ChunkSeriesSet so the caller closes it after the stream is fully drained.",
    "confidence": 75,
    "pre_existing": false
  },
  {
    "file": "storage/remote/read_handler.go",
    "line": 265,
    "severity": "Critical",
    "category": "resource-management",
    "issue": "[GO_MEMORY_MODEL] Concrete failure: a background compaction/retention cycle can call tsdb/block.go Block.Close() (pendingReaders.Wait() then chunkr.Close()/indexr.Close(), munmapping segment files) for a block this query is reading, as soon as this query's now-premature Close() lets the WaitGroup reach zero — while StreamChunkedReadResponses is still mid-iteration calling ChunkOrIterable/sgmBytes.Range on that same mmap'd memory (tsdb/chunks/chunks.go:666-684).",
    "failure_scenario": "Remote-read client requests a large/slow chunked stream spanning a persisted block; concurrently, the normal compaction/retention loop decides to compact or delete that exact block. Because getChunkSeriesSet's querier.Close() already decremented pendingReaders right after Select() (well before the stream finished), Block.Close() proceeds and munmaps the chunk/index segment files while the streaming goroutine is still reading from them, producing a read of unmapped memory (undefined behavior / likely SIGSEGV, taking down the whole Prometheus process, not just the one request).",
    "fix": "Same as above — keep the querier open (and its Close deferred) until iteration of the returned ChunkSeriesSet is fully complete.",
    "confidence": 75,
    "pre_existing": false
  },
  {
    "file": "storage/remote/read_handler.go",
    "line": 247,
    "severity": "High",
    "category": "resource-management",
    "issue": "[GO_MEMORY_MODEL] For Head-backed (recent) data, querier.Close() forwards to headChunkReader.Close() -> isoState.Close() (tsdb/head_read.go:318-323, tsdb/isolation.go:36-41), which unlinks this read from the isolation low-watermark list immediately after Select(), not after iteration finishes. This breaks the snapshot-isolation contract the mechanism exists to enforce: concurrent head truncation/GC can now advance past this 'already closed' read while chunk iteration (tsdb/head_read.go's use of isoState in memSeries.iterator) is still in progress.",
    "failure_scenario": "A chunked remote-read query touching the Head overlaps with a concurrent head truncation (WAL/series GC cycle, which runs periodically in production). Because isolation tracking for this read was released early, truncation may reclaim/garbage-collect series or chunk slots the still-draining iterator is about to visit, yielding inconsistent (non-snapshot) results or a mid-stream error surfaced through StreamChunkedReadResponses, silently corrupting the semantics of what should be a point-in-time consistent read.",
    "fix": "Same root fix as the block case: don't release isolation state (via querier.Close()) until the returned ChunkSeriesSet has been fully iterated by the caller.",
    "confidence": 75,
    "pre_existing": false
  }
]
```

### Probe Requests

- Add a test in `storage/remote/read_handler_test.go` that: (1) builds a `tsdb.DB` with a persisted (non-Head) block via `db.Compact()`, (2) starts a chunked remote-read request against that block, (3) between `getChunkSeriesSet` returning and the stream finishing, calls `block.Close()` (or triggers compaction removing that block) from another goroutine. Expected today: a race detector failure or crash (`go test -race`) once the reader's `pendingReaders` count reaches zero early and the second `Close()` proceeds to munmap while the stream is still reading — this would concretely demonstrate the hazard without needing real production compaction timing.

### Considered But Not Flagged

- **`chunks.Err()` check at `storage/remote/read_handler.go:206`**: only validates the synchronous construction error (e.g., bad `PostingsForMatchers`); it doesn't mask iteration-time errors, which still propagate through `StreamChunkedReadResponses`'s returned `err`/`ws`. Not a bug in isolation, though its errors could now be confusing "closed reader" symptoms as a side effect of the findings above — not a separate independently-actionable item.
- **`ctx` not rechecked during iteration** (`ss.Next()` loop in `codec.go` doesn't poll `ctx.Done()`): true, but this is pre-existing behavior identical before and after this PR (the querier's `Select(ctx, ...)` was always only used for postings construction, never for iteration cancellation) — not introduced by this diff.
- **`storage.ErrChunkSeriesSet(err)` return on `ChunkQuerier` failure** (`read_handler.go:245`): a concrete non-nil `ChunkSeriesSet` wrapping a concrete non-nil error — not a typed-nil interface trap.
- **Deferred `Close()` error handling**: the error from `querier.Close()` is checked and logged (`level.Warn`) in both the old and new code — no silently dropped error here.
- **Test suite passing despite the bug**: `read_handler_test.go` uses `promql.LoadedStorage`, a single-threaded in-memory DB with no concurrent compaction/truncation, so the race window this review identifies is structurally unreachable by the current tests — consistent with, not contradicting, the pre-flight gate results.
