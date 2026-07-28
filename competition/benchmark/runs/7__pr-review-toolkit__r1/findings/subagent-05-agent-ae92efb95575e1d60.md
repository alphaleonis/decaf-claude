# subagent agent-ae92efb95575e1d60

I now have complete, direct-source evidence for all four concerns. Here are my findings.

---

# Silent-Failure / Error-Handling Audit — PR #13777 "Chunked remote read: close the querier earlier"

File under review: `/home/decaf/code/decaf-claude/competition/benchmark/repos/7/storage/remote/read_handler.go`

## FINDING 1 — CRITICAL: querier closed before its data is streamed → use-after-close read of mmap'd chunks (silent corruption or crash)

**Location:** `storage/remote/read_handler.go:247-251` (the `defer querier.Close()`), triggered by the call site at `storage/remote/read_handler.go:205` and the deferred read at `storage/remote/read_handler.go:210-218`.

**The exact mechanism.** `getChunkSeriesSet` (lines 242-266) opens a `ChunkQuerier`, defers `querier.Close()`, and returns the *lazy* `ChunkSeriesSet` from `querier.Select(...)` (line 265). Because the `defer` is scoped to `getChunkSeriesSet`, **`querier.Close()` executes the moment that function returns** — i.e. before the caller ever touches the series set. The caller then hands `chunks` to `StreamChunkedReadResponses` (line 210), which is where the series set is actually iterated and where chunk *bytes* are read (`codec.go:235-296`, byte read at `codec.go:261` `chk.Chunk.Bytes()`).

The returned set reads lazily from resources the closed querier owned:
- `chunkSeriesEntry` holds the block's `ChunkReader` (`tsdb/querier.go:1173-1180`); its iterator loads bytes on demand via `cr.ChunkOrIterable()` (`tsdb/querier.go:773-780`).
- The merge path returns a `lazyGenericSeriesSet` whose `init` (which drives the child `.Next()` index reads) doesn't even run until the first `Next()` during streaming (`storage/lazy.go:20-34`, `storage/merge.go:118-121`).

**What Close() actually releases** — this is the load-bearing part:
- Persistent blocks: `blockChunkReader.Close()` / `blockIndexReader.Close()` only call `pendingReaders.Done()` (`tsdb/block.go:536-539`, `567-570`). They do **not** unmap. The mmap is released by `Block.Close()`, which first blocks on `pb.pendingReaders.Wait()` and then calls `pb.chunkr.Close()` (`tsdb/block.go:378-390`). Retention/compaction reaches this via `deleteBlocks`, whose own comment says it closes the block because it "might need to wait for pending readers to complete" before deleting the files (`tsdb/db.go:1656-1659`).
- Head: `headChunkReader.Close()` calls `isoState.Close()` (`tsdb/head_read.go:318-323`), which removes this reader from the open-reads list (`tsdb/isolation.go:36-41`). Head truncation spins in `WaitForPendingReadersInTimeRange` until no open read overlaps the range (`tsdb/head.go:1141-1158`), called from `truncateMemory` (`tsdb/head.go:1093-1117`); once the reader is gone, truncation unmaps/deletes the head chunk files that streaming is still reading.

So the querier's open-reader registration is precisely the guard that keeps the mmap'd index/chunk data alive. Closing it early (before streaming) removes that guard while the bytes are still being read.

**Concrete triggering scenario.** A client issues a `STREAMED_XOR_CHUNKS` remote-read for a wide time range / large series set, so streaming takes a non-trivial time. During that streaming window, either (a) head truncation fires (head block cut, ~every 2h by default, or admin/compaction), or (b) retention/compaction deletes an overlapping block via `reloadBlocks`→`deleteBlocks`. Because the querier was already closed at line 205, `WaitForPendingReadersInTimeRange` / `pendingReaders.Wait()` no longer see this reader and proceed to unmap/delete the files. `StreamChunkedReadResponses` then reads the unmapped/recycled region.

**Silent-failure angle (why this is the worst kind).** [Inference — depends on OS mmap timing I cannot execute here] Two runtime manifestations:
- If the region is fully unmapped, the read faults → SIGBUS/SIGSEGV crashes the whole Prometheus process. Loud, but a remote-read client can crash the server.
- If the underlying file was released and the address recycled (head chunk sequence files are deleted and new ones created), the still-mapped-looking bytes are stale/garbage. Those get marshaled into `prompb.Chunk{Data: chk.Chunk.Bytes()}` (`codec.go:257-262`) and streamed to the client **with no error anywhere** — `iter.Err()` (codec.go:292) and `ss.Err()` (codec.go:296) have no way to detect that the bytes they returned came from freed memory. This is silent data corruption delivered to the remote-read consumer.

**Confirmed as a regression by this PR.** The diff moved `defer querier.Close()` out of the per-query streaming closure (where it ran *after* `StreamChunkedReadResponses` returned) into `getChunkSeriesSet` (where it runs *before* streaming). Old ordering kept the querier open for the whole stream; the new ordering does not. This is not a pre-existing issue — it is introduced here. Note the doc comment on `getChunkSeriesSet` ("ensure timely release of the querier resources") states the intent that is exactly the defect.

