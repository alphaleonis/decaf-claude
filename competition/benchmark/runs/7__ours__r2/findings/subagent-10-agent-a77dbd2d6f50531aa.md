# subagent agent-a77dbd2d6f50531aa

The exploration agent confirms my full chain and sharpens it decisively:

- **Persistent (on-disk) block chunks ALIAS the mmap** with no copy (`chunks.go:700-703`) — protected only by the `pendingReaders` barrier.
- **Head mmapped chunks are COPIED** out of the mmap under `readPathMtx` in `ChunkDiskMapper.Chunk()` (`head_chunks.go:765-773`) — so the head path is self-contained and safe.
- **The merge layer is lazy** — the returned set is not self-contained after `Select()`.
- **Live-DB block deletion is real**: compaction → `reloadBlocks` → `deleteBlocks` → `Block.Close()` (`pendingReaders.Wait()`) → `chunkr.Close()` unmap → `os.RemoveAll`.

I have everything needed. Here is my review.

---

## System Model

**Boundary under review:** `storage.SampleAndChunkQueryable` contract ↔ its TSDB implementation ↔ the remote-read handler consumer.

**Lifetime/ownership contract (as implemented):** For the TSDB persistent-block path, `ChunkQuerier.Select()` returns a *lazy* `ChunkSeriesSet`. Chunk metadata is read during `Next()`, but chunk **bytes** are read only during iteration (`series.Iterator()` → `populateWithDelChunkSeriesIterator.next()` → `ChunkReader.ChunkOrIterable()`), which returns a chunk whose `Bytes()` slice **aliases the block's memory-mapped segment file** (`tsdb/chunks/chunks.go:700-703`, `chunkenc/chunk.go:305-311` — `pool.Get` wraps, does not copy). The mmap stays valid because the per-query `blockChunkReader` holds `Block.pendingReaders` up; `querier.Close()` → `blockBaseQuerier.Close()` → `blockChunkReader.Close()` → `pendingReaders.Done()` releases that guard. `Block.Close()` (invoked by compaction/retention deletion on a *live* DB) does `pendingReaders.Wait()` then `chunkr.Close()` (munmap) and `os.RemoveAll`. **The querier owns the lifetime of the returned chunk bytes; they are not valid after Close.** The head path deliberately copies bytes out (`head_chunks.go:770-771`) precisely to be self-contained — confirming the codebase treats "bytes must not outlive the reader" as a real invariant that the block path satisfies only via `pendingReaders`.

**What the change does:** `getChunkSeriesSet` defers `querier.Close()` and returns the lazy set, so Close runs on function return — *before* `StreamChunkedReadResponses` iterates and calls `chunk.Bytes()`.

---

```json
[
  {
    "file": "storage/remote/read_handler.go",
    "line": 247,
    "severity": "Critical",
    "category": "design",
    "issue": "[API_CONTRACT] getChunkSeriesSet closes the ChunkQuerier (defer querier.Close(), runs on return) before the returned lazy ChunkSeriesSet is consumed by StreamChunkedReadResponses. For the TSDB persistent-block path the returned chunks' Bytes() alias the block's memory-mapped segment files (tsdb/chunks/chunks.go:700-703, no copy); the querier's Close releases the Block.pendingReaders guard (block.go:567 -> pendingReaders.Done()) that is the sole mechanism preventing Block.Close() (compaction/retention deletion on a live DB: db.go reloadBlocks->deleteBlocks->block.Close->pendingReaders.Wait->chunkr.Close munmap + os.RemoveAll) from unmapping/deleting those files. A compaction or retention cycle that deletes an in-range block while the response is still streaming will munmap memory that StreamChunkedReadResponses then reads via ChunkOrIterable/chunk.Bytes(), i.e. a use-after-munmap -> SIGSEGV or a corrupted/garbage chunk in the served response. The window is widest for exactly the slow/large historical remote reads this PR targets. The storage.ChunkQuerier contract does not grant 'consumable after Close'; LabelQuerier.Close is documented as 'releases the resources of the Querier' and LabelValues warns results are 'not safe to use beyond the lifetime of the querier' — the new pattern violates that ownership contract. The prior code (Close deferred until after StreamChunkedReadResponses returned) respected it.",
    "fix": "Keep the querier open until the ChunkSeriesSet is fully consumed. Options: (a) revert to closing the querier after StreamChunkedReadResponses completes (move Close back out of the helper, or have the helper return querier+set and Close in the caller after streaming); (b) if early release is required to bound memory, make the set self-contained first by copying chunk bytes out of the mmap before Close (as the head path does in ChunkDiskMapper.Chunk), rather than relying on lazy mmap-aliased reads. Do not close the resource that owns the returned data before that data is consumed.",
    "confidence": 75,
    "pre_existing": false
  },
  {
    "file": "storage/remote/read_handler.go",
    "line": 239,
    "severity": "Medium",
    "category": "design",
    "issue": "[EVOLUTION_READINESS] The helper name and doc comment ('encapsulating the operation in its own function to ensure timely release of the querier resources') assert early querier release as a safety/benefit, encoding an invariant that directly contradicts the storage.ChunkQuerier lifetime-ownership contract for lazy implementations. Because the storage interface never documents whether a returned ChunkSeriesSet is consumable after the producing querier is closed, this pattern hard-codes an undocumented, implementation-specific 'self-contained after Close' assumption. It happens to hold for the head block (bytes copied) but not for persistent blocks (bytes aliased) and not for any future/alternate lazy Queryable (e.g. a fanout secondary, a remote/streaming chunk source, tiered storage). The comment will actively mislead future maintainers into believing consume-after-Close is safe, propagating this class of bug.",
    "fix": "Document the lifetime/ownership invariant on storage.ChunkQuerier/ChunkSeriesSet (e.g. 'the returned set and its chunks must not be consumed after the querier is closed unless the implementation guarantees self-containment'). Correct the helper comment so it does not present consume-after-close as safe. If the design intent is truly to release early, make self-containment an explicit, tested contract rather than an incidental property of one backend.",
    "confidence": 75,
    "pre_existing": false
  }
]
```

