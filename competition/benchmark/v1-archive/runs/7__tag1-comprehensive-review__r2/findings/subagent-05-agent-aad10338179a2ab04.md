# subagent agent-aad10338179a2ab04

## Files reviewed

- `/home/decaf/code/decaf-claude/competition/benchmark/repos/7/storage/remote/read_handler.go` (the diff under review: `remoteReadStreamedXORChunks` + new `getChunkSeriesSet` helper)
- `/home/decaf/code/decaf-claude/competition/benchmark/repos/7/storage/remote/codec.go` (`StreamChunkedReadResponses`)
- `/home/decaf/code/decaf-claude/competition/benchmark/repos/7/storage/fanout.go`, `storage/merge.go`, `storage/interface.go` (`ErrChunkSeriesSet`)
- `/home/decaf/code/decaf-claude/competition/benchmark/repos/7/tsdb/querier.go` (`blockChunkQuerier`, `blockBaseQuerier`, `blockChunkSeriesSet`, `chunkSeriesEntry`, `populateWithDelChunkSeriesIterator`)
- `/home/decaf/code/decaf-claude/competition/benchmark/repos/7/tsdb/chunks/chunks.go` (`Reader.Close`, `Reader.ChunkOrIterable`)
- `/home/decaf/code/decaf-claude/competition/benchmark/repos/7/tsdb/fileutil/mmap.go` (`MmapFile.Close` → `munmap`)

## Critical (90-100)

**Use-after-close on the chunk querier's underlying mmap'd chunk reader — data corruption / crash risk.**
Confidence: 97
File: `storage/remote/read_handler.go:205-208, 242-266`

`getChunkSeriesSet` (lines 242-266) creates the `ChunkQuerier`, defers `querier.Close()`, calls `querier.Select(...)`, and returns the resulting `storage.ChunkSeriesSet` — all before the defer fires. The defer runs when `getChunkSeriesSet` itself returns (Go defer semantics: at *function* return, not at "last use" of the resource), so the querier is already closed by the time the caller (`remoteReadStreamedXORChunks`, line 205) receives `chunks`.

That `ChunkSeriesSet`, however, is lazily evaluated — chunk bytes are not read until `StreamChunkedReadResponses` (`storage/remote/codec.go:229-296`) calls `ss.Next()`/`series.Iterator()`/`iter.At()`, which happens entirely *after* `getChunkSeriesSet` has returned. I traced the concrete implementation used by a normal (single local TSDB, no secondaries) Prometheus:

- `fanout.ChunkQuerier` → `db.ChunkQuerier` → (for the common single-querier case) `mergeGenericQuerier.Select` returns `q.queriers[0].Select(...)` directly (`storage/merge.go:105-107`), i.e. the raw, unwrapped per-block lazy series set — no buffering.
- `blockChunkQuerier.Select` (`tsdb/querier.go:174-196`) returns `NewBlockChunkSeriesSet(...)`, a `blockChunkSeriesSet` that stores a reference to `q.chunks` (the `ChunkReader`) and only builds postings — no chunk bytes are read yet.
- `blockChunkSeriesSet.At()` (`tsdb/querier.go:1173-1180`) returns a `chunkSeriesEntry{chunks: b.chunks, ...}`; its `Iterator()` (`tsdb/querier.go:773-780`) creates a `populateWithDelChunkSeriesIterator` that reads chunk data from that same `ChunkReader` on each `Next()` call — i.e., during `StreamChunkedReadResponses`'s loop, not during `Select()`.
- `blockBaseQuerier.Close()` (`tsdb/querier.go:103-115`) closes `q.chunks` — the `ChunkReader`.
- The on-disk `ChunkReader` is `tsdb/chunks.Reader`, whose `Close()` (`tsdb/chunks/chunks.go:656-658`) calls `tsdb_errors.CloseAll(s.cs)` on the `*fileutil.MmapFile`s backing `s.bs`.
- `MmapFile.Close()` (`tsdb/fileutil/mmap.go:56-58`) calls `munmap`, unmapping the memory that `ChunkOrIterable` (`tsdb/chunks/chunks.go:666+`) later dereferences via `s.bs[sgmIndex].Range(...)`.

So for the normal, most common configuration, `StreamChunkedReadResponses` ends up calling `chk.Chunk.Bytes()` against memory that was `munmap`'d before iteration even started. This is not merely "stale/wrong data" — reading an unmapped memory-mapped region is undefined behavior at the OS level and commonly manifests as a `SIGSEGV`/`SIGBUS` that crashes the whole process (not a recoverable Go panic), or silently returns garbage bytes if the page happens to be reused. This directly contradicts the PR's stated goal (avoid instability from broken chunked reads) — it trades a slow-consumer resource-accumulation concern for a memory-safety bug that can crash the server or corrupt every chunked-read response for the remainder of the request.

Fix: keep the querier open for the lifetime of the consumption, e.g. return the querier (or a wrapper `io.Closer`) alongside the `ChunkSeriesSet` and close it only after `StreamChunkedReadResponses` returns — restoring the original defer-after-full-consumption pattern, or have `getChunkSeriesSet` return `(storage.ChunkSeriesSet, io.Closer, error)` and `defer closer.Close()` in the caller after streaming completes.

## Notes (not separately-scored findings)

- On error-handling equivalence: the querier-creation-error path is preserved correctly — `h.queryable.ChunkQuerier` failing now surfaces via `storage.ErrChunkSeriesSet(err)` and is caught by the immediate `chunks.Err()` check (line 206), matching the old early-return behavior. This part of the refactor is fine in isolation; the bug is specifically the premature `Close()`, not the error plumbing.
- On the PR's stated motivation ("avoid OOMs… by closing the queriers earlier"): checking the pre-PR code (commit `53091126c2^`), the `defer querier.Close()` was already scoped inside the per-query `func() error { ... }()` IIFE, so it already ran at the end of each query's iteration — right after that query's `StreamChunkedReadResponses` call completed — not accumulated across the whole request. The refactor doesn't change *when* Close was intended to run relative to full consumption; it just breaks that invariant by moving the call+defer into a helper that returns before consumption happens. This is context, not an independently-scored finding.

No other high-confidence issues found in this diff.
