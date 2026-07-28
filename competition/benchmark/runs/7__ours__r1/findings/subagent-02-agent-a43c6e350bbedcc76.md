# subagent agent-a43c6e350bbedcc76

I have everything I need. Let me confirm the system model before writing up.

## System Model

**Boundary/contract under review:** `storage.ChunkQuerier.Select()` returns a `storage.ChunkSeriesSet`. The implicit-but-load-bearing lifetime contract is that the returned set may only be iterated **while its parent `ChunkQuerier` is still open**.

**Data flow (verified end-to-end):**
1. `getChunkSeriesSet` (read_handler.go:242) opens a `ChunkQuerier`, calls `Select`, then closes the querier via `defer` on **helper return**.
2. `blockChunkQuerier.Select` (tsdb/querier.go:174) returns a **lazy** `blockChunkSeriesSet` holding the block's `IndexReader` and `ChunkReader`.
3. `StreamChunkedReadResponses` (codec.go:235-296) iterates that set: `ss.Next()` reads the index (`b.index.Series`), and `iter.At().Chunk.Bytes()` reads chunk bytes **lazily** via `populateWithDelChunkSeriesIterator.next()` → `cr.ChunkOrIterable()` (tsdb/querier.go:721) — i.e. from the memory-mapped block file.
4. This iteration happens **after** `getChunkSeriesSet` returned, i.e. **after** `querier.Close()`.

**Concurrency mechanism (the safety net that is defeated):** `Block.Chunks()`/`Block.Index()` call `pb.startRead()` → `pendingReaders.Add(1)` (tsdb/block.go:423). The querier's `Close()` decrements it (`blockChunkReader.Close` → `pendingReaders.Done()`, block.go:568). `Block.Close()` — invoked by background compaction/retention/`reloadBlocks` — does `pendingReaders.Wait()` **before** `pb.chunkr.Close()` unmaps the files (block.go:378-389). Closing the querier early removes the only thing holding that `Wait()` back while the set is still being read.

**Pre-PR behavior (verified via `git diff 1580922 5309112`):** `defer querier.Close()` lived inside the same per-query closure as the `StreamChunkedReadResponses` call, so Close ran *after* streaming finished. The non-streamed path (`remoteReadSamples`, read_handler.go:161) still follows this correct pattern — it fully materializes via `ToQueryResult` before the deferred Close.

Here is my report.

```json
[
  {
    "file": "storage/remote/read_handler.go",
    "line": 242,
    "severity": "Critical",
    "category": "design",
    "issue": "[CONCURRENCY_DESIGN] getChunkSeriesSet closes the ChunkQuerier before the returned ChunkSeriesSet is iterated, violating the querier/series-set lifetime contract. The helper opens a ChunkQuerier, calls Select (which returns a LAZY set), and runs `defer querier.Close()` on helper return. The caller (remoteReadStreamedXORChunks -> StreamChunkedReadResponses) only iterates the set AFTER the helper returns. For the TSDB-backed queryable this queryable actually wires to (web/api/v1/api.go:277 -> fanout -> db.ChunkQuerier -> NewMergeChunkQuerier over blockChunkQuerier), iteration reads index entries (blockBaseSeriesSet.Next -> b.index.Series) and chunk bytes (populateWithDelChunkSeriesIterator.next -> cr.ChunkOrIterable -> mmapped block file, surfaced by StreamChunkedReadResponses via chk.Chunk.Bytes()) LAZILY during streaming. querier.Close() calls blockBaseQuerier.Close -> blockChunkReader.Close -> Block.pendingReaders.Done(). That pendingReaders WaitGroup is exactly the mechanism that keeps the block's mmapped files alive: Block.Close() (compaction / retention / reloadBlocks) does pendingReaders.Wait() before pb.chunkr.Close() unmaps the files. By closing the querier before iteration, the handler drops that protection while still holding references it will dereference during the (potentially long) streaming window.",
    "fix": "Do not surface the querier's lifetime as a bare ChunkSeriesSet whose validity outlives its owner. Keep the querier open until streaming completes: either inline the Select back into the same closure as StreamChunkedReadResponses with `defer querier.Close()` (the pre-PR structure), or have getChunkSeriesSet return both the querier and the set (or a closer) so the caller can `defer querier.Close()` AFTER StreamChunkedReadResponses returns. If the intent is to bound resource usage for broken/slow requests, achieve it with request context cancellation/timeouts rather than releasing the reader ownership early.",
    "confidence": 75,
    "pre_existing": false
  }
]
```

