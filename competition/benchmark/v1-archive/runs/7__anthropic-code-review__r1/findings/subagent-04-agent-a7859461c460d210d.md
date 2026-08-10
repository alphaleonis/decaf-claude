# subagent agent-a7859461c460d210d

Those two are unrelated performance/flushing changes, not related to querier lifetime. I have complete evidence now.

## Report: PR #13777 was reverted due to a production SIGSEGV crash

**Verdict: this is a confirmed regression, later reverted.** The early-close change in PR #13777 (merged 2024-03-15, `53091126c2`) was reverted **4 months later** and the revert was even backported to two release branches — strong evidence this was a real, serious bug, not just a stylistic rollback.

### Timeline

1. **2024-03-15** — PR [#13777](https://github.com/prometheus/prometheus/pull/13777) merged (`53091126c2`). Extracted `getChunkSeriesSet`, moving `querier.Close()` from the caller's closure scope into the helper, so the querier closes as soon as `Select()` returns — before `StreamChunkedReadResponses` iterates the `ChunkSeriesSet`. Rationale in the PR description: avoid OOMs from broken chunked remote-read requests holding queriers open too long.
2. **2024-07-05 (reported)** — Issue [#14422](https://github.com/prometheus/prometheus/issues/14422) "SIGSEGV after writing block" filed against v2.53.0. Crash stack trace:
   ```
   fatal error: fault
   [signal SIGSEGV: segmentation violation ...]
   encoding/binary.Uvarint(...)
   github.com/prometheus/prometheus/tsdb/chunks.(*Reader).ChunkOrIterable(...)
       /app/tsdb/chunks/chunks.go:681
   ...
   github.com/prometheus/prometheus/storage.(*compactChunkIterator).Next(...)
       /app/storage/merge.go:724
   github.com/prometheus/prometheus/storage/remote.StreamChunkedReadResponses(...)
       /app/storage/remote/codec.go:246
   github.com/prometheus/prometheus/storage/remote.(*readHandler).remoteReadStreamedXORChunks.func1(...)
       /app/storage/remote/read_handler.go:210
   ```
   Crashes correlated tightly with block compaction ("always happens right after it wrote a new block to disk"), consistent with the mmap'd block being unmapped mid-iteration.
3. **2024-07-26** — PR [#14515](https://github.com/prometheus/prometheus/pull/14515) "Revert 'Chunked remote read: close the querier earlier'" (commit `6e89250a5d`), by Bryan Boreham. Full commit message:
   > "Believed to trigger segmentation faults due to memory-mapped block data still being accessed by iterators after the querier is closed."

   PR body: *"Fixes #14422. I believe the iterators for the querier can access memory-mapped files, which are closed when the querier is closed. A better fix might be to reference-count the chunk-reader so it is only closed when no longer accessed."*
4. **2024-07-29** — #14515 merged.
5. **2024-07-30 / 2024-07-31** — Backported to release branches: PR [#14524](https://github.com/prometheus/prometheus/pull/14524) (Release 2.54) and PR [#14523](https://github.com/prometheus/prometheus/pull/14523) (Release 2.53) — indicating the crash was considered severe enough for immediate patch releases.
6. **2024-10-16** — PR [#14599](https://github.com/prometheus/prometheus/pull/14599) "test(tsdb): add a reproducer for #14422" merged, confirming the root cause explicitly: *"a block that was being queried by the read API was able to get closed because it had no `pendingReaders`"* — i.e., closing the chunk querier decremented the block's reader refcount to zero, letting the block (and its mmap) be closed/compacted away while `StreamChunkedReadResponses` was still iterating chunks from it.

### The revert is a clean, exact inverse of #13777

`gh pr diff 14515` shows it removes `getChunkSeriesSet` entirely and restores the querier creation + `defer querier.Close()` + `Select()` directly inline in the per-query closure in `remoteReadStreamedXORChunks`, i.e., **exactly** the caller-scope pattern that existed before #13777.

### Current state on `main` (verified live via `gh api .../contents/storage/remote/read_handler.go`)

`getChunkSeriesSet` does not exist. The querier lifetime is caller-scoped again, currently around lines 205-238 of `storage/remote/read_handler.go`:
```go
querier, err := h.queryable.ChunkQuerier(query.StartTimestampMs, query.EndTimestampMs)
if err != nil {
    return err
}
defer func() {
    if err := querier.Close(); err != nil {
        h.logger.Warn("Error on chunk querier close", "err", err.Error())
    }
}()
...
ws, err := StreamChunkedReadResponses(
    cw,
    int64(i),
    querier.Select(ctx, true, hints, filteredMatchers...),
    ...
)
```
This `defer` sits inside the `func() error { ... }()` closure that wraps the entire per-query body — meaning `querier.Close()` now fires only after `StreamChunkedReadResponses` finishes streaming that query's chunks, i.e., after the `ChunkSeriesSet` has been fully consumed. No commit since the 2024-07-26 revert has reintroduced early-close (subsequent history on this file: metric renames, slog migration, copyright cleanup, and unrelated flush-buffering changes from 2026 — none touch querier lifetime).

### Answer to question 2: was the caller-scope defer originally intentional to keep the querier alive during streaming?

[Inference from evidence, not an explicit design doc]: The original pattern long predates #13777 (present at least back through the 2021 `ce97cdd477` "Move remote read handler to remote package" commit and earlier). There's no explicit comment in the pre-#13777 code stating "must stay open during streaming," but the *effect* of caller-scope defer — keeping the querier (and thus the underlying block's `pendingReaders` refcount) alive for the full duration of `StreamChunkedReadResponses` — is exactly the property whose removal caused the SIGSEGVs, and exactly what the 2024 revert restored. The `#14599` reproducer test's finding (*"a block ... was able to get closed because it had no `pendingReaders`"*) confirms this was a load-bearing property of the original placement, whether or not it was originally documented as intentional.

### Bottom line for a review of PR #13777 at the time

The core issue this historical context reveals: **closing the chunk querier before `StreamChunkedReadResponses` finishes iterating the returned `ChunkSeriesSet` is unsafe** — it lets the underlying TSDB block's memory-mapped chunk data be released (via `pendingReaders` refcounting) while iterators returned by that querier are still being read, causing SIGSEGVs in production (`tsdb/chunks.Reader.ChunkOrIterable` / `encoding/binary.Uvarint`) that surfaced specifically under load, correlated with block compaction. This was severe enough to warrant a same-week revert plus backports to two already-released minor versions (2.53, 2.54). A reviewer of #13777 should have flagged that moving `defer querier.Close()` into a helper that returns *before* the caller consumes the lazily-evaluated `ChunkSeriesSet` breaks the querier's implicit lifetime contract with the storage layer — `storage.Querier.Select()` returns a lazy iterator, not fully-materialized data, so the querier (and the block readers it pins) must outlive iteration, not just the `Select()` call.
