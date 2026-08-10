# subagent agent-aed818a68e4947078

Depth: deep — high-risk domain (memory-safety / use-after-close on memory-mapped TSDB chunk + index readers); traced the full lifetime-coupling chain across `read_handler.go` → `codec.go` → merge layer → tsdb block/head chunk readers; multiple passes; cascade + composition construction.

I have everything I need. The invariant is documented in the code itself.

## Verdict

The refactor breaks a lifetime-coupling invariant that TSDB relies on and that two existing tests explicitly encode. `getChunkSeriesSet` closes the chunk querier when it *returns*, but `StreamChunkedReadResponses` consumes the returned `ChunkSeriesSet` **lazily** afterward — and in the common path that set is backed by memory-mapped block/head segments whose lifetime is guarded by exactly the querier that was just closed.

Ground-truth confirmed by reading the code:

- `Reader.ChunkOrIterable` (`tsdb/chunks/chunks.go:700-703`): `chkData := sgmBytes.Range(...)` — the chunk's bytes are a slice **into the mmapped segment**, not a copy.
- `compactChunkIterator.Next` (`storage/merge.go:770-771`): with no time-overlap (single block / non-overlapping blocks — the overwhelmingly common case) it returns the **original mmap-backed chunk** with no re-encode/copy. So the returned set is lazy and not self-contained (settles both horns of the lazy-vs-eager hypothesis: it is lazy, hence close-before-consume is unsafe).
- `blockChunkReader.Close` (`tsdb/block.go:567-570`) only does `pendingReaders.Done()`. The munmap happens later in `Block.Close` (`tsdb/block.go:378-389`) which does `pendingReaders.Wait()`.
- `deleteBlocks` (`tsdb/db.go:1656-1665`) documents it verbatim: block deletion "needs to be closed first as it might need to wait for pending readers to complete." So an open querier is the *only* thing blocking compaction/retention from munmapping the segment.
- The head path (`tsdb/head_read.go:318-390`): `headChunkReader.Close` releases `isoState`; mmapped head chunks are returned as `safeHeadChunk` wrapping mmapped bytes **without a copy** (only the open head chunk is copied).
- Smoking gun — two tests encode the invariant: `TestChunkQuerier_ShouldNotPanicIfHeadChunkIsTruncatedWhileReadingQueriedChunks` (`tsdb/db_test.go:3555`, "make sure it's closed only once the test is over", reads `chunk.Bytes()` at 3604 after truncation + GC stress) and `TestQuerierShouldNotFailIfOOOCompactionOccursAfterRetrievingQuerier` (`:3660`, "If it does not wait for querierCreatedBeforeCompaction to be closed, then the query will return incorrect results or fail").

Error-ordering hypothesis (3): the early `chunks.Err()` at `read_handler.go:206` is benign-but-weakened — real per-chunk read errors still surface via `ss.Err()`/`iter.Err()` inside `StreamChunkedReadResponses`. Not a separate failure. Concurrency hypothesis (4) collapses into the compaction/truncation race below (the querier is pull-based; no background goroutine feeds the set).

