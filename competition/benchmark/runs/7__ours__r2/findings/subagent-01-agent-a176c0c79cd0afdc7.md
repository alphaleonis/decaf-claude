# subagent agent-a176c0c79cd0afdc7

# Code Review

**Reviewer**: broad-reviewer
**Date**: 2026-07-27
**Scope**: `storage/remote/read_handler.go` diff (PR prometheus/prometheus #13777, "Chunked remote read: close the querier earlier") — extraction of querier creation + `Select` into `getChunkSeriesSet`.

## Summary

| Severity | Count |
|----------|-------|
| 🔴 Critical | 1 |
| 🟠 High | 1 |
| 🟡 Medium | 1 |
| 🟢 Low | 0 |

**Verdict**: CRITICAL_ISSUES

## Project Standards Applied

No project documentation (CLAUDE.md or equivalent) found in this repository. Applying Knowledge Preservation, Production Reliability, and Structural Quality categories only.

---

## Findings

### 🔴 Critical: Querier is closed before the lazily-iterated ChunkSeriesSet it backs is consumed — use-after-unmap / use-after-close

| | |
|---|---|
| **File** | `storage/remote/read_handler.go:239-266` |
| **Category** | NULL_REFERENCE (use-after-close / dangling mmap access) |
| **Confidence** | 100 |
| **Pre-existing** | no |

**Issue:** `getChunkSeriesSet` (read_handler.go:242-266) calls `h.queryable.ChunkQuerier(...)`, then `defer func(){ querier.Close() }()` (lines 247-251), then returns `querier.Select(ctx, true, hints, filteredMatchers...)` at line 265. The `defer` fires as soon as this function returns — i.e., before the caller (`remoteReadStreamedXORChunks`, line 205) ever touches the returned `storage.ChunkSeriesSet`. That set is consumed **lazily** by `StreamChunkedReadResponses` in `storage/remote/codec.go:235-266`: `ss.Next()` (line 235), `series.Iterator()` (line 237), `iter.Next()`/`iter.At()` (lines 246-250), and `chk.Chunk.Bytes()` (line 261) all execute *after* `getChunkSeriesSet` has already returned and closed the querier.

I traced what `Close()` actually does for the dominant real-world path (querying on-disk TSDB blocks, which is essentially every remote-read request that isn't limited to the last few minutes of head data):

- `h.queryable.ChunkQuerier` bottoms out (through `storage.NewMergeChunkQuerier`, `storage/merge.go:79`) in one `blockChunkQuerier` per on-disk block plus a head chunk querier.
- `mergeGenericQuerier.Close()` (`storage/merge.go:255-263`) closes every constituent querier.
- `blockBaseQuerier.Close()` (`tsdb/querier.go:103-115`) calls `q.chunks.Close()`, i.e. `chunks.Reader.Close()` (`tsdb/chunks/chunks.go:656-658`), which calls `tsdb_errors.CloseAll(s.cs)` on the per-segment `*fileutil.MmapFile` closers.
- `MmapFile.Close()` (`tsdb/fileutil/mmap.go:56-64`) unconditionally calls `munmap(f.b)` — there is no reference counting; the backing memory is unmapped immediately.
- The `ChunkSeriesSet` returned by `blockChunkQuerier.Select` (`NewBlockChunkSeriesSet`, `tsdb/querier.go:1158-1171`) returns `chunkSeriesEntry{chunks: b.chunks, ...}` from `At()` (line 1173-1180). `chunkSeriesEntry.Iterator` (`tsdb/querier.go:773-780`) drives `populateWithDelChunkSeriesIterator`, whose `next()` calls `p.cr.ChunkOrIterable(p.currMeta)` (`tsdb/querier.go:721`) — i.e. `Reader.ChunkOrIterable` (`tsdb/chunks/chunks.go:666-699`), which reads directly out of the (now unmapped) `sgmBytes` byte slice.

So by the time `StreamChunkedReadResponses` calls `iter.Next()`/`chk.Chunk.Bytes()`, the memory backing the chunk bytes has already been `munmap`'d. This is not a rare race — it's the deterministic, unconditional ordering introduced by moving the `defer` into a helper that returns before the result is used. Verified unit tests pass only because `TestStreamReadEndpoint` (`storage/remote/read_handler_test.go:198`) uses `promql.LoadedStorage`, which keeps all loaded samples in the head (in-memory, not yet compacted to mmap'd blocks) — so the test never exercises `blockChunkQuerier`/`chunks.Reader` at all, and the gate's "PASS" does not validate the common on-disk-block path.

**Why Critical:** Forward path: on-disk block data is queried via chunked remote read → `getChunkSeriesSet` returns → querier (and its mmap'd chunk-segment files) is closed → `StreamChunkedReadResponses` later dereferences the unmapped memory region → the OS delivers SIGBUS/SIGSEGV on the touched address (Go does not call `debug.SetPanicOnFault`, confirmed absent via repo-wide search, and `web/web.go:96`'s `recover()` cannot catch a hardware fault) → the entire Prometheus process crashes, not just the one request. In the narrower window where another mmap call has reused the exact virtual address before the read (concurrent compaction/block open), the alternative outcome is silently returning **wrong bytes** (foreign chunk data) to the remote-read client — a data-correctness failure instead of a crash. Backward path: for the request to complete without crashing/corrupting, either (a) the OS happens to leave the unmapped page readable (not guaranteed, not the normal munmap semantics) or (b) all chunk consumption for that querier occurs only for head (non-block) series, which only holds for narrow, recent-only time-range queries. Both directions converge on the same conclusion: this breaks the common historical-data streamed remote-read path. The PR's stated goal — avoiding OOMs from misbehaving streaming clients — is undermined by trading a memory-growth risk for a crash/correctness risk that is arguably worse (full-process denial of service vs. one client's memory).

**Fix:** Don't close the querier when the helper returns; close it only once the `ChunkSeriesSet` is fully drained (or errors). E.g., wrap the returned set so `Close()` is deferred to exhaustion:

```go
// getChunkSeriesSet executes a query to retrieve a ChunkSeriesSet. The
// returned set owns the querier and closes it once iteration is exhausted
// or errors, since chunk data is read lazily from the querier's backing
// storage during iteration (see storage.ChunkSeriesSet/ChunkIterable).
func (h *readHandler) getChunkSeriesSet(ctx context.Context, query *prompb.Query, filteredMatchers []*labels.Matcher) storage.ChunkSeriesSet {
	querier, err := h.queryable.ChunkQuerier(query.StartTimestampMs, query.EndTimestampMs)
	if err != nil {
		return storage.ErrChunkSeriesSet(err)
	}

	var hints *storage.SelectHints
	if query.Hints != nil {
		hints = &storage.SelectHints{
			Start:    query.Hints.StartMs,
			End:      query.Hints.EndMs,
			Step:     query.Hints.StepMs,
			Func:     query.Hints.Func,
			Grouping: query.Hints.Grouping,
			Range:    query.Hints.RangeMs,
			By:       query.Hints.By,
		}
	}
	return &closeOnExhaustChunkSeriesSet{
		ChunkSeriesSet: querier.Select(ctx, true, hints, filteredMatchers...),
		querier:        querier,
		logger:         h.logger,
	}
}
```

(with `closeOnExhaustChunkSeriesSet.Next()` calling the underlying `Next()` and, on the first `false`/error, closing `querier` exactly once — logging the same "Error on chunk querier close" warning the original code logged). This preserves the PR's intent (close as soon as the series set stops being consumed) without closing before consumption starts.

**Actionability Check:**
- [x] Fix specifies exact change
- [x] Fix requires no additional decisions (one reasonable wrapper shape is given; the close-once bookkeeping is standard)

---

### 🟠 High: Head chunk reader's isolation state is released before iteration completes, ahead of when it used to be

| | |
|---|---|
| **File** | `storage/remote/read_handler.go:247-251` (via `tsdb/head_read.go:318-323`) |
| **Category** | RACE_CONDITION |
| **Confidence** | 50 |
| **Pre-existing** | no |

**Issue:** For the head portion of the merged `ChunkQuerier`, `Close()` calls `headChunkReader.Close()` (`tsdb/head_read.go:318-323`), which closes the read's `isolationState` (`tsdb/isolation.go:36`). That isolation state is what tells the head "this read is still in flight" and gates how far `Head.Truncate()`/compaction can safely reclaim in-memory/mmapped head chunks. Same restructuring as the Critical finding: the isolation state is now released as soon as `getChunkSeriesSet` returns, rather than after `StreamChunkedReadResponses` finishes reading head chunk data.

**Why High:** If a truncation/compaction runs concurrently with the (now-unprotected) in-flight streamed read, it can reclaim head chunks the iterator still intends to read, similarly leading to reading stale/reused memory or a nil/garbage chunk. Unlike the block-mmap case, this requires a concurrent truncation to actually land in the window between `Close()` and the later `iter.Next()` calls, so I can't verify from the diff alone that it fires on every request — hence anchor 50 rather than 100. It shares the same root cause and same fix as the Critical finding (don't release resources tied to the querier until the returned `ChunkSeriesSet` is exhausted), so fixing the Critical finding above resolves this one too.

**Fix:** Same as the Critical finding's fix — close-on-exhaustion instead of close-on-return.

**Actionability Check:**
- [x] Fix specifies exact change
- [x] Fix requires no additional decisions

---

### 🟡 Medium: No test exercises the on-disk block (mmap'd) chunk path for streamed reads

| | |
|---|---|
| **File** | `storage/remote/read_handler_test.go:198-260` |
| **Category** | TESTING_VIOLATION / test-coverage gap |
| **Confidence** | 75 |
| **Pre-existing** | yes (test used pre-existing `promql.LoadedStorage` fixture; not newly introduced by this diff), but the diff's correctness now critically depends on this exact gap |

**Issue:** `TestStreamReadEndpoint` only loads samples via `promql.LoadedStorage`'s `load` DSL, which lands data in the head (in-memory) rather than in compacted, mmap'd on-disk blocks. Because `blockChunkQuerier`/`tsdb/chunks.Reader` are never exercised, the pre-flight gate ("go test ./storage/remote/ -run 'Read|Stream|Chunk' — PASS") gives no signal about the Critical finding above — the exact code path where the bug manifests is untested.

**Why Medium (test-coverage category, not itself a production bug):** This doesn't break anything by itself, but it means the test suite would not have caught the Critical regression above, and won't catch a regression if the fix is later reverted or weakened. Given this PR's whole purpose is querier lifecycle around chunk data, a test that forces compaction to a persistent block (or otherwise forces `blockChunkQuerier`) before issuing the streamed chunked read would meaningfully close the gap.

**Fix:** Add (or extend) a streamed-read test that compacts head data into a block before querying, e.g. call `store.DB.Compact(ctx)` (or equivalent test helper) between loading samples and issuing the streamed read, so the query is served via `blockChunkQuerier`/`tsdb/chunks.Reader` rather than the head.

**Actionability Check:**
- [x] Fix specifies exact change
- [x] Fix requires no additional decisions

---

## Considered But Not Flagged

- **`chunks.Err()` check timing (read_handler.go:206):** Calling `chunks.Err()` immediately after `getChunkSeriesSet` returns, before any `Next()` call, only reliably surfaces construction-time errors (e.g. `ChunkQuerier` failing, wrapped via `storage.ErrChunkSeriesSet`, or `PostingsForMatchers` failing synchronously inside `Select`). This is a faithful, equivalent replacement for the prior inline `querier, err := ...; if err != nil { return err }` check — not a new bug. (Confidence 25, not reported.)
- **`remoteReadSamples` (unstreamed) path, lines 117-187:** Uses the same `defer querier.Close()` pattern but is unaffected because `ToQueryResult(querier.Select(...), ...)` fully materializes the `SeriesSet` synchronously, within the same function scope, before the enclosing `defer` fires. Out of scope for this diff and correctly left unchanged.
- **Unused import / signature changes:** `labels` package usage in the new `getChunkSeriesSet` signature is already imported; no new unused imports introduced.
- **Warnings handling (`ss.Warnings()` in codec.go):** Also technically read after querier close, but this is metadata rather than raw chunk bytes and is dominated by the Critical finding above (fixing that fixes this too); not flagged separately.

## Positive Observations

- The extraction itself (`getChunkSeriesSet`) is a clean, well-named refactor that isolates query construction and hint translation — good structural clarity, and the docstring correctly states the *intended* goal (timely resource release).
- Error handling for `ChunkQuerier` construction failures is preserved via `storage.ErrChunkSeriesSet`, keeping the existing HTTP error-mapping behavior (`errors.As(err, &httpErr)`) intact.
- The change is narrowly scoped to the streamed chunked path and does not touch the unstreamed sample path, limiting blast radius of the refactor itself (even though the refactor's core assumption is unsound for the reason above).
