# subagent agent-a3085026915bfa0d7

## Findings: PR #13777 review — `storage/remote/read_handler.go`

**Verdict: the change violates a documented/enforced resource-lifetime contract.** The new `getChunkSeriesSet` helper closes the querier before the `ChunkSeriesSet` it returns is iterated, and the underlying `tsdb` block implementation relies on the querier staying open for exactly that duration. This is not a theoretical concern — I confirmed via `gh api` that it caused a production SIGSEGV and PR #13777 was reverted four months later.

### The conflicting code (storage/remote/read_handler.go)

```
239  // getChunkSeriesSet executes a query to retrieve a ChunkSeriesSet,
240  // encapsulating the operation in its own function to ensure timely release of
241  // the querier resources.
242  func (h *readHandler) getChunkSeriesSet(ctx context.Context, query *prompb.Query, filteredMatchers []*labels.Matcher) storage.ChunkSeriesSet {
243      querier, err := h.queryable.ChunkQuerier(query.StartTimestampMs, query.EndTimestampMs)
...
247      defer func() {
248          if err := querier.Close(); err != nil {
...
251      }()
...
265      return querier.Select(ctx, true, hints, filteredMatchers...)
266  }
```

The `defer` fires the instant `getChunkSeriesSet` returns at line 265 — i.e. the querier is closed **before** the caller ever touches the returned `ChunkSeriesSet`. The caller, `remoteReadStreamedXORChunks` (line 205), then hands that already-orphaned `ChunkSeriesSet` to `StreamChunkedReadResponses` (lines 210-218), which does the actual iteration.

### Why that's unsafe, per the interface docs

1. **`storage/interface.go:171-172`** — `LabelQuerier.Close()` (embedded in both `Querier` and `ChunkQuerier`):
   > `// Close releases the resources of the Querier.`

2. **`storage/remote/codec.go:219-220`** — doc on `StreamChunkedReadResponses`:
   > `// StreamChunkedReadResponses iterates over series, builds chunks and streams those to the caller.`
   > `// It expects Series set with populated chunks.`

   The function's own body (`storage/remote/codec.go:235-296`) shows this "iteration" is lazy: `ss.Next()` / `series.Iterator(iter)` / `iter.Next()` / `iter.At()` (line 250, `chk.Chunk.Bytes()`) all run *inside this function*, i.e. after `getChunkSeriesSet` has already returned and closed the querier. The comment's claim that it "expects...populated chunks" doesn't match reality for the real (`tsdb`) `ChunkQuerier` — chunks are populated lazily during this very iteration, not up front.

3. **`tsdb/querier.go:174-196`** — `blockChunkQuerier.Select` returns a `ChunkSeriesSet` (`NewBlockChunkSeriesSet`) that holds a live reference to `q.chunks` (the block's `ChunkReader`) and reads through it lazily via `populateWithDelGenericSeriesIterator.next()` → `p.cr.ChunkOrIterable(p.currMeta)` (`tsdb/querier.go:721`), which is invoked from inside `iter.Next()` during `StreamChunkedReadResponses`'s loop — **after** `getChunkSeriesSet`'s deferred `querier.Close()` has already run.

4. **`tsdb/block.go:377-378`** — the actual synchronization contract this breaks:
   > `// Close closes the on-disk block. It blocks as long as there are readers reading from the block.`
   `func (pb *Block) Close()` waits on `pb.pendingReaders` (`tsdb/block.go:383`) before physically closing/unmapping the chunk and index files. A per-query `ChunkReader.Close()` (`tsdb/block.go:567-569`, `blockChunkReader.Close()`) merely does `pb.pendingReaders.Done()` — it's the release signal `Block.Close()` waits on. `getChunkSeriesSet` fires that "I'm done reading" signal via `querier.Close()` before `StreamChunkedReadResponses` has actually finished reading chunk bytes.

5. **`tsdb/chunks/chunks.go:621-644, 656-658`** — the chunk `Reader` is backed by `fileutil.OpenMmapFile`; `Reader.Close()` unmaps those files (`tsdb_errors.CloseAll(s.cs)`). If a concurrent block deletion/compaction calls `Block.Close()` after the premature `pendingReaders.Done()` but while `StreamChunkedReadResponses` is still calling `ChunkOrIterable` on the now-unmapped segment, the read lands on freed memory.

### External corroboration (via `gh api`)

- Issue [prometheus/prometheus#14422](https://github.com/prometheus/prometheus/issues/14422) "SIGSEGV after writing block" — crash trace: `encoding/binary.Uvarint` → `tsdb/chunks.(*Reader).ChunkOrIterable` (`tsdb/chunks/chunks.go:681`) → `blockChunkReader.ChunkOrIterable`, happening right after a block write/compaction.
- PR [prometheus/prometheus#14515](https://github.com/prometheus/prometheus/pull/14515) "Revert 'Chunked remote read: close the querier earlier'", body: *"I believe the iterators for the querier can access memory-mapped files, which are closed when the querier is closed... A better fix might be to reference-count the chunk-reader so it is only closed when no longer accessed."* This PR reverts exactly the change under review here (#13777).

### Contrast with the non-chunked path (proves the pattern is known-correct elsewhere)

`remoteReadSamples` (`storage/remote/read_handler.go:117-187`) keeps the querier open for the whole `ToQueryResult(...)` call (line 161), and `ToQueryResult` (`storage/remote/codec.go:125-...`) fully materializes samples into `prompb` structs before returning — all while the querier is still open, with `defer querier.Close()` covering the entire closure. This is the safe pattern the chunked path (via `getChunkSeriesSet`) deviates from by closing before, rather than after, consumption.

### Summary

The doc comment added by this PR — *"encapsulating the operation in its own function to ensure timely release of the querier resources"* (`storage/remote/read_handler.go:239-241`) — is factually wrong about safety: it treats querier-close as safe once `Select()` returns, but `Select()` returns a lazy `ChunkSeriesSet` whose iteration (in `StreamChunkedReadResponses`, called from `storage/remote/read_handler.go:210-218`) still needs the querier's underlying (mmap-backed) resources. This directly conflicts with `Block.Close()`'s documented contract that it only releases resources once all readers are done (`tsdb/block.go:377-383`). This is a confirmed real bug (crash), not merely a style nit — the PR was subsequently reverted.
