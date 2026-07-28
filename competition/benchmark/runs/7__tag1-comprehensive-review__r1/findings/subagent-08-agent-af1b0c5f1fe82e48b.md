# subagent agent-af1b0c5f1fe82e48b

# Error-Handling Audit — storage/remote/read_handler.go (PR #13777)

## Summary of the three specific questions asked

1. **ChunkQuerier-creation error propagation**: confirmed NOT dropped. `storage.ErrChunkSeriesSet(err)` (storage/interface.go:402-403) returns `errChunkSeriesSet{err}`, whose `Err()` returns the wrapped err (storage/interface.go:398) and `Next()` returns `false` (storage/interface.go:396). `getChunkSeriesSet`'s early return path (read_handler.go:244-246) is caught by `chunks.Err()` at read_handler.go:206-208 and returned exactly as `return err` did before, then reaches the same outer `errors.As(err, &httpErr)` / `http.Error(...)` handling at read_handler.go:228-234. No regression — even without the explicit check it would still surface via `ss.Err()` at codec.go:296 since `ss.Next()` returns false immediately.

2. **Deferred `querier.Close()` Warn-and-swallow**: unchanged. The same log line (`level.Warn(h.logger).Log("msg", "Error on chunk querier close", "err", err.Error())`) was simply relocated into the new helper (read_handler.go:247-251). No new behavior.

3. **Does moving `Select()` change WHEN a Select error is observed?** No — `ChunkQuerier.Select()` (tsdb/querier.go:174) returns a bare `ChunkSeriesSet`, not `(ChunkSeriesSet, error)`. Select-time errors have always only been observable via the returned set's `.Err()` once drained inside `StreamChunkedReadResponses` (codec.go:296: `return ss.Warnings(), ss.Err()`). The new `chunks.Err()` check at read_handler.go:206 fires immediately after `getChunkSeriesSet` returns, before any iteration — for a genuinely lazy series set this is always nil at that point, so it only ever catches the Finding-3 immediate-error case. No Select-error path is newly masked.

None of the above three are silent-failure regressions. However, tracing the actual resource lifetime surfaced a critical issue outside the three framed questions but squarely in scope of "silent failures" — reported below per governance's "surface adjacent harms" directive.

---

## CRITICAL — Early `querier.Close()` creates a use-after-close race on mmap'd chunk data; failure is invisible to any Go error path

**Location**: `storage/remote/read_handler.go:242-266` (`getChunkSeriesSet`), interacting with `tsdb/block.go:378-390` (`Block.Close`), `tsdb/block.go:562-570` (`blockChunkReader.Close`), `tsdb/chunks/chunks.go:665-667` and `675-712` (`Reader.Close` / `Reader.ChunkOrIterable`), `storage/merge.go:104-150` and `255-263` (`mergeGenericQuerier.Select`/`Close`), and `tsdb/db.go:1656-1666` (`DB.deleteBlocks`).

**Issue**: In `getChunkSeriesSet`, the `defer querier.Close()` (read_handler.go:247-251) fires when the function returns — i.e., immediately after `querier.Select(ctx, true, hints, filteredMatchers...)` is evaluated (read_handler.go:265) but **before** the caller ever iterates the returned `ChunkSeriesSet`. The caller (`remoteReadStreamedXORChunks`, read_handler.go:205-214) hands the still-unconsumed set straight to `StreamChunkedReadResponses`, which reads chunk bytes lazily during its `for ss.Next()` loop (codec.go:235-295) — this is confirmed by `mergeGenericQuerier.Select` (storage/merge.go:104-150), which wraps sub-results in a `lazyGenericSeriesSet` whose merge/read logic runs only on first `Next()`.

`querier.Close()` is synchronous across every block touched by the query (`mergeGenericQuerier.Close`, storage/merge.go:255-263 closes each sub-querier in a loop). For a TSDB block querier, closing calls `blockChunkReader.Close()` (tsdb/block.go:567-570), which does exactly one thing: `r.b.pendingReaders.Done()`. That `pendingReaders` WaitGroup is the *sole* mechanism that keeps a block's on-disk files (and their mmap) alive against concurrent deletion — `Block.Close()` (tsdb/block.go:378-390) explicitly documents "It blocks as long as there are readers reading from the block," calling `pb.pendingReaders.Wait()` before `pb.chunkr.Close()` actually unmaps the chunk file (`tsdb/chunks/chunks.go:665-667`, `Reader.Close()` → `tsdb_errors.CloseAll(s.cs)` on the `fileutil.OpenMmapFile` handles). `DB.deleteBlocks` (tsdb/db.go:1656-1666, invoked from compaction/retention) calls exactly this `block.Close()` before removing the directory, with the comment: *"it might need to wait for pending readers to complete."*

