# Comprehensive Review — PR #13777 (prometheus/prometheus)

> ℹ️ **Mode: `--local`** — this review was displayed only. Nothing was posted to GitHub.
>
> ⚠️ **PR state: MERGED, then REVERTED upstream.** PR #13777 was merged (`53091126c2`) and later reverted by PR #14515 (`6e89250a5d`, Bryan Boreham, 2024-07-26): *"Revert 'Chunked remote read: close the querier earlier' — Believed to trigger segmentation faults due to memory-mapped block data still being accessed by iterators after the querier is closed."* This is exact real-world confirmation of the Critical finding below. This review is retrospective.

## Summary

Extracts the chunked-remote-read querier acquisition and the `Select` call out of the per-query loop body in `remoteReadStreamedXORChunks` into a new helper, `getChunkSeriesSet`. The helper acquires a `ChunkQuerier`, `defer`s its `Close()`, builds the `SelectHints`, and returns `querier.Select(...)` as a `storage.ChunkSeriesSet`. A querier-acquisition error is now folded into `storage.ErrChunkSeriesSet(err)` and surfaced at the call site via `chunks.Err()`. The stated intent is to close queriers "earlier" to avoid OOMs from broken/slow chunked remote-read requests.

**Type:** bugfix (resource lifecycle)
**Effort:** 2/5 — single-file mechanical extraction (+32/-21, one file), no new dependencies or public API.

## Walkthrough

| File | Change | Summary |
|------|--------|---------|
| `storage/remote/read_handler.go` | Modified | Moves `ChunkQuerier` acquisition + `Select` into a new `getChunkSeriesSet` helper whose deferred `querier.Close()` fires when the helper returns, closing the querier before `StreamChunkedReadResponses` consumes the returned (lazy) `ChunkSeriesSet`. Acquisition errors are routed through `storage.ErrChunkSeriesSet` / `chunks.Err()`. |

---

## Review Findings

**Overall Risk: Critical** — the change introduces a remotely-triggerable use-after-close on memory-mapped block data. Confirmed by the upstream revert.

### Critical (1)

- **[code-reviewer · architecture-reviewer · security-reviewer · edge-case-hunter · adversarial-general · silent-failure-hunter · blind-hunter]** **Use-after-close: the `ChunkQuerier` is closed before the lazy `ChunkSeriesSet` it produced is consumed** — `storage/remote/read_handler.go:247` (deferred `Close` in helper) / consumed at `:205-214`.
  - `getChunkSeriesSet` registers `defer querier.Close()` and then `return querier.Select(...)`. Go `defer` runs at **function** return, so the querier is closed the instant the helper returns — *before* `remoteReadStreamedXORChunks` hands `chunks` to `StreamChunkedReadResponses`, which iterates it lazily (`ss.Next()` / `At()` / `iter.At()` / `chk.Chunk.Bytes()` in `storage/remote/codec.go`).
  - Traced through the in-tree TSDB: `blockChunkQuerier.Select` (`tsdb/querier.go:174-196`) returns a lazy `blockChunkSeriesSet` holding a reference to the querier's `ChunkReader`; `At()` (`tsdb/querier.go:1173-1180`) hands that same reader to each `chunkSeriesEntry`, which reads chunk bytes on demand. `blockBaseQuerier.Close()` (`tsdb/querier.go:103-115`) closes that reader; for on-disk blocks the underlying `MmapFile.Close()` (`tsdb/fileutil/mmap.go:56-58`) `munmap`s the region, and closing the querier releases the block-pinning `pendingReaders` guard (`tsdb/block.go`). `chk.Chunk.Bytes()` is a **zero-copy view** into that mmap.
  - **Impact:** iterating the set after close reads unmapped memory → `SIGSEGV`/`SIGBUS`, a fatal Go runtime fault that `recover` cannot catch, crashing the whole Prometheus process; or, in the silent-corruption variant, garbage chunk bytes streamed to the remote-read client. Remotely triggerable by a normal `STREAMED_XOR_CHUNKS` request; the race window is the full streaming duration (widest for exactly the large/slow responses the PR targets). The pre-PR code kept the querier open across `StreamChunkedReadResponses`, so this is a regression.
  - **Ground truth:** reverted upstream in `6e89250a5d` / PR #14515 for this exact reason (segfaults from mmap'd block data accessed after querier close).
  - **Efficacy note (adversarial-general):** beyond being unsafe, the change likely does **not** achieve its OOM goal — `querier.Close()` does not free the marshal/frame buffers held while a slow client fails to drain the stream, which is the more plausible OOM source.
  - **Fix:** do not close the querier before the set is consumed. Return the querier/closer to the caller (e.g. `(storage.ChunkSeriesSet, io.Closer, error)`) and `defer` / call `Close()` in `remoteReadStreamedXORChunks` **after** `StreamChunkedReadResponses` returns; or run consumption inside a closure while the querier is open; or materialize/copy chunk bytes before closing (defeats zero-copy streaming). *Rejected alternative:* rely on `Select` eagerly materializing — rejected because the `ChunkSeriesSet` contract does not guarantee it and the TSDB violates it.
  - Confidence: **99** (7 independent agents + verified upstream revert).