```json
[
  {
    "file": "storage/remote/read_handler.go",
    "line": 247,
    "severity": "Critical",
    "category": "resource-management",
    "issue": "[ADV_COMPOSITION] getChunkSeriesSet's defer querier.Close() fires on return (pendingReaders.Done) → StreamChunkedReadResponses then lazily reads mmap-backed index/chunk bytes → concurrent compaction/retention calls Block.Close (pendingReaders.Wait returns immediately) and munmaps the segment → next ss.Next()/chk.Chunk.Bytes() reads unmapped memory → segfault (process crash) or corrupted response bytes streamed to client.",
    "fix": "Keep the chunk querier open for the entire consumption of the ChunkSeriesSet. Do not close it inside getChunkSeriesSet; instead run StreamChunkedReadResponses before the querier is closed (e.g. pass the stream into the helper, or return querier alongside the set and defer Close in remoteReadStreamedXORChunks after streaming completes — restoring the pre-PR ordering). If early release is truly required, materialize a self-contained copy of every chunk's Bytes() before Close (which negates the memory benefit).",
    "confidence": 75,
    "pre_existing": false
  },
  {
    "file": "storage/remote/read_handler.go",
    "line": 265,
    "severity": "Critical",
    "category": "resource-management",
    "issue": "[ADV_CASCADE] Head-path variant: closing the querier releases headChunkReader.isoState → head compaction/truncation (Head.truncateMemory / chunkDiskMapper truncation, as exercised by the skipped TestChunkQuerier_ShouldNotPanicIfHeadChunkIsTruncatedWhileReadingQueriedChunks) is no longer held off → mmapped head chunks (returned as safeHeadChunk without copy) are munmapped while StreamChunkedReadResponses still reads chk.Chunk.Bytes() → panic/segfault or corrupt bytes. Query range spanning the head over a slow client widens the window.",
    "fix": "Same fix as the block-path finding — the querier (and its isolation state) must outlive consumption of the returned ChunkSeriesSet. One structural change (stream while the querier is still open) covers both the pendingReaders and isoState protections.",
    "confidence": 50,
    "pre_existing": false
  }
]
```

### Probe Requests

- **Probe (handler-level race):** New test in `storage/remote/read_handler_test.go`. Build a `tsdb.DB` with one persistent block over the query range, register it behind the `readHandler`, issue a `STREAMED_XOR_CHUNKS` remote-read whose `ResponseWriter`/`Flusher` blocks between frames (simulating a slow client). While the handler is streaming, trigger block deletion by calling `db.reloadBlocks()` after making the block deletable (or `db.Compact` + reload). Expected: with the PR (`getChunkSeriesSet` closes early) → segfault or CRC/decoding corruption of streamed chunks; with the querier kept open until streaming finishes → clean stream. Production line under test: `storage/remote/read_handler.go:247` (the `defer querier.Close()`).
- **Probe (unit, tighter):** Call `h.getChunkSeriesSet(...)` to obtain the `ChunkSeriesSet` (querier already closed by the helper), then force the source block's `Block.Close()` (retention/compaction path), then iterate the set reading `iter.At().Chunk.Bytes()`. Expected: read of unmapped memory (crash under the same GC-stress technique used at `tsdb/db_test.go:3586-3606`). Contrast with the current inline pattern where Close is deferred to after consumption.
- **Probe (existing test, re-point):** Adapt the deliberately-skipped `TestChunkQuerier_ShouldNotPanicIfHeadChunkIsTruncatedWhileReadingQueriedChunks` (`tsdb/db_test.go:3487`) to close the querier *before* the `chunk.Bytes()` loop — this reproduces the head-path finding; today it keeps the querier open specifically to avoid the crash.

## Considered But Not Flagged

- **Error-ordering weakening (hypothesis 3):** `chunks.Err()` at `read_handler.go:206` runs before lazy iteration, so it only catches `Select`-time setup errors (e.g. `PostingsForMatchers`, `ChunkQuerier` failure via `ErrChunkSeriesSet`). Fell apart as an independent bug: real iteration errors still surface through `ss.Err()`/`iter.Err()` returned by `StreamChunkedReadResponses` (`codec.go:292-296`). Redundant, not incorrect.
- **Eager-materialization horn (hypothesis 2):** Investigated whether `Select(sortSeries=true)` copies chunk bytes so the set is self-contained. Fell apart: `compactChunkIterator` copies/re-encodes only on time-overlap (`merge.go:775`); the no-overlap path returns mmap-backed originals, and head open-chunk copy (`head_read.go:371-382`) does not cover mmapped head chunks or persistent blocks. So the set is not self-contained — which is why the use-after-close is real rather than a non-issue.
- **Concurrency/goroutine race (hypothesis 4):** No background goroutine feeds the pull-based merge series set, so "closing while goroutines feed it" has no concrete instance; the only concurrency is with compaction/truncation, already captured in the two primary findings.
