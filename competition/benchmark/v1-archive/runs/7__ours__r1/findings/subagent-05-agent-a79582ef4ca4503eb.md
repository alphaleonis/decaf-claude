# subagent agent-a79582ef4ca4503eb

Everything is confirmed mechanically. Depth stated below.

---

## Depth: deep — external-API streaming endpoint (remote read) touched; traced multi-step use-after-close cascades end-to-end across `storage/remote` → `storage/merge` → `tsdb` block + head chunk readers and the compaction/retention/truncation GC paths.

The change wraps querier creation + `Select` in `getChunkSeriesSet`, whose `defer querier.Close()` fires when the helper **returns** — before `StreamChunkedReadResponses` iterates the returned lazy `ChunkSeriesSet`. I confirmed the series set is fully lazy: `iter.Next()` → `populateWithDelChunkSeriesIterator.next()` → `p.cr.ChunkOrIterable()` reads chunk bytes during streaming (`storage/remote/codec.go:250-266`, `chk.Chunk.Bytes()` at line 261), i.e. **after** `Close()`. The querier's `Close()` is exactly the reader-liveness signal the storage layer relies on to keep chunk memory valid.

```json
[
  {
    "file": "storage/remote/read_handler.go",
    "line": 247,
    "severity": "Critical",
    "category": "resource-management",
    "issue": "[ADV_CASCADE] getChunkSeriesSet defers blockChunkReader.Close() (pendingReaders.Done) and returns a lazy set → StreamChunkedReadResponses later reads zero-copy mmap chunk bytes; concurrent compaction/retention runs Block.Close()→pendingReaders.Wait()(now 0)→chunkr munmap+file removal → streaming reads unmapped memory → SIGSEGV process crash, or garbage/corrupt XOR chunks streamed to the remote-read client.",
    "fix": "Do not close the ChunkQuerier before StreamChunkedReadResponses finishes iterating. Revert to closing after streaming (defer in the caller across the full stream), or fully materialize/copy chunks before Close. If the goal is only to release the head isolation state early, release that specifically rather than the whole reader.",
    "confidence": 75,
    "pre_existing": false
  },
  {
    "file": "storage/remote/read_handler.go",
    "line": 247,
    "severity": "High",
    "category": "async",
    "issue": "[ADV_CASCADE] early Close() → headChunkReader.Close()→isoState.Close() removes the read from iso.readsOpen → Head.Truncate's WaitForPendingReadersInTimeRange no longer waits for the in-flight stream → chunkDiskMapper.Truncate deletes a mmapped segment the stream still needs → ChunkDiskMapper.Chunk returns *CorruptionErr → head_read.go:426 panic mid-stream → aborted request and possible corruption-handling side effects; the truncation-vs-reader coordination (isolation.go:142-143) is defeated.",
    "fix": "Keep the head querier (and its isolationState registration) open until StreamChunkedReadResponses completes, so WaitForPendingReadersInTimeRange continues to gate head truncation for the streamed range.",
    "confidence": 50,
    "pre_existing": false
  }
]
```

### Why the block path (Finding 1) is Critical and reproducible
- `Reader.ChunkOrIterable` (`tsdb/chunks/chunks.go:700-702`) wraps the mmap segment slice with `pool.Get` (`chunkenc/xor.go:66`, `chunk.go:373` — `stream: d`, **no copy**). `chk.Bytes()` is a live view into the mmap.
- `blockChunkReader.Close()` (`tsdb/block.go:567`) only does `pendingReaders.Done()`; the mmap is unmapped later by `Block.Close()`→`pb.chunkr.Close()` (`block.go:386`), and `pendingReaders.Wait()` (`block.go:383`) is the **only** guard.
- `deleteBlocks` (`db.go:1662`) calls `Block.Close()` then renames+`os.RemoveAll`. It runs from `reloadBlocks` after every compaction (compacted parents become deletable) and from retention. A remote read overlapping a just-compacted or retention-eligible block races it.
- Before this PR, `Close()` ran after streaming, so `pendingReaders` stayed >0 and `Block.Close()` blocked until the stream finished. The PR removes precisely that protection.
- **Abuse amplifier (ADV_ABUSE):** the stalled/slow client this PR targets is the exact input that widens the race window — a stream held open for minutes maximizes the chance a compaction/retention deletes the block mid-iteration. The fix makes its own target scenario more dangerous, not safer.

