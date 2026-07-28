# subagent agent-aeb5ce3e87f4785a7

## Verdict: Confirmed use-after-close bug

Closing the chunk querier before the caller iterates the returned `ChunkSeriesSet` is **not safe** — it is a genuine, severe regression. `storage.ChunkQuerier.Select()` for the on-disk TSDB path returns a **lazily-evaluated** series set; the actual chunk bytes are read from the querier's (mmap'd) chunk-file readers only when the caller later calls `Next()`/`At()`/`Iterator().Next()` — which now happens *after* the querier (and its underlying mmap'd files) have already been closed.

### Where it manifests

`storage/remote/read_handler.go`:
- **Line 205**: `chunks := h.getChunkSeriesSet(ctx, query, filteredMatchers)` — by the time this call returns, the querier is already closed (see below).
- **Lines 210–218**: `StreamChunkedReadResponses(..., chunks, ...)` — this is where the caller actually iterates `chunks` and triggers chunk-byte reads, i.e., a use-after-close.
- **Lines 242–266** (`getChunkSeriesSet`): lines 247–251 `defer func(){ querier.Close() }()` fires as soon as this helper returns (right after line 265 `return querier.Select(...)`) — not when the caller finishes consuming the `ChunkSeriesSet` it returned. That's the root cause: the `defer`'s scope was moved to a function whose lifetime no longer matches the object's actual usage lifetime. This is exactly the bug the old code avoided by keeping `defer querier.Close()` in the caller's scope, spanning the whole `Select()` + streaming-iteration lifetime.

### Evidence chain (why `Select()` is lazy and closing breaks it)

- `tsdb/querier.go:174-193` `blockChunkQuerier.Select` — only resolves postings (`PostingsForMatchers`) and returns `NewBlockChunkSeriesSet(...)`; it does **not** read chunk byte data at Select-time.
- `tsdb/querier.go:1158-1176` `NewBlockChunkSeriesSet` / `blockChunkSeriesSet.At()` — `At()` returns a `chunkSeriesEntry` that just holds a reference to the block's `ChunkReader` (`b.chunks`), not decoded data.
- `tsdb/querier.go:767-780` `chunkSeriesEntry.Iterator()` — builds a `populateWithDelChunkSeriesIterator` that also just holds the `ChunkReader` reference.
- `tsdb/querier.go:697-724` `populateWithDelGenericSeriesIterator.next()` — line 721 calls `p.cr.ChunkOrIterable(p.currMeta)`, i.e. the chunk bytes are fetched **lazily, during iteration** (inside `StreamChunkedReadResponses`'s loop).
- `tsdb/chunks/chunks.go` `Reader.ChunkOrIterable` reads directly from `s.bs` (`[]ByteSlice`), which for persisted blocks are `realByteSlice` wrapping bytes from `fileutil.OpenMmapFile(...)`.
- `tsdb/querier.go:103-113` `blockBaseQuerier.Close()` closes `q.index`, `q.chunks` → `Reader.Close()` → `tsdb_errors.CloseAll(s.cs)`, which unmaps the mmap'd chunk segment files backing `s.bs`.
- `storage/merge.go:255` `mergeGenericQuerier.Close()` — `DB.ChunkQuerier(...)` returns a merged querier across all blocks (+ head); closing it closes every underlying block's `ChunkReader`/mmap in one shot.
- `storage/remote/codec.go:221-266` `StreamChunkedReadResponses` — the `for ss.Next()` / `iter.Next()` / `iter.At()` loop is where the chunk-byte reads actually happen — and this runs in the caller, after `getChunkSeriesSet` has already returned and closed everything.

`chunks.Err()` (new line 206) doesn't mask this: `blockBaseSeriesSet.Err()` (`tsdb/querier.go:639`) just returns the postings error, it does not force any chunk read.

### Impact

For any streamed chunked remote-read query touching persisted (on-disk, mmap'd) blocks — i.e., essentially any query that isn't restricted purely to the most recent in-memory head data — `StreamChunkedReadResponses` will read chunk bytes from already-unmapped memory. In Go this is undefined behavior and typically triggers a fatal, unrecoverable segfault of the whole Prometheus process (not a catchable error), or in a less bad case returns corrupted chunk data to the remote-read client. This is on a very common, externally-triggerable code path (any client issuing a streamed remote-read request), making it a high-severity regression.

No other significant new bugs were found in this diff — the rest of the extraction (matcher/hints handling, error wrapping, logging) is behavior-preserving.
