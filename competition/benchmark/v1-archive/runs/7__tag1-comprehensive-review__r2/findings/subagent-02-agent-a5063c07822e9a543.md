# subagent agent-a5063c07822e9a543

I have complete, code-grounded evidence. Here is my analysis.

## Security Analysis

### Languages Detected
Go

### Findings

#### High

- **[availability / use-after-close]** The querier that owns the memory-mapped chunk data is closed *before* the returned `ChunkSeriesSet` is iterated and its chunk bytes are streamed — a use-after-munmap that can crash the whole Prometheus process. — `storage/remote/read_handler.go:205` (with `defer querier.Close()` at `read_handler.go:247-251` and `querier.Select(...)` returned at `read_handler.go:265`)

  - **Attack vector**: A remote-read client sends a normal, well-formed chunked request (`STREAMED_XOR_CHUNKS`). `getChunkSeriesSet` opens a `ChunkQuerier`, defers `querier.Close()`, and returns the *lazy* `ChunkSeriesSet` from `querier.Select(...)`. The deferred `Close()` fires the instant `getChunkSeriesSet` returns. Only afterward does `StreamChunkedReadResponses` (`storage/remote/codec.go:221`) iterate the set and read `chk.Chunk.Bytes()` — the raw chunk bytes.

    I verified the data flow end-to-end in this tree:
    - `blockChunkQuerier.Select` (`tsdb/querier.go:174-195`) returns `NewBlockChunkSeriesSet(...)`, a lazy set holding a reference to `q.chunks`; it does **not** materialize chunk data.
    - `blockBaseQuerier.Close` (`tsdb/querier.go:103-115`) calls `q.chunks.Close()`.
    - For persistent blocks, `blockChunkReader.Close()` calls `pb.pendingReaders.Done()` (`tsdb/block.go:567-568`), and `Block.Close()` gates unmapping on `pb.pendingReaders.Wait()` (`tsdb/block.go:383`). While the querier is open the block is pinned and its mmap stays valid; once the querier closes, a concurrent compaction/block deletion can unmap the block's chunk files.
    - For the head, `ChunkDiskMapper.Chunk` returns a slice into the mmap (`mmapFile.byteSlice.Range(...)`, `tsdb/chunks/head_chunks.go:764-765`) and explicitly warns (lines 673-676) that its read lock only covers the `Chunk()` call — "if Close() is called, the data in the byte slice will get corrupted as the mmapped file will be closed." The returned view escapes into the streamer, and head-chunk truncation can munmap it.

    `chk.Chunk.Bytes()` is a zero-copy view into that mmap (no copy is made along the chunked path — that is the point of streamed chunked read). Reading it after the backing file is unmapped is a SIGBUS/SIGSEGV against unmapped pages, which Go treats as a fatal, unrecoverable runtime error (`recover()` cannot catch it) — the entire Prometheus process crashes.

  - **Impact**: Remotely-triggerable hard crash (availability/DoS) of the Prometheus server. [Inference] Relative to the OOM the PR targets, this trades a bounded-memory improvement for a memory-safety hazard: instead of a possible OOM on a broken/slow stream, a race with normal compaction/head-truncation during streaming can SIGBUS the process. The exposure window is the full streaming duration of the response — precisely the large/slow responses the PR is concerned about, which widens the race window.

  - **Confidence**: 80/100. The lazy-iterate-after-close data flow and the mmap-view semantics are confirmed directly from code in this tree (certain). The uncertainty is in triggering reliability: the crash requires a compaction or head-chunk truncation to complete in the window between `Close()` and the chunk read. An attacker cannot deterministically schedule compaction, but long/large streams and repeated requests materially raise the odds; this is a genuine correctness regression rather than a purely theoretical one. [Unverified] I did not re-confirm that no queryable implementation on the server wiring copies chunk bytes before returning; the standard TSDB path does not.

  - **Remediation**: Keep the `ChunkQuerier` alive until iteration completes. Do not `defer querier.Close()` inside a helper that returns the lazy `ChunkSeriesSet`. Either (a) revert to closing the querier in the outer loop-body closure so `Close()` runs only after `StreamChunkedReadResponses` returns (the pre-PR structure at `read_handler.go` before commit `53091126c2`), or (b) have the helper return both the querier and the set and defer `querier.Close()` in the caller after streaming, or (c) if early release is required for the OOM goal, copy chunk bytes out of the mmap before the querier closes (defeats zero-copy streaming). Option (a)/(b) preserves the resource-lifetime invariant that TSDB relies on (`pendingReaders` pinning and the `readPathMtx` read-lock contract).

### Assessment of the secondary angle (inputs / error disclosure / limits)
No security-relevant change. The matchers, hints, and time range passed to the querier are identical to before. Error handling is preserved: `chunks.Err()` surfaces the same open/select errors, `storage.ErrChunkSeriesSet(err)` wraps the `ChunkQuerier` open failure equivalently, and the `errors.As(err, &httpErr)` disclosure path is unchanged. The concurrency gate (`remoteReadGate`) and `remoteReadMaxBytesInFrame` are untouched. No new input reaches the querier and no new error content is disclosed.

### Positive Observations
- The pre-existing error-wrapping via `storage.ErrChunkSeriesSet` correctly propagates querier-open failures through the `ChunkSeriesSet.Err()` contract, so the refactor does not swallow errors.
- No secrets, injection surface, or auth changes are introduced by this diff.

No low-severity best-practice observations to omit.

```json-findings
[{"severity":"High","confidence":80,"category":"edge-case","source":"security-reviewer","agent":"security-reviewer","file":"storage/remote/read_handler.go","line":205,"finding":"getChunkSeriesSet closes the ChunkQuerier (defer querier.Close() at lines 247-251) before the lazy ChunkSeriesSet it returns is iterated. StreamChunkedReadResponses then reads chk.Chunk.Bytes(), which are zero-copy views into the querier's memory-mapped chunk files (blockChunkQuerier.Select returns a lazy NewBlockChunkSeriesSet; blockBaseQuerier.Close calls q.chunks.Close()). Closing the querier releases the block pendingReaders pin (tsdb/block.go:383,567) and the head ChunkDiskMapper read-path guarantee (tsdb/chunks/head_chunks.go:673-676), allowing a concurrent compaction/head-truncation to munmap the backing pages. Reading them during streaming is a SIGBUS/SIGSEGV that fatally crashes the Prometheus process (recover cannot catch it). Remotely triggerable via a normal chunked remote-read request; the pre-PR code kept the querier open across StreamChunkedReadResponses, so this is a regression.","remediation":"Do not close the querier inside a helper that returns the lazy ChunkSeriesSet. Close it only after StreamChunkedReadResponses returns (revert to the pre-53091126c2 loop-body defer, or return the querier alongside the set and defer Close in the caller). If early release is required, copy chunk bytes out of the mmap before closing."}]
```