Dual-path check (Finding 1): forward — Select→Close(pendingReaders 0)→compaction deletes block→munmap→streamed read faults. Backward — for the fault, the byte slice must be mmap-backed (confirmed zero-copy), Close must have dropped the last reader ref (confirmed), and deletion must be ungated except by pendingReaders (confirmed). Paths agree.

### Abuse-case / OOM verdict (the PR's stated intent)
The PR aims to avoid OOMs from broken/stalled chunked reads. Assessment: for **persistent blocks** the querier holds only shared mmap references (cheap, not per-query heap), so closing early frees little memory — it mostly moves resource release ahead of the point the resource is still needed, introducing the use-after-free above. For the **head**, holding the querier keeps `isolationState`/`readsOpen` registered, which legitimately blocks head truncation and can grow head memory during a long stall — so there is a real OOM lever here, but the change releases the *entire* reader (defeating truncation's reader-wait and mmap-lifetime guarantees) rather than just the isolation watermark. Net: it trades a bounded, recoverable OOM risk for an unbounded-consequence use-after-free / crash / corrupt-data-served risk.

### Probe Requests
- **Test file+name:** `storage/remote/read_handler_test.go` → `TestGetChunkSeriesSet_UseAfterClose`.
- **Deterministic probe (no timing race):** inject a fake `storage.ChunkQuerier` whose `Select` returns a `ChunkSeriesSet` backed by a buffer, and whose `Close()` overwrites/poisons that buffer (simulating munmap). Drive the real path (`remoteReadStreamedXORChunks` → `getChunkSeriesSet` → `StreamChunkedReadResponses`) with a slow/segmented writer; assert the streamed chunk bytes equal the pre-close bytes. **Expected failure with current code:** streamed bytes reflect the poisoned buffer (or panic), because `Close()` ran before iteration.
- **Integration probe (demonstrates the real cascade):** tsdb-backed `SampleAndChunkQueryable`; start a chunked read over a persistent block, block the HTTP writer mid-stream, then trigger `db.reloadBlocks()`/`deleteBlocks` (or `head.Truncate`) for the overlapping block; assert no panic/segfault and byte-correct chunks. **Expected failure with early Close:** segfault (block path) or `CorruptionErr` panic (head path).
- **Exact production line(s) implicated:** `storage/remote/read_handler.go:247-251` (the `defer querier.Close()` inside `getChunkSeriesSet`) firing at line 265's return, ahead of `StreamChunkedReadResponses` at `read_handler.go:210`. Do not run — nominated only.

## Considered But Not Flagged
- **Head mmapped-chunk torn read (silent corruption):** `ChunkDiskMapper.Chunk` copies chunk data (`head_chunks.go:767-771`) and serializes with truncation via `readPathMtx` (`Chunk` RLock vs `deleteFiles` Lock, `head_chunks.go:968`). So the head path degrades to a `CorruptionErr`→panic (Finding 2), not a silent torn read. Step that failed: the defensive copy + lock prevents reading unmapped bytes once past the map lookup. (The persistent block `Reader` has no such copy — hence Finding 1 stands.)
- **Open head chunk race:** the currently-appended head chunk is copied via `ChunkWithCopy`/`copyHeadChunk=true` (`querier.go:717`, `head_read.go:371-382`). Safe. Step that failed: the open chunk is materialized before Close matters.
- **remoteReadSamples path:** unchanged and safe — `ToQueryResult` fully materializes results into protobuf before the deferred `Close()` (non-lazy). Not affected by this change.
- **fanout/secondary remote-of-remote wiring:** for the default local-tsdb primary, the merge/compacting merger still reads block chunks lazily during iteration, so it inherits Finding 1 rather than mitigating it; no additional distinct scenario. Not separately flagged.