**Fix.** The querier must outlive the streaming of its series set. Do not close it inside a helper that returns before streaming. Options:
- Simplest correct fix: revert to closing the querier after `StreamChunkedReadResponses` completes — keep querier creation, `Select`, streaming, and `defer querier.Close()` in the same scope (the per-query closure), as it was before this PR.
- If the goal of "close earlier" is to release the querier before the *next* loop iteration (rather than during streaming), that is what the pre-PR per-iteration `defer` inside the closure already achieved — the closure runs once per query, so Close already happened between queries. So the PR's stated benefit does not require reading after Close.

I recommend confirming whether this was later reverted/fixed upstream before shipping; the code as merged in this checkout has the defect.

---

## Concern 1 — Early `chunks.Err()` check vs. lazily-produced errors: SAFE (no silent miss)

`chunks.Err()` at `read_handler.go:206` runs before iteration. On the lazy merge path, `lazyGenericSeriesSet.Err()` returns `nil` until the set is initialized (`storage/lazy.go:36-41`), so the early check is effectively a no-op there and catches only construction-time errors — e.g. `ChunkQuerier()` failing returns `storage.ErrChunkSeriesSet(err)` whose `Err()` is immediately populated (`storage/interface.go:392-404`; `read_handler.go:243-245`), or the single-querier `PostingsForMatchers` failure (`tsdb/querier.go:185-188`).

Crucially, lazily-produced errors are **not** dropped: `StreamChunkedReadResponses` surfaces iterator errors mid-stream (`codec.go:292-294`) and returns `ss.Err()` after iterating (`codec.go:296`), and the caller propagates that to `http.Error` (`read_handler.go:219-234`). So every error path is surfaced either at line 206 or by the streamer. No silent failure here; the early check is redundant-but-harmless, not a regression.

## Concern 2 — Close() error logged at Warn, not returned: NOT a regression (pre-existing, minor)

`getChunkSeriesSet` logs the querier `Close()` error at Warn and does not propagate it (`read_handler.go:247-251`). This matches the pre-existing non-streamed path (`remoteReadSamples`, `read_handler.go:141-145`) and the old chunked code (identical block in the diff). A `Close()` error (e.g. a chunk/index/tombstone reader close failure) is therefore never reflected in the HTTP response and the stream is still reported as success — but this behavior is unchanged by this PR. Low priority; flagging only for completeness, not as a regression.

## Concern 3 — `ws` warnings logged, not returned to client: SAFE (pre-existing, no channel exists)

Warnings from `StreamChunkedReadResponses` are logged at Warn and not sent to the client (`read_handler.go:223-225`). This is identical to the pre-PR code (unchanged in the diff), and the chunked wire format (`prompb.ChunkedReadResponse`) has no warnings field to carry them. No regression.

---

## Bottom line

Concerns 1, 2, and 3 are clean or pre-existing. **Concern 4 is real and is the headline: this PR introduces a use-after-close read of mmap'd index/chunk data by closing the querier before the series set is streamed.** The code-level defect (reads occur after the guarding querier is closed; that querier is the only thing holding the mmap against truncation/deletion) is directly verified from source across `read_handler.go`, `codec.go`, `tsdb/querier.go`, `tsdb/block.go`, `tsdb/head_read.go`, `tsdb/head.go`, `tsdb/isolation.go`, and `tsdb/db.go`. The exact runtime manifestation (crash vs. silently corrupt chunk bytes) under a concurrent truncation/compaction is [Inference] since I could not execute the race, but the silent-corruption path is plausible and requires no client-visible error. Recommend reverting the early-close (keep `Close` in the same scope as, and after, `StreamChunkedReadResponses`).

Relevant files:
- `/home/decaf/code/decaf-claude/competition/benchmark/repos/7/storage/remote/read_handler.go`
- `/home/decaf/code/decaf-claude/competition/benchmark/repos/7/storage/remote/codec.go`
- `/home/decaf/code/decaf-claude/competition/benchmark/repos/7/tsdb/querier.go`
- `/home/decaf/code/decaf-claude/competition/benchmark/repos/7/tsdb/block.go`
- `/home/decaf/code/decaf-claude/competition/benchmark/repos/7/tsdb/head_read.go`
- `/home/decaf/code/decaf-claude/competition/benchmark/repos/7/tsdb/head.go`
- `/home/decaf/code/decaf-claude/competition/benchmark/repos/7/tsdb/isolation.go`
- `/home/decaf/code/decaf-claude/competition/benchmark/repos/7/tsdb/db.go`
- `/home/decaf/code/decaf-claude/competition/benchmark/repos/7/storage/lazy.go`
- `/home/decaf/code/decaf-claude/competition/benchmark/repos/7/storage/merge.go`