By decrementing `pendingReaders` as soon as `Select()` returns — instead of after the response has been fully streamed — this change hands compaction/retention the "all clear" signal to unmap the chunk file's mmap region **while `StreamChunkedReadResponses` may still be actively reading chunk bytes from it** (a request streaming a large chunked range is, by design, exactly the slow/long-lived case this PR targets). `Reader.ChunkOrIterable` (tsdb/chunks/chunks.go:675-712) reads directly off the mmap'd byte slice (`sgmBytes.Range(...)`) with no liveness check — there is no Go-level `error` this can produce, because the failure happens below the error-return abstraction as raw memory access on a region that has been `munmap`'d out from under it.

**Hidden errors / failure modes** (none of which produce a catchable, loggable Go error):
- Reading unmapped memory typically triggers a fatal `SIGSEGV`. Go converts this to an unrecoverable fault (not a normal panic `recover()` can catch), crashing the *entire Prometheus process* — killing every other in-flight request, not just this one.
- If the OS hasn't yet reclaimed the physical pages, the read may silently succeed with garbage or stale bytes — the client receives corrupted chunk data in its remote-read response with **zero** indication anything is wrong: no error, no Warn log, no HTTP error status.

**User impact**: This is strictly worse than the OOM behavior the PR sets out to fix. Instead of a memory-pressure issue that operators can observe and mitigate (alerting, restarts), a large/slow chunked remote-read request racing with normal background compaction/retention can now either take down the whole Prometheus server or silently hand back wrong metric data to the remote-read client. Debugging this after the fact would be extremely difficult — a SIGSEGV crash log gives no application-level context, and silently-wrong data leaves no trace at all.

**Recommendation**: Do not release the querier (and thus the block's `pendingReaders` slot) before the `ChunkSeriesSet` returned from it has been fully consumed. Keep the querier's `Close()` tied to the *end* of streaming, not the end of `Select()`. Concretely: either (a) keep `defer querier.Close()` in `remoteReadStreamedXORChunks` after `StreamChunkedReadResponses` returns (i.e., revert the resource-lifetime part of this change while keeping the ChunkQuerier-creation-error wrapping as a separate, safe simplification), or (b) have `getChunkSeriesSet` return a `ChunkSeriesSet` wrapper whose own `Close`/drain path closes the underlying querier only once iteration is truly done, and ensure `StreamChunkedReadResponses`/its caller invoke that close after streaming finishes.

**Rejected alternative considered**: detecting "read from an already-unmapped mmap" inside `Reader.ChunkOrIterable` and turning it into a normal Go `error`. Rejected — there is no portable, reliable way to detect a stale mmap from user-space Go without OS-level signal handling (e.g., `mmap`'d SIGSEGV handler tricks), and it would only paper over the real problem (the block's data being invalidated mid-read) rather than preventing it. Keeping the resource alive for the true duration of use is the direct fix.

**Confidence note** [labeling per verified-truth directive]: I directly read and traced `block.go`, `chunks.go`, `merge.go`, and `db.go` in the PR-state worktree and confirmed the code paths described above exist exactly as cited. I did **not** run a reproduction (race detector / fuzz test) to empirically prove the crash-vs-corrupted-read outcome — that specific manifestation (SIGSEGV vs. silently-stale-page read) depends on OS memory-management timing I have not verified experimentally; that part is `[Inference]` from standard mmap/munmap semantics, not a confirmed observed crash. The underlying race condition itself (early `pendingReaders.Done()` racing `Block.Close()`/`deleteBlocks`) is verified directly from the code, not inferred.

---

## Findings NOT present (explicitly checked, ruled out)

- **Empty catch blocks / swallowed errors introduced by this diff**: none found — both error paths in the diff (`ChunkQuerier` creation failure, `querier.Close()` failure) are logged/returned identically to before.
- **Broad exception catching**: N/A, Go code, no such pattern here.
- **New fallback-to-mock or silent default-value behavior**: none introduced.

## Files relevant to this review
- `/tmp/cr-pr-nTfNFIfi/storage/remote/read_handler.go` (the diff)
- `/tmp/cr-pr-nTfNFIfi/storage/remote/codec.go` (`StreamChunkedReadResponses`)
- `/tmp/cr-pr-nTfNFIfi/storage/interface.go` (`errChunkSeriesSet`/`ErrChunkSeriesSet`)
- `/tmp/cr-pr-nTfNFIfi/storage/merge.go` (`mergeGenericQuerier.Select`/`Close`)
- `/tmp/cr-pr-nTfNFIfi/tsdb/block.go` (`Block.Close`, `startRead`, `blockChunkReader`)
- `/tmp/cr-pr-nTfNFIfi/tsdb/chunks/chunks.go` (`Reader.Close`, `Reader.ChunkOrIterable`)
- `/tmp/cr-pr-nTfNFIfi/tsdb/db.go` (`deleteBlocks`)