### High (1)

- **[adversarial-general]** **No test or benchmark guards the new lifecycle or the OOM claim** — `storage/remote/read_handler.go:242-266`.
  - `read_handler_test.go` was not modified. Nothing asserts the `ChunkSeriesSet` is still fully readable after `getChunkSeriesSet` returns (i.e. after `Close`), and no benchmark substantiates the memory improvement. A change whose correctness rests entirely on "the set is valid after the querier is closed" has nothing guarding that invariant — a test with a `ChunkQuerier` whose `Close()` invalidates its readers would have caught the Critical bug.
  - **Fix:** add a handler-level test asserting streamed output is correct when `Close()` invalidates readers; add a peak-heap before/after benchmark to substantiate the OOM claim. Confidence: **95**.

### Medium (3)

- **[architecture-reviewer · adversarial-general · comment-analyzer]** **Doc comment is actively misleading** — `storage/remote/read_handler.go:239-241`. The comment says the helper exists "to ensure timely release of the querier resources," framing the early close as a pure win and hiding the load-bearing, hazardous fact that the returned set is consumed *after* the querier is closed. A future maintainer would treat a dangerous pattern as an established safe optimization. **Fix:** state the real precondition (the returned set must be fully materialized and safe to iterate post-`Close`; lazy backends are unsafe here) — though per the Critical finding the design itself should change rather than just the comment. Confidence: **80**.

- **[architecture-reviewer]** **Helper API shape swallows the querier handle, preventing caller-side lifetime management** — `storage/remote/read_handler.go:242-246`. Folding the acquisition error into `storage.ErrChunkSeriesSet` so the caller can uniformly check `chunks.Err()` also discards the `querier`, which is the direct enabler of the premature-close design and is not evolution-safe. **Fix:** return `(storage.ChunkSeriesSet, io.Closer, error)` or use a loan/callback form (`withChunkSeriesSet(ctx, query, matchers, func(ss) error) error`) so acquisition errors stay distinct from iteration errors and querier lifetime is caller-controlled. *Rejected alternative:* keep the value-only signature and document the constraint — rejected because it leaves the hazard in place. Confidence: **78**.

- **[adversarial-general]** **The condition being "fixed" is uninstrumented** — `storage/remote/read_handler.go:189-237`. The change is motivated purely operationally ("I have seen instances misbehaving") but adds no metric/log for aborted/errored chunked reads, querier lifetime, or in-flight streamed bytes. Operators cannot confirm the fix worked or detect the failure mode. **Fix:** add a counter for aborted/errored chunked reads and/or a histogram of streamed bytes per request. Confidence: **80**.

### Positive Observations

- The querier-acquisition error path is correct in isolation: `storage.ErrChunkSeriesSet(err)` → `chunks.Err()` faithfully reproduces the old early-return behavior, and the `errChunkSeriesSet` implementation (`Next()==false`, `Err()` returns the wrapped error) makes `StreamChunkedReadResponses` fall straight through to `return ss.Warnings(), ss.Err()`. No error is dropped.
- The `SelectHints` construction was moved verbatim with no field-mapping errors.
- The `if err != nil` guard before registering the `defer` correctly avoids a nil-querier `Close()`.
- The `querier.Close()` Warn-log path is textually unchanged (still fires, just relocated).

### Recommended Actions

1. **Do not merge as-is** (and indeed it was reverted upstream). Keep the `ChunkQuerier` alive until `StreamChunkedReadResponses` has fully consumed the `ChunkSeriesSet` — hand the closer back to the caller and close after streaming, or use a closure/loan pattern.
2. Re-validate the OOM premise: measure whether closing the querier earlier actually reduces peak memory, or whether the OOM is driven by marshal/frame buffers held for slow clients (bound those via backpressure / a per-request byte budget instead).
3. Add a regression test (a `ChunkQuerier` whose `Close()` invalidates readers) and a peak-heap benchmark before attempting this optimization again.
4. Rewrite the `getChunkSeriesSet` doc comment to state the real lifetime precondition, or remove the early-close design.
5. Add observability for the failure mode this targets so any future attempt is measurable.

---

### Review metadata

- **Diff tier:** small (53 changed lines, 1 file, Go)
- **Agents run (9):** pr-summarizer, code-reviewer, architecture-reviewer, security-reviewer, edge-case-hunter, adversarial-general, silent-failure-hunter, comment-analyzer, blind-hunter
- **Agents skipped:** pr-test-analyzer (no test files in diff), type-design-analyzer (no new type/struct/interface definitions), issue-linker (`--local`/`--pr` mode), CVE/dependency check (no dependency-manifest files changed)
- **Opus agent tool calls:** architecture-reviewer=12 (budget 25) ✓ · security-reviewer=10 (budget 25) ✓
- **Confidence filter:** ≥ 75 (dropped 1 finding below threshold: "lifecycle divergence from the samples path", confidence 70)
