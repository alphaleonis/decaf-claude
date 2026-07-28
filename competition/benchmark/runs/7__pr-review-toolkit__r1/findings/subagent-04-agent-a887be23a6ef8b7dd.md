# subagent agent-a887be23a6ef8b7dd

I now have complete, verified evidence. Let me compile the review.

## Code Review: PR #13777 "Chunked remote read: close the querier earlier"

### Scope reviewed
- `storage/remote/read_handler.go` — the refactored `remoteReadStreamedXORChunks` and new `getChunkSeriesSet` (the only changed file)
- Traced the full lazy-read lifecycle through `storage/remote/codec.go`, `storage/interface.go`, `storage/generic.go`, `storage/merge.go`, `tsdb/querier.go`, `tsdb/block.go`, `tsdb/chunks/chunks.go`, `tsdb/db.go`

---

### CRITICAL — Use-after-close of the chunk querier: the `ChunkSeriesSet` is streamed after its querier (and mmap read reference) has been released

**Location:** `storage/remote/read_handler.go:242-266` (new `getChunkSeriesSet`), consumed at `storage/remote/read_handler.go:205-218`.

**What the change does.** `getChunkSeriesSet` registers `defer querier.Close()` (lines 247-251) and then `return querier.Select(...)` (line 265). Go runs that deferred `Close()` when `getChunkSeriesSet` *returns* — i.e. the querier is closed **before** the returned `storage.ChunkSeriesSet` is ever iterated. The caller only iterates it later, inside `StreamChunkedReadResponses` (lines 210-218). In the pre-PR code the `defer querier.Close()` lived in the outer per-query closure and therefore ran **after** streaming finished (the still-unchanged sample path at lines 141-161 shows the original pattern).

**Why this is unsafe — the read is lazy, and it reads from the closed readers.** Verified chain:

1. `StreamChunkedReadResponses` pulls everything lazily, after `Select` returned: `ss.Next()` (`storage/remote/codec.go:235`), `series.Iterator` (`:237`), `iter.Next()`/`iter.At()` (`:246`,`:250`), and crucially `chk.Chunk.Bytes()` (`:261`).
2. `blockBaseSeriesSet.Next()` reads series labels from the **index reader** `b.index.Series(...)` (`tsdb/querier.go:560`) and from the **tombstones reader** `b.tombstones.Get(...)` (`:573`) — both already closed.
3. Chunk bytes are loaded lazily from the **chunk reader** during iteration: `populateWithDelGenericSeriesIterator.next()` → `p.cr.ChunkOrIterable(p.currMeta)` (`tsdb/querier.go:721`).
4. For a persistent block, `Reader.ChunkOrIterable` returns a chunk backed by `realByteSlice(f.Bytes())` — a slice **directly into the mmap**, with no copy (`tsdb/chunks/chunks.go:666-673`, mmap opened at `:635`, wrapped at `:643`). Only the in-memory head chunk is deep-copied (`ChunkWithCopy`, `tsdb/querier.go:714-719`); persistent-block and mmapped chunks are not.

**Why it becomes a use-after-unmap (the actual crash risk).** The block's mmap lifetime is guarded by a reader ref-count, and `Close()` releases that guard:

- `Block.Chunks()`/`Index()`/`Tombstones()` each call `startRead()` → `pendingReaders.Add(1)` and return a thin wrapper over the block's shared, mmap-backed readers (`tsdb/block.go:428-449`).
- The wrapper `Close()` methods only do `pendingReaders.Done()` — they do **not** unmap (`tsdb/block.go:536-539`, `557-560`, `567-570`).
- The real unmap happens only in `Block.Close()`, which sets `closing=true`, then `pendingReaders.Wait()`, and only then calls `pb.chunkr.Close()` (→ `CloseAll(s.cs)` munmap) (`tsdb/block.go:378-390`; `tsdb/chunks/chunks.go:656-658`). The method's own doc says: *"It blocks as long as there are readers reading from the block."*
- `blockBaseQuerier.Close()` closes all three readers (`tsdb/querier.go:103-115`); the merge querier closes every child querier (`storage/merge.go:255-263`); and `db.ChunkQuerier` is exactly that merge over per-block queriers (`tsdb/db.go:2067-2072`).

So the moment `getChunkSeriesSet` returns, `pendingReaders` drops to zero for every block backing this query. **[Inference — this is the documented contract of `pendingReaders`, not something I executed to reproduce; it is expected behavior, not guaranteed]** A concurrent compaction or retention deletion that calls `Block.Close()` will now pass `pendingReaders.Wait()` and unmap the chunk file **while `StreamChunkedReadResponses` is still reading bytes out of it** — a use-after-unmap, i.e. `SIGBUS`/`SIGSEGV` or silently corrupt chunk bytes in the response. The pre-PR code held the reader reference for the whole stream, which is precisely what made `Block.Close()` block until streaming completed.

