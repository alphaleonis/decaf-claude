# subagent agent-ab5e5887c73ca6d14

## Go Idiom Review — storage/remote/read_handler.go (PR #13777, "Chunked remote read: close the querier earlier")

**Verification performed:** Traced the resource chain concretely rather than relying on interface docs alone.

- `blockChunkQuerier.Select()` (`tsdb/querier.go:174-196`) returns `NewBlockChunkSeriesSet(...)`, which retains the querier's `IndexReader`/`ChunkReader` (`q.index`, `q.chunks`) by reference — it does not copy chunk bytes at Select time.
- Its iterator, `populateWithDelChunkSeriesIterator.Next()` (`tsdb/querier.go:877` → `populateCurrForSingleChunk`/`populateChunksFromIterable`), pulls samples from `p.currDelIter`, which is driven from `cr.ChunkOrIterable(meta)` — i.e. reads happen lazily, on each `Next()` call made by the *consumer*, not at `Select()` time.
- `chunks.Reader.Close()` (`tsdb/chunks/chunks.go:656-658`) calls `tsdb_errors.CloseAll(s.cs)`, closing the `fileutil.MmapFile`s backing `s.bs` — this unmaps the segment files the `ByteSlice`s point into. It is a real, synchronous release, not a refcount decrement.
- `storage/merge.go`'s `mergeGenericQuerier.Select` (the fan-out layer `h.queryable` actually goes through) is equally lazy — even the single-querier case just forwards to the underlying `Select`, and the multi-querier case returns a `lazyGenericSeriesSet`. So wrapping in a fanout/merge queryable does not shield this.
- `StreamChunkedReadResponses` (`storage/remote/codec.go:221-296`) is the consumer: `ss.Next()`/`ss.At()`/`iter.Next()`/`iter.At()` are called there — strictly *after* `getChunkSeriesSet` has already returned to its caller.

Go's defer semantics: `return querier.Select(...)` evaluates the return value first, then runs the deferred `querier.Close()`, then control returns to the caller. Because the returned `ChunkSeriesSet` shares (by reference) the same `ChunkReader`/`IndexReader` objects owned by `querier`, the `Close()` call mutates state the caller's series set still depends on — the classic "cleanup runs on an object whose lazily-evaluated output escapes the defer's scope" trap. This is a genuine use of unmapped memory once the caller starts iterating: on Linux that reliably manifests as a `SIGSEGV` → an unrecoverable Go runtime fatal error (crashes the whole `prometheus` process, not just the request), or — if the OS has not yet reused the unmapped pages — silently returns stale/garbage chunk bytes to the remote-read client.

Contrast confirmed: `remoteReadSamples` (`storage/remote/read_handler.go:117-187`) is correct — it fully materializes via `ToQueryResult(querier.Select(...))` *inside* the same closure where `defer querier.Close()` lives, before that closure returns. `getChunkSeriesSet` instead returns the lazy set itself across the defer boundary, which is the bug this PR's "close earlier" intent introduced.

Also checked: `chunks.Err()` as the sole immediate check (`read_handler.go:206-208`) is not itself a regression — `storage.ChunkQuerier.Select` has no `error` return in its signature, so surfacing immediate errors (e.g. `PostingsForMatchers` failures) via `.Err()` is the existing interface contract, and `StreamChunkedReadResponses` also checks `ss.Err()`/`iter.Err()` during and after iteration (`codec.go:292-295`). Not flagged.

