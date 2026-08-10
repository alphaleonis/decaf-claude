Below is the reviewer subagent's full report, verbatim.

---

### Strengths

- **The refactor is clean and readable.** Extracting the querier-open / hints-build / `Select` sequence into `getChunkSeriesSet` (`storage/remote/read_handler.go:242-266`) removes a fair amount of inline noise from `remoteReadStreamedXORChunks` and makes the loop body (`:205-208`) easy to follow.
- **Error propagation is preserved and arguably cleaner.** Returning `storage.ErrChunkSeriesSet(err)` when `ChunkQuerier()` fails (`:245`) and surfacing it via `chunks.Err()` at the call site (`:206`) correctly funnels the querier-open error into the same `return err` path the old code used, so the HTTP error behavior (`HTTPError` → status, else 500) is unchanged.
- **The `Close()` error is still logged, not swallowed** (`:248-250`), matching the pre-existing pattern in `remoteReadSamples` — the warning-on-close semantics were retained.
- **No double-close.** `Close()` is invoked exactly once per query iteration via the single `defer` in the helper; the caller never closes.

### Issues

#### Critical (Must Fix)

**1. The querier is now closed *before* its lazily-read chunk data is consumed — a use-after-release regression. `storage/remote/read_handler.go:205-208` + `:242-266`**

This is the core problem, and it is the opposite of an improvement for the streaming path.

- `getChunkSeriesSet` returns `querier.Select(ctx, true, hints, ...)` (`:265`). For the local TSDB, `Select` returns a **lazy** `ChunkSeriesSet` (`tsdb/querier.go:174-196` → `NewBlockChunkSeriesSet`), not a materialized one. Chunk bytes are read on demand during iteration via `populateWithDelGenericSeriesIterator.next()` → `p.cr.ChunkOrIterable(...)` (`tsdb/querier.go:721`).
- The `defer querier.Close()` (`:247-251`) fires **when `getChunkSeriesSet` returns** — i.e., *before* `StreamChunkedReadResponses` (`:210`) ever calls `ss.Next()` / `series.Iterator()` / `chk.Chunk.Bytes()` (`storage/remote/codec.go:235-291`).
- For persistent blocks, `ChunkOrIterable` returns a chunk whose bytes point **directly into the mmap'd segment file** (no copy): `pool.Get` sets `c.b.stream = b` where `b = realByteSlice.Range(...)` is a subslice of the mmap (`tsdb/chunks/chunks.go:700-703`, `:584-586`), and `XORChunk.Bytes()` returns that same slice (`tsdb/chunkenc/xor.go:75-77`). That slice is exactly what the stream writes at `codec.go:261`.

Why closing early is unsafe: `blockChunkReader.Close()` does **not** unmap — it only calls `pb.pendingReaders.Done()` (`tsdb/block.go:567-569`). The mmap is unmapped later by `Block.Close()`, which first does `pendingReaders.Wait()` (`tsdb/block.go:378-389`). That `pendingReaders` refcount is the *only* thing preventing a block's chunk file from being unmapped while a query reads it — `deleteBlocks` even documents this ("needs to be closed first as it might need to wait for pending readers to complete", `tsdb/db.go:1656-1662`). By calling `Close()` (→ `Done()`) before the stream drains, this change releases that protection while `StreamChunkedReadResponses` is still reading the mmap.

Failure scenario: a remote read streaming persistent-block data races with a background block deletion (compaction of the source block completes, or retention kicks in → `db.reloadBlocks()` → `deleteBlocks()` → `Block.Close()`). `pendingReaders.Wait()` returns immediately (the reader already signaled `Done`), `pb.chunkr.Close()` unmaps the segment, and the in-flight `StreamChunkedReadResponses` reads from an unmapped region → **SIGSEGV, or silently serves corrupted chunk bytes to the client.**

By contrast the **old** code deferred `querier.Close()` inside the per-query IIFE, so it ran *after* `StreamChunkedReadResponses` finished — the querier (and its `pendingReaders` hold) spanned the entire stream, and block deletion correctly blocked until the read completed. The old ordering was correct; this PR inverts it.

Note the tension the PR is really fighting: holding the querier across a slow client transfer does block compaction/truncation for that block — a legitimate liveness concern. But you cannot both release the querier early *and* keep reading its mmap'd chunks lazily. A safe "close earlier" would require materializing/copying all chunk bytes before `Close()` (which defeats the streaming/memory goal), or spanning the querier's lifetime over the stream as before. As written, the change trades a liveness concern for a memory-safety bug — recommend reverting the early-close and keeping the querier open until `StreamChunkedReadResponses` returns (i.e., restore the deferred close at the closure scope, or pass a `func()`/`defer` that runs after streaming).

The helper's own doc comment — "to ensure timely release of the querier resources" (`:239-241`) — documents precisely the intent that is unsafe here; if the early-close is kept for any reason, that comment should at minimum be corrected, but the ordering itself is the defect.

#### Important (Should Fix)

**2. No test covers the changed lifecycle. (diff adds 0 test lines; `storage/remote/read_handler_test.go`)**

The diff touches only `read_handler.go`. `TestStreamReadEndpoint` (`:198`) loads data via `promql.LoadedStorage` and issues a single query with no concurrent compaction/deletion, so it exercises functional streaming output but cannot detect the use-after-release above — which is exactly why CI stays green despite the regression. At minimum, a test asserting the querier remains valid for the duration of the stream (e.g. a fake `ChunkQuerier` whose `Close()` marks it closed and whose returned series set panics/errors if iterated after close) would have caught this and would guard against re-introduction.

#### Minor (Nice to Have)

**3. `chunks.Err()` pre-check is partially redundant. `storage/remote/read_handler.go:206`**

For a real (non-error) lazy merge series set, `Err()` before the first `Next()` generally returns `nil` (init is deferred), so this check reliably catches only the `ErrChunkSeriesSet` open-failure path; genuine `Select`-time/iteration errors still surface inside `StreamChunkedReadResponses`. That's acceptable and not wrong, but the check's coverage is narrower than it may appear — worth a one-line comment clarifying it guards the querier-open error, so a future reader doesn't assume it validates the whole query.

### Recommendations

- Restore the invariant that the chunk querier outlives consumption of its `ChunkSeriesSet`: keep the `defer querier.Close()` in a scope that ends *after* `StreamChunkedReadResponses` returns (the pre-PR structure did this correctly). If the goal of not holding the querier across a slow client is important, solve it explicitly (e.g. bounded buffering/copy of chunk bytes before release, or a documented decision to accept the hold) rather than by reordering `Close()` ahead of the lazy read.
- Add a regression test with a `ChunkQuerier` test double that fails loudly if its series set is iterated after `Close()`.
- If any variant of early-close is retained, fix the `getChunkSeriesSet` doc comment so it doesn't advertise "timely release" as safe for lazily-consumed results.

### Assessment

**Ready to merge?** No.

**Reasoning:** The change moves `querier.Close()` ahead of the lazy draining of the returned `ChunkSeriesSet`, releasing the `pendingReaders` hold that protects the block's mmap while `StreamChunkedReadResponses` is still reading chunk bytes straight out of that mmap — a timing-dependent use-after-unmap that can crash Prometheus or serve corrupted data when a remote read races a concurrent block compaction/retention deletion; the prior ordering (close after streaming) was correct.