## Considered But Not Flagged

- **Head-block path (mmapped and in-memory head chunks).** Not a defect. `ChunkDiskMapper.Chunk()` copies chunk bytes out of the mmap under `readPathMtx` (`tsdb/chunks/head_chunks.go:765-773`), and the open head chunk is deep-copied via `ChunkWithCopy` (`head_read.go:371-382`). `headChunkReader.Close()` only closes append-isolation state (`isolation.go:36-41`), which is unrelated to mmap lifetime. Head-derived chunks are self-contained, so consuming them after Close is safe. This is corroborating evidence that the hazard is specific to persistent on-disk blocks, and that the codebase already treats "chunk bytes must not outlive the reader" as a real invariant.

- **Error propagation via `storage.ErrChunkSeriesSet` + `chunks.Err()` check (read_handler.go:206, 245).** Sound, and a slight improvement. On `ChunkQuerier()` failure the helper returns an error-bearing set whose `Err()` is checked before streaming; iteration-time errors are still surfaced by `StreamChunkedReadResponses` via `iter.Err()`/`ss.Err()`. `chunks.Err()` on the lazy merge set before any `Next()` returns nil, but that is correct — it does not mask later errors. No finding.

- **`remoteReadSamples` (sample, non-chunk path).** Unchanged and unaffected: `ToQueryResult` fully materializes samples into `prompb` structs before the deferred `querier.Close()` runs, so its set is self-contained. The bug is unique to the lazy chunk path.

- **Concurrency correctness of `getChunkSeriesSet` in isolation.** The helper itself is fine (querier per call, no shared mutable state). The defect is purely the ordering of Close relative to cross-boundary consumption, captured in the primary finding.

### Probe Requests
(nominated only — not run; shared read-only tree)
1. **Race/UAF reproduction:** a targeted test in `tsdb`/`storage/remote` that (a) opens a `DB` with ≥2 persistent blocks in range, (b) creates the chunk querier and obtains the lazy `ChunkSeriesSet`, (c) triggers compaction+`reloadBlocks` (deleting the source blocks) *after* `querier.Close()` but *before* fully consuming the set, then (d) iterates and calls `chunk.Bytes()`. Run under `-race` and/or with `GODEBUG=madvdontneed` / an mmap that faults on access to surface the use-after-munmap deterministically.
2. **Contract assertion:** confirm via `git log`/PR history whether a follow-up reverts or guards this (the mechanism strongly suggests it should), to validate severity framing.

**Central contract conclusion:** The `storage.ChunkQuerier` → tsdb persistent-block implementation does **not** permit iterating series / reading `chunk.Bytes()` after `querier.Close()`. The returned chunks alias mmap memory whose lifetime is owned by the querier via `Block.pendingReaders`; `Close()` releases that ownership. This change consumes the set after Close, introducing a use-after-munmap that a concurrent compaction/retention deletion of an in-range block can turn into a crash or corrupted response — most likely in exactly the slow-stream scenario the PR aims to improve.