```json
[
  {
    "file": "storage/remote/read_handler.go",
    "line": 247,
    "severity": "Critical",
    "category": "resource-management",
    "issue": "[GO_DEFER] getChunkSeriesSet defers querier.Close() but returns the lazy storage.ChunkSeriesSet produced by querier.Select() (line 265); the caller (remoteReadStreamedXORChunks -> StreamChunkedReadResponses) iterates that set only after this function has returned, i.e. after Close() has already run and released/unmapped the underlying ChunkReader/IndexReader (tsdb blockChunkQuerier backs onto mmap'd segment files via chunks.Reader.Close -> CloseAll(s.cs)). This is a use-after-close: reading chunk bytes from an unmapped mmap region typically crashes the process (SIGSEGV -> unrecoverable Go fatal error) or returns corrupted data.",
    "fix": "Do not defer Close() inside getChunkSeriesSet while returning its lazy output. Either fully materialize the series (mirror remoteReadSamples' ToQueryResult-before-Close pattern) if streaming isn't required, or change getChunkSeriesSet to also return the querier's Close func/the querier itself so the caller defers Close() in remoteReadStreamedXORChunks's per-query closure, after StreamChunkedReadResponses has finished consuming the set for that query.",
    "confidence": 100,
    "pre_existing": false
  }
]
```

### Probe Requests

- **Test file+name:** `storage/remote/read_handler_test.go`, `TestStreamReadEndpoint` (line 198).
- **What to add (not run):** before constructing `api := NewReadHandler(...)` (line 213), force the loaded head data into a persistent, mmap-backed block: `require.NoError(t, store.DB.Compact(context.Background()))` (via the embedded `*tsdb.DB` on `teststorage.TestStorage`, `util/teststorage/storage.go:53-54`). Without compaction, `LoadedStorage` only exercises the in-memory Head querier, whose chunks live in RAM and whose `Close()` merely drops a read lock — that's why the existing test doesn't already catch this; it never queries a `blockChunkQuerier` backed by mmap'd chunk segment files.
- **Production lines implicated:** `storage/remote/read_handler.go:247-251` (the `defer querier.Close()`) and `:265` (`return querier.Select(...)`).
- **Expected failure if run:** a crash (`SIGSEGV`/Go runtime fatal error reading from unmapped memory) or, nondeterministically, corrupted/garbage chunk bytes in the streamed response instead of the expected `test_metric1`/histogram series — i.e. `TestStreamReadEndpoint` would fail or the test binary would abort rather than reach its `require.Equal` assertions on decoded results.

## Considered But Not Flagged

- **`chunks.Err()` as the only pre-stream check** — matches `storage.ChunkQuerier.Select`'s existing no-error-return contract; iteration-time errors are still caught via `iter.Err()`/`ss.Err()` inside `StreamChunkedReadResponses`. Not a regression (confidence 0, false positive on inspection).
- **Inner `for _, w := range ws` shadowing the outer `w http.ResponseWriter` parameter** in `remoteReadStreamedXORChunks` — shadows correctly within the loop body only (`w.Error()` on the shadowed `annotations` element), functionally correct, same pattern pre-exists in the sibling `remoteReadSamples`. Style only, no consequence (not reported, below the anchor-50 bar).
- **Head/in-memory chunk querier path** (as opposed to block-backed) — closing a head querier releases an RLock rather than unmapping memory; still a potential race against concurrent head truncation/GC reusing chunk memory while iteration continues, but confirming that requires deeper head-chunk-GC tracing beyond this diff's scope to state as a distinct, actionable finding; the block-backed path alone is sufficient to confirm Critical severity, so this was not pursued as a second finding (speculative, confidence 25).

**Files read:** `/home/decaf/code/decaf-claude/competition/benchmark/repos/7/storage/remote/read_handler.go`, `/home/decaf/code/decaf-claude/competition/benchmark/repos/7/storage/remote/codec.go`, `/home/decaf/code/decaf-claude/competition/benchmark/repos/7/tsdb/querier.go`, `/home/decaf/code/decaf-claude/competition/benchmark/repos/7/tsdb/chunks/chunks.go`, `/home/decaf/code/decaf-claude/competition/benchmark/repos/7/storage/merge.go`, `/home/decaf/code/decaf-claude/competition/benchmark/repos/7/util/teststorage/storage.go`, `/home/decaf/code/decaf-claude/competition/benchmark/repos/7/storage/remote/read_handler_test.go`.
