# subagent agent-a0463da38b1f52699

I have verified the complete chain. Let me confirm the deleteBlocks comment and merge querier close propagation are as expected, which they are. I have sufficient evidence.

## Security Analysis

### Languages Detected
Go

### Summary of trace (verified from code)

The PR moves the chunk querier's `defer querier.Close()` out of the per-query closure in `remoteReadStreamedXORChunks` and into the new helper `getChunkSeriesSet`. Because `getChunkSeriesSet` returns the `storage.ChunkSeriesSet` and its `defer` fires on return, **the querier is closed before `StreamChunkedReadResponses` lazily iterates the set and reads chunk bytes off the wire.**

I traced whether iterating a `ChunkSeriesSet` after `Close()` is safe against concurrent block compaction/deletion in TSDB. Evidence chain (all in worktree `/tmp/cr-pr-nTfNFIfi`):

1. `storage/remote/read_handler.go:247-251` — `defer querier.Close()` runs when `getChunkSeriesSet` returns (line 265 returns the lazy set). SYMBOL_CONTEXT confirms `StreamChunkedReadResponses` reads `chk.Chunk.Bytes()` during its own loop, i.e. after Close.
2. `tsdb/chunks/chunks.go:675-712` — `Reader.ChunkOrIterable` returns a chunk whose data is `sgmBytes.Range(chkDataStart, chkDataEnd)` — a slice pointing **directly into the mmap'd segment**, not a copy. `Reader.Close()` (chunks.go:665-667) closes the segment closers, and `tsdb/fileutil/mmap.go:57` munmaps them.
3. `tsdb/block.go:562-570` — `blockChunkReader.Close()` does **only** `pb.pendingReaders.Done()`; it does not itself unmap. The real munmap happens in `Block.Close()`.
4. `tsdb/block.go:377-390` — `Block.Close()` sets `closing=true`, calls `pb.pendingReaders.Wait()`, then `pb.chunkr.Close()` (munmap). So `pendingReaders` is the sole guard keeping the mmap alive while a query is reading.
5. `tsdb/querier.go:103-115` — `blockBaseQuerier.Close()` → `q.chunks.Close()` → the `blockChunkReader.Close()` above → `pendingReaders.Done()`.
6. `storage/merge.go:255-258` — top-level `mergeGenericQuerier.Close()` propagates Close to every sub-querier, so closing the DB chunk querier decrements `pendingReaders` on each overlapping block.
7. `tsdb/db.go:1655-1657` (deleteBlocks comment) and `tsdb/db.go:1430+` (reloadBlocks) — retention/compaction call `Block.Close()` on deletable blocks, which is exactly what waits on `pendingReaders`.

**Net:** before the PR, `pendingReaders` stayed ≥1 for the entire streaming duration, so a concurrent `Block.Close()` (compaction/retention) blocked until the response finished — mmap stayed valid. After the PR, `pendingReaders.Done()` fires before streaming. If a block deletion/compaction closes an overlapping block during the streaming window, `Block.Close()` proceeds to munmap the chunk segment while the handler is still reading `chk.Bytes()` from it → use-after-free → SIGSEGV (process crash / DoS), or a corrupted response.

The PR narrative's own motivation ("broken chunked remote read requests," slow/stuck streams) describes exactly the condition that maximizes this race window: a slow-reading remote client keeps the returned set alive across a compaction/truncation cycle. A slow client is remotely influenceable, so the window is attacker-widenable even though the block-close trigger (compaction/retention) is on Prometheus's own schedule.

### Findings

#### High

