# subagent agent-a20c656de100ca031

I have all the evidence needed. Here are my complete findings.

---

# Test Coverage Analysis — PR prometheus/prometheus #13777 "Chunked remote read: close the querier earlier"

## Does the PR add or change any tests?

**No.** The merge commit (`53091126c2`) touches exactly one file, `storage/remote/read_handler.go` (+32/-21). No `_test.go` file is added or modified. Confirmed via `git show --stat`. This is a behavioral/lifecycle change to a hot path with zero accompanying test changes.

## Summary

The change extracts `getChunkSeriesSet` (read_handler.go:242-266) and closes the `ChunkQuerier` via `defer` (lines 247-251) that fires when the helper returns at line 265 — i.e., the querier is closed **before** the returned `storage.ChunkSeriesSet` is consumed by `StreamChunkedReadResponses` (called at read_handler.go:210-218, iterating `chunks` after the close has already run). This is precisely the use-after-close invariant the task flags.

The single most important determination you asked for: the existing tests **do use a real tsdb-backed queryable, not a mock** — so a naive "close is a no-op" argument does not apply. **However**, the test data lives entirely in the **in-memory head block**; it is never compacted into the memory-mapped persistent blocks whose chunk readers `Close()` actually unmaps. That is the exact resource the early close releases out from under the still-live iterators. So the tests exercise the code path but **cannot** trip the fault.

