# subagent agent-aaa76ea62de2da982

I have everything needed. The investigation is conclusive: the change introduces a use-after-close (segfault) bug, and this exact commit was reverted upstream for precisely this reason.

---

### Strengths

- The refactor itself is clean and idiomatic Go. Extracting the querier setup into `getChunkSeriesSet` (`storage/remote/read_handler.go:242-266`) de-duplicates the hints-construction block and reads well.
- Error propagation was converted correctly to the storage idiom: a failed `ChunkQuerier(...)` is now surfaced as `storage.ErrChunkSeriesSet(err)` (line 245) and re-checked via `chunks.Err()` at the call site (line 206). Functionally this preserves the original "return the error → HTTP 500/typed error" behavior.
- The `level.Warn` logging on close-error is preserved verbatim (lines 247-251), and the `sortSeries=true` argument and the "series must be sorted" comment are carried over faithfully.
- The stated motivation — bounding memory when clients send broken/abandoned chunked read requests — is a real and reasonable problem to target.

### Issues

#### Critical (Must Fix)

**Use-after-close of memory-mapped block chunks → segfault** — `storage/remote/read_handler.go:242-266` (the `defer querier.Close()` at 247-251 combined with returning the lazy `querier.Select(...)` at 265).

- **What's wrong:** `getChunkSeriesSet` closes the `ChunkQuerier` via `defer` and *then* returns the `storage.ChunkSeriesSet` produced by `querier.Select(...)`. That `ChunkSeriesSet` is **lazy** — it does no chunk I/O at construction. The actual chunk reads happen later, in `StreamChunkedReadResponses` (`storage/remote/codec.go:235-261`), when `ss.Next()` / `iter.Next()` drive `populateWithDelChunkSeriesIterator.Next()` → `populateWithDelGenericSeriesIterator.next()` → `p.cr.ChunkOrIterable(...)` (`tsdb/querier.go:721`). By that point the querier — and thus the block's `ChunkReader` — is already closed.
- **Why it's a crash, not just a leak:** For persistent blocks, `Reader.ChunkOrIterable` (`tsdb/chunks/chunks.go:666-703`) returns a chunk that **references the mmap'd segment bytes without copying** — `s.pool.Get(enc, chkData)` sets `c.b.stream = chkData`, where `chkData` is a slice into `sgmBytes` (the mmap). `blockBaseQuerier.Close()` (`tsdb/querier.go:103-115`) calls `q.chunks.Close()` → `Reader.Close()` → `CloseAll(s.cs)` (`tsdb/chunks/chunks.go:656-658`), which unmaps those segments. Reading `chk.Chunk.Bytes()` at `codec.go:261` afterward dereferences unmapped memory → segmentation fault.
- **Confirmation this is real:** This exact commit was reverted on `main` — `6e89250a5d Revert "Chunked remote read: close the querier earlier"` (PR #14515 reverting #13777). The revert message states: *"Believed to trigger segmentation faults due to memory-mapped block data still being accessed by iterators after the querier is closed."* The revert is reachable from HEAD's history, so the tree currently under review contains the buggy version.
- **Why the sibling path is safe (and this one isn't):** `remoteReadSamples` (`read_handler.go:131-171`) keeps its `defer querier.Close()` inside the same closure that *fully materializes* the result via `ToQueryResult(...)` before the closure returns. The chunked path streams lazily, so moving `Close()` ahead of consumption breaks the resource lifetime invariant. Note the head-chunk path happens to be safe because `hcr.ChunkWithCopy` (`tsdb/querier.go:717`) copies; only persistent-block reads (the typical historical remote-read case) crash — which makes this an intermittent, data-dependent segfault that's easy to miss in light testing.
- **How to fix:** The early-close approach is fundamentally incompatible with the lazy, mmap-backed streaming iterator. Either (a) revert to closing the querier only after `StreamChunkedReadResponses` has fully consumed the set (the original behavior), or (b) if bounding memory on broken requests is the real goal, address it a different way (e.g. copying chunk bytes before close, or relying on `ctx` cancellation to tear the querier down) rather than closing the querier while its iterators are still live. Option (a) is what upstream chose.

#### Important (Should Fix)

**No test covers the streamed path against real (block-backed) storage** — `storage/remote/read_handler.go`.

- The change ships with zero test updates. A test that exercises `remoteReadStreamedXORChunks` against a queryable whose chunks are mmap-backed persistent blocks (not just an in-memory/head fixture) and then reads the streamed frames would have surfaced the crash. Any in-memory-only test would pass because head chunks are copied — which is likely why this slipped through. If the early-close idea is ever revisited, a block-backed streaming test is the guard that matters.

#### Minor (Nice to Have)

- The doc comment on `getChunkSeriesSet` (lines 239-241) asserts the function ensures "timely release of the querier resources." Given the lifecycle bug, this comment is actively misleading — it documents the intent as if it were safe. Whatever the resolution, the comment should not claim safe early release while iterators outlive the querier.

### Recommendations

- Treat this as a lifetime-ownership problem, not a code-organization problem. The clean-looking extraction obscured the fact that ownership of the mmap-backed bytes was being dropped mid-stream. When a function returns a lazy iterator, any `defer Close()` on the resource that iterator depends on must move to the consumer's scope.
- Add a regression test that streams from persistent blocks before considering any future attempt at early release.
- If OOM-on-broken-requests is a live concern, capture it as a separate issue and design against context cancellation / read deadlines, which tear down the querier safely at a point where iteration has stopped.

### Assessment

**Ready to merge?** No.

**Reasoning:** The change relocates `querier.Close()` ahead of the lazy consumption of the `ChunkSeriesSet`, so streamed reads that touch persistent (mmap-backed) blocks dereference unmapped memory and segfault; this is confirmed by the upstream revert of this very commit (PR #14515). The refactor is otherwise clean, but the core premise — closing the querier "earlier" in a lazily-streamed path — is unsound and should not land as written.