**Verified vs. inferred, to be precise:**
- Verified: the querier is closed before the set is iterated; the stream reads labels/tombstones/chunk-bytes lazily from those readers; persistent chunk bytes alias the mmap with no copy; reader `Close()` only decrements `pendingReaders` while `Block.Close()` unmaps after the wait.
- [Inference]: the concrete crash/corruption requires a compaction/retention `Block.Close()` to race the in-flight stream. Absent a concurrent block close, the mmap stays mapped and results are still correct — which is why unit tests and manual testing pass and the defect is a latent data race rather than a deterministic failure.

**Severity:** Critical by impact (remote read is a heavily used path — Thanos/Cortex/federation), gated behind a race window, so non-deterministic.

**Suggested fixes (any one):**
- Keep the querier open until streaming completes: have `getChunkSeriesSet` return `(storage.ChunkSeriesSet, io.Closer)` (or the querier) and `defer querier.Close()` in the caller *after* `StreamChunkedReadResponses`, i.e. restore the original lifetime while still isolating hint construction in a helper.
- Or fully materialize/copy chunk bytes before `Close()` (defeats the streaming/memory goal, so not preferred).
- If the goal is only to bound memory on hung/broken clients, address that without shortening the reader lifetime (e.g. context cancellation / write deadlines), rather than closing the querier before its data is consumed.

---

### Secondary points from the task, with evidence

**`chunks.Err()` immediately after `Select` — correct and idiomatic (safe).** Both construction-error sources funnel into `Err()`: a failed `ChunkQuerier()` returns `storage.ErrChunkSeriesSet(err)` (`read_handler.go:245`), and a failed `PostingsForMatchers` inside `Select` returns `storage.ErrChunkSeriesSet(err)` (`tsdb/querier.go:187`). `errChunkSeriesSet.Err()` returns the wrapped error verbatim (`storage/interface.go:398,402-404`), so checking `chunks.Err()` before iterating (`read_handler.go:206`) is the right way to surface these, and it runs before any streaming output is written. Note it does **not** re-check `Err()` after iteration — but `StreamChunkedReadResponses` already returns `ss.Err()`/`iter.Err()` at the end (`codec.go:292-296`), so post-iteration errors are still surfaced.

**HTTPError status propagation preserved (safe).** Because `errChunkSeriesSet.Err()` returns the original error unwrapped, the caller's `errors.As(err, &httpErr)` (`read_handler.go:228-229`) still recovers an `HTTPError` returned by `ChunkQuerier()`, so the HTTP status-code behavior is unchanged.

**Asymmetry with the sample path is the tell (context).** `remoteReadSamples` closes its querier in the closure too, but `ToQueryResult(querier.Select(...))` (`read_handler.go:161`) **fully materializes** the result into the protobuf before the closure returns, so close-after-materialize is safe there. The chunked path is the opposite: after this PR it closes-then-materializes because streaming is lazy. That difference is exactly what makes the change unsafe for chunks but not for samples.

**Head in-memory chunks are copied (partial mitigation, not a fix).** `ChunkWithCopy` deep-copies the live head chunk (`tsdb/querier.go:714-719`, comment at `:693-696` about avoiding read/copy races). That protects only the in-memory head chunk; persistent-block chunks and mmapped chunks are still read straight from mmap after Close, so the exposure remains. **[Inference]** Releasing the head querier early also drops the head read reference sooner (isolation/mmapped-head-chunk truncation), an additional exposure surface I did not trace to a definitive conclusion.

---

### Minor
- **No regression test accompanies the change** (diff touches only `read_handler.go`). A race like this is hard to unit-test deterministically, but at minimum an assertion that the querier outlives streaming (e.g. a fake `ChunkQuerier` whose `Close()` marks it closed and whose returned set panics/errors if iterated post-close) would lock in the intended contract.
- **Doc comment slightly overstates safety.** `getChunkSeriesSet`'s comment (`read_handler.go:239-241`) says it ensures "timely release of the querier resources" — accurate about timing, but the release happens *before* the resources are done being used, which is the core problem. If the lifetime is fixed, update the comment accordingly.

### Bottom line
The refactor is clean and the `Err()`/error-propagation mechanics are correct, but the central lifecycle change is unsafe: it closes the chunk querier — releasing the `pendingReaders` guard that keeps block mmaps alive — before the returned `ChunkSeriesSet` is iterated and streamed. Verified that streaming reads labels, tombstones, and (uncopied) chunk bytes from those released readers; [Inference] a concurrent block compaction/retention unmap during streaming yields a use-after-unmap crash or corrupt response. Recommend restoring the querier's lifetime to span the entire `StreamChunkedReadResponses` call while keeping the helper for hint construction.

Correction note per my working directive: the crash/corruption outcome above is labeled [Inference] because it depends on a concurrent `Block.Close()` I did not reproduce; the lifecycle facts it rests on are directly verified at the cited `file:line` locations.