**This is not hypothetical.** The PR was reverted (commit `6e89250a5d`, PR #14515, Bryan Boreham) with the message:
> "Believed to trigger segmentation faults due to memory-mapped block data still being accessed by iterators after the querier is closed."

The regression reached a release and was rolled back. The existing tests passed the whole time. That is the definitive verdict on test adequacy: **inadequate.**

---

## Evidence: real tsdb, but head-only data

**The queryable is a real `*tsdb.DB` (not a mock):**
- `storage/remote/read_handler_test.go:203-209` — `TestStreamReadEndpoint` builds `store` via `promql.LoadedStorage(t, ...)`.
- `promql/test.go:59-72` — `LoadedStorage` returns a `*teststorage.TestStorage`.
- `util/teststorage/storage.go:52-56` — `TestStorage` **embeds `*tsdb.DB`**; `util/teststorage/storage.go:30-50` — `New` opens a real on-disk TSDB in a temp dir. So `querier.Close()` runs real tsdb cleanup, not a stub.

**But the data never leaves the head, so no mmapped persistent-block chunks exist:**
- `TestStreamReadEndpoint` and `BenchmarkStreamReadEndpoint` (read_handler_test.go:198, :134) only append + commit (via `LoadedStorage` and `addNativeHistogramsToTestSuite` at :434-443). Neither the test nor `teststorage`/`LoadedStorage` ever calls `Compact`/`CompactHead`/`createBlock` (grep for those in `storage/remote/` returns nothing; `teststorage.New` sets 24h min/max block durations specifically so data stays appendable in the head).

**Why head-only data hides the bug:**
- `tsdb/querier.go:103-115` — `blockBaseQuerier.Close()` calls `q.chunks.Close()`, which unmaps the memory-mapped chunk files of a **persistent** block. A `blockChunkSeriesSet` returned by `Select` reads those chunks **lazily during iteration**. Close-then-iterate on a persistent block = reading unmapped memory = the segfault the revert describes. Head chunks are in-memory and not released this way, so the head-only test iterates safely after close and the assertions on exact chunk bytes (read_handler_test.go:296-431) still pass.

---

## Findings (severity-ranked)

### Critical Gaps (8-10)

1. **[CRITICAL, 10] No test covers the exact invariant the PR relies on: querier closed before `ChunkSeriesSet` is consumed, against persistent (mmapped) blocks.** `storage/remote/read_handler.go:205-218` + `:247-251`. Failure scenario: a remote-read STREAMED_XOR_CHUNKS request whose series live in a compacted on-disk block. `getChunkSeriesSet` closes the querier (unmapping the block's chunk files), then `StreamChunkedReadResponses` iterates the now-dangling chunk iterators → segfault / silent memory corruption. The head-only `TestStreamReadEndpoint` (read_handler_test.go:198) is structurally incapable of catching this. Confirmed by the production revert (`6e89250a5d`). This gap is the whole reason the change was unsafe.
   - Where it would live: `storage/remote/read_handler_test.go`, a new `TestStreamReadEndpoint_PersistentBlocks` (or similar) that appends data, forces a head compaction into a persistent block (e.g. `store.DB.Compact(ctx)` / `CompactHead`), then runs the streamed read and asserts the full response — so the mmapped-block path is exercised end-to-end after close.

### Important Improvements (5-7)

2. **[IMPORTANT, 7] The `ChunkQuerier` construction-error path (`read_handler.go:243-245`) is untested.** `getChunkSeriesSet` now converts a `ChunkQuerier(...)` error into `storage.ErrChunkSeriesSet(err)` (storage/interface.go:401-402), surfaced via `chunks.Err()` at read_handler.go:206. No test injects a queryable whose `ChunkQuerier` returns an error, so the new error-routing (error object → `ErrChunkSeriesSet` → `Err()` → HTTP error) is never verified. A regression that dropped or mis-mapped this error (e.g. returning `nil` set) would go unnoticed. Would live in `read_handler_test.go` with a small fake `SampleAndChunkQueryable`.

3. **[IMPORTANT, 6] The `Select`-level error path via `chunks.Err()` is untested.** read_handler.go:206-208. Distinct from construction error: a `ChunkSeriesSet` that carries a deferred `Select` error. No test asserts this maps to the correct HTTP status (`HTTPError` vs 500 at :228-234).

4. **[IMPORTANT, 5] Close-error handling is untested.** read_handler.go:247-251 logs a warning if `querier.Close()` errors and otherwise swallows it. No test with a queryable whose `Close()` returns an error verifies the request still succeeds and the warning is logged. Low blast radius, but it is new branching behavior.

### Test Quality Issues

5. **[QUALITY] Existing streamed tests assert exact serialized chunk bytes (read_handler_test.go:307-431).** These are golden-byte assertions — brittle to any encoding change, yet, as shown, blind to the lifecycle regression that actually mattered. They give a false sense of thoroughness: high-fidelity on output shape, zero coverage of resource lifetime. Not something to fix in this PR, but it explains why "the tests pass" was misleading here.

6. **[QUALITY] Empty-result and large-multi-block streaming after close are uncovered.** No test for a matcher that selects zero series (does `getChunkSeriesSet` still behave when the set is empty after close?), nor for a result large enough to span multiple mmapped blocks streamed across many frames after close — the scenario most likely to dereference unmapped memory in production.

### Positive Observations

- The test harness is genuinely real-storage-backed (`*tsdb.DB`), which is the right foundation — the gap is data placement (head vs. persistent block), not a mock/no-op querier. A relatively small addition (force compaction before the read) would have exercised the failing path.
- `TestStreamReadEndpoint` does cover the happy path thoroughly: multiple queries, external-label handling, byte-frame splitting, float and native-histogram chunks, and `QueryIndex` propagation.

---

## Verdict on test adequacy

**Inadequate for this specific change.** The PR altered a resource-lifecycle invariant (close querier before consuming its lazily-iterated `ChunkSeriesSet`) and added no test proving that invariant holds. The one existing test that touches the path (`TestStreamReadEndpoint`, read_handler_test.go:198) runs against head-only, in-memory data and is structurally unable to exercise the memory-mapped persistent-block iteration that the early close breaks. Per Prometheus's own contribution guideline ("if the PR adds or changes a behaviour ... it would need a unit/e2e test"), a test compacting data into a persistent block and streaming it after the querier closed was required and absent.

[Verified] The consequence is not speculative: the change was reverted in production (commit `6e89250a5d` / PR #14515) for triggering segmentation faults from exactly this early close — while the existing test suite remained green throughout. A single persistent-block test would [Inference — expected, not guaranteed] have caught it before merge.

**Key files:**
- `/home/decaf/code/decaf-claude/competition/benchmark/repos/7/storage/remote/read_handler.go` (lines 205-218 consume-after-close; 242-266 helper; 247-251 deferred close)
- `/home/decaf/code/decaf-claude/competition/benchmark/repos/7/storage/remote/read_handler_test.go` (198 `TestStreamReadEndpoint`; 134 benchmark; 203-209 head-only store setup)
- `/home/decaf/code/decaf-claude/competition/benchmark/repos/7/util/teststorage/storage.go` (30-56 real `*tsdb.DB`, no compaction)
- `/home/decaf/code/decaf-claude/competition/benchmark/repos/7/tsdb/querier.go` (103-115 `blockBaseQuerier.Close` → `chunks.Close()` unmaps)
- `/home/decaf/code/decaf-claude/competition/benchmark/repos/7/storage/interface.go` (401-402 `ErrChunkSeriesSet`)
