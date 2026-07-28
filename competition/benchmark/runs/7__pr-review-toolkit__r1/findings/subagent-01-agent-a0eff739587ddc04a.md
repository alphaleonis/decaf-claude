# subagent agent-a0eff739587ddc04a

I have everything I need. Here is my test-coverage analysis.

---

# Test Coverage Analysis — PR #13777 "Chunked remote read: close the querier earlier"

## Summary

The PR reorders resource lifetime: it extracts querier creation/`Select`/`Close` into `getChunkSeriesSet` (`storage/remote/read_handler.go:242-266`), which closes the `ChunkQuerier` via `defer` (lines 247-251) **before** the returned `storage.ChunkSeriesSet` is streamed by `StreamChunkedReadResponses` (called at `read_handler.go:210`, iterated at `codec.go:235-296`). The whole risk surface of this change is **use-after-close**: the chunk iterators are consumed after the querier that owns their backing memory is closed.

The PR adds **no tests**, and the existing suite does **not** cover the regression this refactor risks. I can state this as verified fact rather than inference: the identical change on HEAD (`53091126c2`) was later reverted upstream in `6e89250a5d` with the message *"Believed to trigger segmentation faults due to memory-mapped block data still being accessed by iterators after the querier is closed."* The existing tests passed both before and after that segfault was discovered — they never exercised the failing path. So "no new tests" is **not** adequate here.

## What the existing tests actually do

Two tests hit the chunked path, both via `NewReadHandler` + `ServeHTTP` with `STREAMED_XOR_CHUNKS`:

- `TestStreamReadEndpoint` (`storage/remote/read_handler_test.go:198`) — asserts `recorder.Code/100 == 2` (line 277) and byte-exact chunk output (lines 296-431).
- `BenchmarkStreamReadEndpoint` (`read_handler_test.go:134`) — asserts success and result count.

Both build their queryable with `promql.LoadedStorage` → `teststorage.New` (`util/teststorage/storage.go:31-50`). That **is** a real `tsdb.DB`, so structurally these tests do reach the reordered code: `getChunkSeriesSet` closes the querier, then `StreamChunkedReadResponses` iterates the set — synchronously inside `ServeHTTP` — so the iterate-after-close ordering genuinely happens under test.

The gap is the **fixture's storage layout, not a no-op mock**. `teststorage.New` sets `MinBlockDuration = MaxBlockDuration = 24h` (`storage.go:38-39`) and never compacts. All loaded samples (spanning ~4h) stay in the **in-memory head**. The head `ChunkQuerier`'s chunks are backed by live Go heap memory that `Close()` does not unmap or free, so iterating after close is harmless for this fixture. The dangerous case — a **persistent, memory-mapped block** querier, whose `Close()` releases the mmap so later iteration reads unmapped memory — is never constructed. [Inference, consistent with the revert message] That is precisely why the tests are green while the change segfaults in production against on-disk blocks.

Net: the tests catch gross breakage of head-based streaming, but they would pass whether or not the change is safe on a real block querier. They are not a regression detector for this PR's actual risk.

## Untested scenarios, ranked

### 1. Streaming after early `Close` on a memory-mapped block querier — the reverted segfault. Criticality 10
No test compacts data into a persistent block and then streams it. This is the exact defect that got the change reverted. Recommendation — two complementary tests:

- `TestStreamReadEndpoint_ConsumeAfterCloseIsSafe` using a **mock** `storage.SampleAndChunkQueryable` that models block semantics: its `ChunkQuerier` returns a `ChunkSeriesSet` whose chunk `Data`/iterator is backed by a buffer the querier **invalidates on `Close()`** (e.g. zeroes it, or the iterator returns a sentinel error / panics if touched after `Close` was called). Drive it through `ServeHTTP` and assert the streamed bytes equal the pre-close data. Under the current design this test fails deterministically (no reliance on an actual OS segfault), reproducing the use-after-close. This is the load-bearing test the PR is missing.
- An integration variant that appends data, calls `db.Compact()` to force a persistent mmap'd block, then runs the chunked read and asserts correct output — run under `-race`. [Inference] A real crash here is timing/OS-dependent and may not reproduce deterministically, which is why the mock above is the primary detector and this is the belt-and-suspenders.

### 2. Querier-creation error path is unasserted. Criticality 7
The PR moved error propagation from a direct `return err` to `ErrChunkSeriesSet(err)` (`read_handler.go:245`) surfaced via `chunks.Err()` at the caller (`read_handler.go:206-208`). No test injects a queryable whose `ChunkQuerier(...)` returns an error, and no chunked-path test asserts a non-2xx status at all (every assertion is `Code/100 == 2`). Recommendation — `TestStreamReadEndpoint_ChunkQuerierError`: mock queryable returning `(nil, errors.New("boom"))` from `ChunkQuerier`; POST a `STREAMED_XOR_CHUNKS` request; assert `recorder.Code == 500` and body contains `boom`. Add a second case returning an `HTTPError` to assert the status mapping at `read_handler.go:228-231`.

### 3. Lazy error during iteration is unasserted. Criticality 5
A `ChunkSeriesSet` that errors mid-iteration is surfaced via `ss.Err()` (`codec.go:296`) → HTTP error. Not covered for the chunked handler. Recommendation — `TestStreamReadEndpoint_IterationError`: mock querier whose `Select` returns a set that yields one series then reports `Err()` (or returns a nil-`Chunk`, hitting `codec.go:252-254`); assert the error reaches the client as 500.

### 4. `Close()` returning an error (warn-log branch). Criticality 2
`read_handler.go:248-250` logs and swallows a close error. Log-only, no behavioral contract; test only if you want the branch covered. Low priority.

## Test-quality note

`TestStreamReadEndpoint` asserts byte-exact chunk payloads (`read_handler_test.go:311`, etc.). That is a reasonable golden assertion for XOR encoding stability, but it means the test is coupled to encoding internals and would need regeneration on any encoder change — acceptable here, just flagging it is not a behavior-only assertion.

## Positive observations

- The chunked path is genuinely driven end-to-end through the public `ServeHTTP` surface, and iteration-after-close does occur under test — the structure is right; only the storage layout undercuts it.
- Output correctness for the head case is asserted precisely (frame counts, per-series chunk splits by byte limit, histogram chunks), so head-side streaming breakage would be caught.
- `errChunkSeriesSet` itself has a clean, tested-elsewhere contract (`storage/interface.go:396-404`): `Next()` false, `Err()` returns the wrapped error — so the wiring is sound; it is only the handler-level assertion that is missing.

## Verdict on "no new tests"

Not acceptable for merge as-is. For a change whose sole purpose is resource-lifetime reordering, the minimum bar is a test that consumes the series set **after** the querier closes against a fixture that treats post-close access as invalid (gap 1, the mock detonate-on-close test) plus the querier-creation error assertion (gap 2). The upstream revert is direct evidence that shipping without gap 1 let a segfault through. Gaps 3-4 are worthwhile but secondary.

Key references: `storage/remote/read_handler.go:205-208` (new `chunks.Err()` check), `:242-266` (`getChunkSeriesSet`, defer-close at `:247-251`, `ErrChunkSeriesSet` at `:245`); `storage/remote/read_handler_test.go:198`/`:134` (existing tests), `:277`/`:179`/`:84` (only-success assertions); `storage/remote/codec.go:235-296` (iteration + `ss.Err()`); `util/teststorage/storage.go:31-50` (head-only fixture); revert `6e89250a5d`.