## Considered But Not Flagged

- **Error surfacing via `chunks.Err()` vs. the previous explicit `ChunkQuerier`/`Select` error return** (read_handler.go:206). This is behavior-equivalent and arguably an improvement: a `ChunkQuerier()` construction error is now wrapped as `storage.ErrChunkSeriesSet(err)` and unwrapped by `chunks.Err()`; a `Select`-time error (e.g. `PostingsForMatchers` failure returning `storage.ErrChunkSeriesSet`) is now caught *before* streaming instead of surfacing mid-stream. Note one interaction: for a lazy merge set (`lazyGenericSeriesSet`), `chunks.Err()` may trigger init and thus index reads — but those already happen post-`Close()`, so this does not add a *new* hazard beyond the flagged finding. Sound on its own; dismissed.

- **Non-streamed path `remoteReadSamples`** (read_handler.go:117-187). Unchanged by this PR and correct: `ToQueryResult(querier.Select(...))` fully materializes samples into `prompb.QueryResult` before the deferred `querier.Close()` runs within the same closure. It is the reference pattern the streamed path deviated from. Not a finding.

- **Head-querier variant of the same hazard.** For in-order/OOO head queriers (`db.blockChunkQuerierForRange` -> `NewBlockChunkQuerier(RangeHead)`), `headChunkReader.Close()` releases the `isolationState` (`isoState.Close()`, tsdb/isolation.go:36, just unlinks from the reads list — no nil-out, so no immediate nil deref). The same "iterate after Close" shape applies, and reading proceeds against a released isolation state (advancing the low watermark mid-read). I could not, from the diff and surrounding code alone, prove a definite crash/corruption mechanism for the head (head mmap truncation gating is more indirect than the block `pendingReaders.Wait()`), so I fold it into the primary finding as corroboration rather than raising it as a separate Critical claim. Anchor ~50 on its own; not separately flagged.

## Probe Requests

I did not run these (read-only mandate); nominating for the author/maintainer to confirm the runtime consequence:

1. A stress/integration test that issues a `STREAMED_XOR_CHUNKS` remote read spanning at least one persistent block, then concurrently triggers block deletion/compaction (`db.reloadBlocks` / retention) so that `Block.Close()` -> `pendingReaders.Wait()` races with the streaming iteration. Expected without the fix: SIGSEGV/SIGBUS on `chk.Chunk.Bytes()` reading an unmapped region, or corrupt chunk bytes in the response.
2. Run the remote-read handler tests under `-race` with a mock `SampleAndChunkQueryable` whose `ChunkQuerier.Close()` marks the reader closed and whose `ChunkSeriesSet` iteration asserts the querier is still open — this makes the contract violation deterministic without needing the compaction race.

### Summary for the parent agent

One Critical design defect in `/home/decaf/code/decaf-claude/competition/benchmark/repos/7/storage/remote/read_handler.go` (the new `getChunkSeriesSet`, lines 242-266, and its call site at lines 205-208): it closes the `ChunkQuerier` before the returned lazy `ChunkSeriesSet` is iterated by `StreamChunkedReadResponses`. Because TSDB chunk data is read lazily from memory-mapped block files during iteration, and the querier's `Close()` releases the `Block.pendingReaders` guard that keeps those files mapped, a concurrent block compaction/retention during the streaming window can unmap the files and cause a segfault or corrupt response — a worse failure mode than the OOM the PR set out to prevent. Confidence 75 (contract violation is certain from the code; the crash requires a concurrent block deletion, which is realistic under the exact slow/large-read conditions the PR targets). Supporting evidence spans `tsdb/block.go` (`pendingReaders`), `tsdb/querier.go` (lazy `ChunkOrIterable`), and `storage/remote/codec.go` (`StreamChunkedReadResponses` reading `Chunk.Bytes()` during iteration). The pre-PR code and the sibling non-streamed `remoteReadSamples` path both honor the lifetime contract; this change is the sole regression.
