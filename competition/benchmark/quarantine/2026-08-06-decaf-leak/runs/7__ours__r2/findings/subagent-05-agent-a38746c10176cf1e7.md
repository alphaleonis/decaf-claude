# subagent agent-a38746c10176cf1e7

I now have complete evidence for all four questions. Here is my analysis.

---

# Prometheus TSDB Resource-Lifetime / Concurrency Trace

Repo: `/home/decaf/code/decaf-claude/competition/benchmark/repos/7`

## Q1 — Code paths that call `Block.Close()` on a live, in-use DB (not just shutdown)

**Conclusion:** Yes. Background compaction produces a new block, then `reloadBlocks()` marks the SOURCE blocks (the new block's compaction parents) deletable and `deleteBlocks()` closes+removes them — all while the DB continues serving queries. The only lock held across deletion is `db.mtx` (briefly, in `reloadBlocks`), not for the whole compaction.

Chain of evidence:

- Background loop drives it. `tsdb/db.go:986` `func (db *DB) run(...)`, selecting on `case <-db.compactc:` (`tsdb/db.go:1012`) which invokes `db.Compact(ctx)`.
- `tsdb/db.go:1137` `func (db *DB) Compact(...)` takes only the compaction mutex `db.cmtx.Lock()` (`:1138`), then `return db.compactBlocks()` (`:1216`).
- `tsdb/db.go:1369` `compactBlocks()` produces the new block and reloads:
  - `:1386` `uid, err := db.compactor.Compact(db.dir, plan, db.blocks)` — new block from the planned SOURCE blocks.
  - `:1391` `if err := db.reloadBlocks(); err != nil {`
- `tsdb/db.go:1430` `reloadBlocks()` — marks the new block's parents (the sources) deletable, then deletes:
  - `:1441-1442` `db.mtx.Lock(); defer db.mtx.Unlock()` — the only query-affecting lock.
  - `:1449` `deletableULIDs := db.blocksToDelete(loadable)`
  - `:1454-1465` loops loaded blocks and marks parents deletable:
    ```go
    for _, b := range block.Meta().Compaction.Parents {
        ...
        deletable[b.ULID] = nil
    }
    ```
  - `:1525-1529` appends old in-memory blocks that are deletable so they can be closed.
  - `:1530` `if err := db.deleteBlocks(deletable); err != nil {`
- `tsdb/db.go:1573` `deletableBlocks()` also independently marks already-compacted blocks (`:1590-1592`):
  ```go
  if block.Meta().Compaction.Deletable {
      deletable[block.Meta().ULID] = struct{}{}
  }
  ```
  plus retention (`BeyondTimeRetention` `:1608`, `BeyondSizeRetention` `:1631`).
- `tsdb/db.go:1659` `deleteBlocks()` — closes the loaded block THEN removes the dir:
  ```go
  for ulid, block := range blocks {
      if block != nil {
          if err := block.Close(); err != nil { ... }   // :1662
      }
      ...
      fileutil.Replace(toDelete, tmpToDelete)            // :1678
      os.RemoveAll(tmpToDelete)                          // :1681
  }
  ```
  The doc comment (`:1656-1658`) states: "closes the block if loaded ... needs to be closed first as it might need to wait for pending readers to complete."

DB keeps serving queries: `tsdb/db.go:1909` `Querier()` only takes `db.mtx.RLock()` (`:1912-1913`), snapshots overlapping blocks (`:1915-1919`), then opens block queriers (which call `startRead()`), and releases. So an already-open querier holds a `pendingReaders` count that outlives the `db.mtx` critical section, and a concurrent deletion blocks on it.

Other `Block.Close()` sites on a live DB: `reloadBlocks` also closes newly-opened-but-superseded blocks on the corruption path (`tsdb/db.go:1472` `block.Close()`), and `CleanTombstones` re-invokes `reloadBlocks` (`tsdb/db.go:2142`). (`tsdb/db.go:587` is the DB-open error path; `:1842` is head close at shutdown — not the live-DB case.)

## Q2 — `pb.pendingReaders.Wait()` in `Block.Close()` is the deletion barrier

**Conclusion:** Confirmed. `Block.Close()` sets `closing=true`, then blocks on `pendingReaders.Wait()` until every open block reader has called `Done()`.

`tsdb/block.go:377-390`:
```go
// Close closes the on-disk block. It blocks as long as there are readers reading from the block.
func (pb *Block) Close() error {
	pb.mtx.Lock()
	pb.closing = true
	pb.mtx.Unlock()

	pb.pendingReaders.Wait()          // :383  <-- the barrier

	return tsdb_errors.NewMulti(
		pb.chunkr.Close(),            // :386  unmaps the chunk segment files
		pb.indexr.Close(),
		pb.tombstones.Close(),
	).Err()
}
```

The counter is incremented in `startRead()` (`tsdb/block.go:416-424`): after checking `if pb.closing { return ErrClosing }` (`:420-421`) it does `pb.pendingReaders.Add(1)` (`:423`). Each reader type decrements on Close:
- `blockChunkReader.Close()` — `tsdb/block.go:567-569` `r.b.pendingReaders.Done()`
- `blockIndexReader.Close()` — `tsdb/block.go:536-538`
- `blockTombstoneReader.Close()` — `tsdb/block.go:557-559`

So `deleteBlocks` -> `Block.Close()` cannot unmap `pb.chunkr` until the per-query `blockChunkReader.Close()` runs.

## Q3 — HEAD block chunk-read path

**Conclusion:** For the HEAD, memory-mapped head chunks are **COPIED out of the mmap** inside `ChunkDiskMapper.Chunk()` before returning, so `headChunkReader.ChunkOrIterable` does **NOT** return bytes aliasing the head's mmap. `headChunkReader.Close()` only closes the isolation state (append isolation), which is unrelated to mmap file lifetime. There is **no `pendingReaders`-style guard on the head** protecting against truncation; instead mmap safety is provided by (a) the eager copy under `readPathMtx`, and (b) a separate querier/truncation-collision mechanism.

Evidence:

- `headChunkReader` and its methods, `tsdb/head_read.go:312-335`:
  ```go
  func (h *headChunkReader) Close() error {
  	if h.isoState != nil {
  		h.isoState.Close()      // :320
  	}
  	return nil
  }
  func (h *headChunkReader) ChunkOrIterable(meta chunks.Meta) (...) {
  	chk, _, err := h.chunk(meta, false)   // copyLastChunk=false
  	return chk, nil, err
  }
  func (h *headChunkReader) ChunkWithCopy(meta chunks.Meta) (...) {
  	return h.chunk(meta, true)
  }
  ```
- `isoState.Close()` is purely append-isolation bookkeeping (unlinks from a doubly-linked list under `isolation.readMtx`), `tsdb/isolation.go:36-41` — it does not release any mmap/ref guard:
  ```go
  func (i *isolationState) Close() {
  	i.isolation.readMtx.Lock()
  	defer i.isolation.readMtx.Unlock()
  	i.next.prev = i.prev
  	i.prev.next = i.next
  }
  ```
- For an mmapped (not in-memory) head chunk, `memSeries.chunk` dispatches to the disk mapper, `tsdb/head_read.go:421-434`:
  ```go
  if ix < len(s.mmappedChunks) {
  	chk, err := chunkDiskMapper.Chunk(s.mmappedChunks[ix].ref)   // :422
  	...
  }
  ```
- The decisive part — `ChunkDiskMapper.Chunk()` makes a **copy**, `tsdb/chunks/head_chunks.go:671-782`:
  ```go
  cdm.readPathMtx.RLock()
  // We hold this read lock for the entire duration because if Close()
  // is called, the data in the byte slice will get corrupted as the mmapped
  // file will be closed.
  defer cdm.readPathMtx.RUnlock()          // :672-676
  ...
  chkData := mmapFile.byteSlice.Range(chkDataEnd-int(chkDataLen), chkDataEnd)   // :765 (mmap-backed)
  // Make a copy of the chunk data to prevent a panic occurring because the returned
  // chunk data slice references an mmap-ed file which could be closed after the
  // function returns but while the chunk is still in use.
  chkDataCopy := make([]byte, len(chkData))
  copy(chkDataCopy, chkData)               // :770-771  <-- EAGER COPY
  chk, err := cdm.pool.Get(chunkenc.Encoding(chkEnc), chkDataCopy)   // :773
  ```
  So the returned head chunk is self-contained (its bytes are a heap copy), not an alias of the mmap. The `readPathMtx.RLock()` is held only for the duration of `Chunk()` (the copy happens under it), preventing a concurrent unmap during the copy.
- Truncation/deletion of head chunk files is guarded by the same `readPathMtx` (write side), not by any per-reader ref count. `ChunkDiskMapper.Truncate()` `tsdb/chunks/head_chunks.go:908` computes files to remove under `readPathMtx.RLock()` (`:909-926`) and `deleteFiles()` `:966` takes `cdm.readPathMtx.Lock()` (`:968`) to `Close()` + unmap and `delete(cdm.mmappedChunkFiles, seq)` (`:970-977`) before `os.Remove` (`:981`). Because `Chunk()` already copied the bytes out under the RLock, a truncation that proceeds after `Chunk()` returns cannot corrupt an in-flight head chunk.

Note the `copyHeadChunk` path used by queries: `populateWithDelGenericSeriesIterator.next` calls `hcr.ChunkWithCopy` for the open in-memory head chunk (`tsdb/querier.go:712-719`), and the eager `copy(newB, b)` for that in-memory chunk is in `tsdb/head_read.go:371-382`. For mmapped head chunks it takes the `ChunkOrIterable`/`chunk(...,false)` branch, which still returns copied bytes via `ChunkDiskMapper.Chunk()` above.

**Contrast (why persistent blocks need `pendingReaders` but head doesn't):** the on-disk block chunk reader does the opposite — it returns a chunk whose data **aliases the mmap directly, with no copy**, `tsdb/chunks/chunks.go:700-703`:
```go
chkData := sgmBytes.Range(chkDataStart, chkDataEnd)   // slice into the mmap
chkEnc := sgmBytes.Range(chkEncStart, chkEncStart+ChunkEncodingSize)[0]
chk, err := s.pool.Get(chunkenc.Encoding(chkEnc), chkData)
return chk, nil, err
```
That is exactly why `tsdb.Block` needs the `pendingReaders` WaitGroup to defer `pb.chunkr.Close()` (unmap) until all query readers are done — the block chunk bytes live in the mmap for the duration of consumption, whereas head chunk bytes are copied out.

## Q4 — Does `NewCompactingChunkSeriesMerger` / `mergeGenericQuerier` copy/re-encode chunk bytes eagerly in `Select()` or lazily during iteration?

**Conclusion:** **Lazily.** `Select()` returns a lazy series set; the merger's `At()` only wraps the underlying series in a `ChunkSeriesEntry` whose `ChunkIteratorFn` is a closure. No chunk bytes are read or re-encoded until the consumer calls `.Iterator()` on the returned `ChunkSeries`. The returned `ChunkSeriesSet` is therefore **NOT self-contained** after `Select()` returns — during iteration it still calls `s.Iterator(nil)` on the underlying block chunk series, which reads from the block chunk readers (i.e. still touches the block's mmap). This is precisely the window the `pendingReaders` barrier must cover.

Evidence:

- `mergeGenericQuerier.Select` returns a `lazyGenericSeriesSet` whose merge is deferred to first `Next()`, `storage/merge.go:118-121` (and `:146-149`):
  ```go
  return &lazyGenericSeriesSet{init: func() (genericSeriesSet, bool) {
      s := newGenericMergeSeriesSet(seriesSets, q.mergeFn)
      return s, s.Next()
  }}
  ```
- The merge at the series level (`genericMergeSeriesSet.At`) just calls `mergeFunc` on the underlying series' `At()` — it does not materialize chunk bytes, `storage/merge.go:368-377`:
  ```go
  func (c *genericMergeSeriesSet) At() Labels {
  	if len(c.currentSets) == 1 {
  		return c.currentSets[0].At()
  	}
  	series := make([]Labels, 0, len(c.currentSets))
  	for _, seriesSet := range c.currentSets {
  		series = append(series, seriesSet.At())
  	}
  	return c.mergeFunc(series...)
  }
  ```
- `NewCompactingChunkSeriesMerger`'s `mergeFunc` returns a `ChunkSeriesEntry` whose chunk iterator is a **deferred closure**, `storage/merge.go:683-701`:
  ```go
  return &ChunkSeriesEntry{
  	Lset: series[0].Labels(),
  	ChunkIteratorFn: func(chunks.Iterator) chunks.Iterator {
  		iterators := make([]chunks.Iterator, 0, len(series))
  		for _, s := range series {
  			iterators = append(iterators, s.Iterator(nil))   // :693 called only when .Iterator() runs
  		}
  		return &compactChunkIterator{
  			mergeFunc: mergeFunc,
  			iterators: iterators,
  		}
  	},
  }
  ```
  `s.Iterator(nil)` on the underlying (block) chunk series is invoked only when the consumer calls `.Iterator()` — i.e. during consumption, not during `Select()`.
- The re-encode/merge of overlapping chunks also happens lazily inside `compactChunkIterator.Next()` (`storage/merge.go:721-787`). It reads underlying chunk bytes via `iter.At()` and `next.Chunk.Bytes()` (`:756`) and only re-encodes when overlaps are detected (`:775` `NewSeriesToChunkEncoder(c.mergeFunc(...))`). In the common non-overlapping case it returns `c.curr` (`:734`) directly — a `chunks.Meta` whose `.Chunk` came straight from the underlying block chunk reader (mmap-aliased per Q3's block path). So even the merged output can carry mmap-aliasing chunk bytes when there is no overlap.

Where those underlying block chunk bytes are fetched during iteration: `populateWithDelGenericSeriesIterator.next` (`tsdb/querier.go:697`) calls `p.currMeta.Chunk, iterable, p.err = p.cr.ChunkOrIterable(p.currMeta)` (`tsdb/querier.go:721`) against the block `ChunkReader` — i.e. `chunks.go:666` `(s *Reader).ChunkOrIterable`, which aliases the mmap (Q3). This iteration runs during consumption of the merged `ChunkSeriesSet`, after `Select()` has returned and after `db.mtx` has been released — hence the correctness of the whole scheme depends on the `pendingReaders` barrier keeping the block's mmap alive until the per-query `blockChunkReader.Close()` fires.

---

### Summary of the key aliasing facts
- **Persistent block chunks:** returned bytes ALIAS the block's mmap (`tsdb/chunks/chunks.go:700-703`, no copy) → require `pb.pendingReaders` barrier in `Block.Close()` (`tsdb/block.go:383`).
- **Head mmapped chunks:** returned bytes are COPIED out of the mmap under `readPathMtx` (`tsdb/chunks/head_chunks.go:765-773`) → no per-reader mmap ref count needed; `headChunkReader.Close()` only closes append-isolation state.
- **Merger:** lazy — no eager copy/re-encode in `Select()`; underlying block readers are still consulted during `.Iterator()` consumption (`storage/merge.go:118-121, 683-701, 721-787`).

No files were modified.