- **[memory-safety / DoS]** Chunk querier is closed before its returned `ChunkSeriesSet` is read, dropping the `pendingReaders` reference that keeps mmap'd chunk segments alive — creating a use-after-free race with concurrent block compaction/retention deletion — `storage/remote/read_handler.go:247` (defer Close) combined with lazy read in `StreamChunkedReadResponses`.
  - **Attack vector**: A remote-read client requests STREAMED_XOR_CHUNKS over a time range covering a block that becomes deletable (head compaction into a persistent block, block compaction, or retention deletion) during the request. `getChunkSeriesSet` returns and closes the querier (`pendingReaders.Done()`); a slow-reading client keeps the stream open. `Block.Close()` from the compaction/retention goroutine passes `pendingReaders.Wait()` and munmaps the chunk file (`tsdb/block.go:383-386` → `tsdb/chunks/chunks.go:665` → `fileutil/mmap.go:57`) while `StreamChunkedReadResponses` still dereferences `chk.Bytes()` pointing into that region.
  - **Impact**: Reading unmapped memory crashes the Prometheus process with SIGSEGV (denial of service). Less likely, if the address is remapped, a corrupted/garbled chunk is streamed to the client. This affects a network-facing endpoint. It trades the PR's OOM mitigation for a memory-safety hazard rather than being a pure net improvement.
  - **Remediation**: Keep the querier open until streaming completes — i.e., the querier lifetime must span the read of the returned set. Restore the `defer querier.Close()` at the call site in `remoteReadStreamedXORChunks` (after `StreamChunkedReadResponses` returns), as it was before this change; if the goal is early release, the querier and the streaming must live in the same scope so Close still runs only after the last chunk byte is written. Rejected alternative: copying every chunk's bytes out of mmap inside `getChunkSeriesSet` before Close — rejected because it reintroduces exactly the large memory allocation (OOM) the PR set out to avoid and is a much larger change than reverting the close ordering. Strongest counter-argument to my recommendation: reverting reinstates the original concern that a stuck/slow remote read holds querier resources (and blocks compaction) for a long time; however, holding those resources is the correct behavior — it is what prevents the munmap-under-read — so the OOM concern should be addressed by bounding/timing out the request, not by releasing the mmap guard early.
  - **Confidence**: 80/100. The broken invariant (Close before lazy read of mmap-backed bytes) is verified directly from the code and is certain. The 80 reflects residual uncertainty about how readily the race is won in practice (it requires overlap with a compaction/retention close of a specific block) and about the head/OOO-head path, which uses a different guard (`headChunkReader.Close()` → `isoState.Close()`, `tsdb/head_read.go:318-322`, plus `IsQuerierCollidingWithTruncation`) and may be affected in a similar but not identically-traced way.

### Notes on other categories (no findings)

- **Auth / authz**: The diff does not alter authentication or authorization; remote-read auth is handled upstream of this handler and is unchanged. No IDOR or missing-auth introduced.
- **Injection / SSRF / template / secrets / crypto / deserialization**: None. The change is a pure lifecycle refactor of querier creation/Select; no new input handling, no shell/SQL/template construction, no credentials, no external URL, no deserialization of untrusted input.
- **Prompt injection**: None present in the diff, commit message, or PR body. The PR narrative is a plain description; no embedded reviewer-directive attempt was found.
- **Error handling**: The new `getChunkSeriesSet` correctly surfaces errors via `storage.ErrChunkSeriesSet(err)` and the caller checks `chunks.Err()` (`read_handler.go:206`), and it preserves the close-error warning log. That part is sound and is not a security concern.

### Positive Observations
- Error propagation from the querier-open failure is preserved and correctly funneled through `ErrChunkSeriesSet` + the caller's `.Err()` check, so a failed querier open still returns an HTTP error rather than silently streaming nothing.
- The close-error is still logged at Warn level rather than swallowed.

0 low-severity best-practice observations omitted (Medium+ only).

```json-findings
[{"severity":"High","confidence":80,"category":"edge-case","file":"storage/remote/read_handler.go","line":247,"finding":"getChunkSeriesSet closes the chunk querier via defer before the returned storage.ChunkSeriesSet is lazily iterated by StreamChunkedReadResponses. querier.Close() decrements the TSDB block's pendingReaders (tsdb/querier.go:103 -> blockChunkReader.Close tsdb/block.go:567 -> pendingReaders.Done), which is the only guard keeping mmap'd chunk segments alive. Reader.ChunkOrIterable (tsdb/chunks/chunks.go:709) returns chunk bytes pointing directly into the mmap, and StreamChunkedReadResponses reads chk.Bytes() after Close. A concurrent compaction/retention Block.Close() (tsdb/block.go:383-386, waits on pendingReaders then munmaps) can unmap the segment mid-stream, causing use-after-free: SIGSEGV/process crash (DoS) on the network-facing remote-read endpoint, or a corrupted response. A slow-reading remote client widens the race window. Before this PR the defer ran only after streaming completed, holding the reference for the whole response.","remediation":"Keep the chunk querier open until StreamChunkedReadResponses has fully consumed the ChunkSeriesSet: restore defer querier.Close() at the call site in remoteReadStreamedXORChunks so Close runs after streaming, or place querier and streaming in the same scope. Do not release the querier (and thus the mmap pendingReaders guard) before the last chunk byte is written. Avoid copying all chunk bytes before Close as a fix, since that reintroduces the OOM this PR targets.","source":"security-reviewer"}]
```

Files examined (all under `/tmp/cr-pr-nTfNFIfi`): `storage/remote/read_handler.go`, `tsdb/querier.go`, `tsdb/block.go`, `tsdb/chunks/chunks.go`, `tsdb/db.go`, `tsdb/head_read.go`, `storage/merge.go`, `tsdb/fileutil/mmap.go`.
