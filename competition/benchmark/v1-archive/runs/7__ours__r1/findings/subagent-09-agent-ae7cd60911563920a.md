# subagent agent-ae7cd60911563920a

# Code Review

**Reviewer**: broad-reviewer
**Date**: 2026-07-27
**Scope**: `storage/remote/read_handler.go` — extraction of `getChunkSeriesSet` in PR prometheus/prometheus#13777 ("Chunked remote read: close the querier earlier"), reviewed against `tsdb/querier.go`, `tsdb/chunks/chunks.go`, `tsdb/fileutil/mmap.go`, `tsdb/head_read.go`, `tsdb/isolation.go`, `storage/merge.go`, and `storage/remote/codec.go` to determine whether the resource-lifecycle change is safe.

## Summary

| Severity | Count |
|----------|-------|
| 🔴 Critical | 1 |
| 🟠 High | 1 |
| 🟡 Medium | 0 |
| 🟢 Low | 0 |

**Verdict**: CRITICAL_ISSUES

## Project Standards Applied

No CLAUDE.md or project-local review documentation was found in this repository checkout. Applying Knowledge Preservation, Production Reliability, and Structural Quality categories only.

---

## Findings

### 🔴 Critical: `getChunkSeriesSet` closes the querier before the `ChunkSeriesSet` it returns is ever iterated, and chunk reads are lazy — this is a use-after-close on the underlying block/mmap resources

| | |
|---|---|
| **File** | `storage/remote/read_handler.go:242-266` |
| **Category** | RACE_CONDITION (use-after-close / premature resource release) |
| **Confidence** | 100 |
| **Pre-existing** | no — introduced by this changeset |

**Issue:**

`getChunkSeriesSet` does:
```go
querier, err := h.queryable.ChunkQuerier(query.StartTimestampMs, query.EndTimestampMs)
...
defer func() { querier.Close() ... }()
...
return querier.Select(ctx, true, hints, filteredMatchers...)
```
Because the `defer` fires when the function returns, `querier.Close()` has **already run** by the time `remoteReadStreamedXORChunks` receives the `ChunkSeriesSet` and hands it to `StreamChunkedReadResponses` for iteration. This is only safe if `Select()` eagerly materializes all chunk data. It does not — I traced the full call chain in this repo:

1. `tsdb.DB.ChunkQuerier` (the queryable actually wired into `NewReadHandler` via `web/api/v1/api.go:277`) returns `storage.NewMergeChunkQuerier(blockQueriers, ...)` over per-block `blockChunkQuerier`s (`tsdb/db.go:2067-2073`).
2. `blockChunkQuerier.Select` (`tsdb/querier.go:174-196`) returns `NewBlockChunkSeriesSet(q.blockID, q.index, q.chunks, ...)` — the returned series set holds a live reference to `q.chunks` (the block's `ChunkReader`), the exact same object `blockBaseQuerier.Close()` closes (`tsdb/querier.go:103-115`).
3. Actual chunk-byte access is lazy: `populateWithDelGenericSeriesIterator.next()` calls `p.cr.ChunkOrIterable(p.currMeta)` (`tsdb/querier.go:721`) only when the series set's `Next()`/iterator is driven — i.e. inside `StreamChunkedReadResponses`'s `for ss.Next() { ... iter.At() ... }` loop (`storage/remote/codec.go:235-262`), which runs **after** `getChunkSeriesSet` has already returned and closed the querier.
4. For on-disk (compacted) blocks, `chunks.Reader.ChunkOrIterable` (`tsdb/chunks/chunks.go:665-704`) does a **zero-copy** wrap of the mmap'd segment bytes (`chunkenc.Pool.Get` at `tsdb/chunkenc/chunk.go:305-311` sets `c.b.stream = b` directly, no copy) and CRC32-validates those bytes in the same call — i.e. it touches the mapped memory synchronously.
5. `chunks.Reader.Close()` (`tsdb/chunks/chunks.go:656-658`) calls `tsdb_errors.CloseAll(s.cs)`, and each closer is an `*fileutil.MmapFile`, whose `Close()` calls `munmap(f.b)` (`tsdb/fileutil/mmap.go:56-64`) — this unmaps the memory region.

Put together: for any streamed remote-read query that touches a persistent (on-disk) block, `StreamChunkedReadResponses` reads chunk bytes out of a memory region that has **already been `munmap`'d** by the time it's read. This is a classic use-after-free at the OS level.

There is a second, independent instance of the same root cause for head (in-memory) data: `NewRangeHead`/`headChunkReader` carries an `isolationState` that registers the query in `Head`'s `readsOpen` list so that concurrent `Head.Truncate`/GC won't evict chunks the query is still reading (`tsdb/head.go:1180`, comment at `tsdb/db.go:2022-2024`: "registers itself in the queue that the truncation waits on"). `headChunkReader.Close()` (`tsdb/head_read.go:318-323`) calls `isoState.Close()`, unregistering that protection. Because `getChunkSeriesSet` closes this before `StreamChunkedReadResponses` has consumed the data, the isolation guard is released while the read is still in flight, opening a race with concurrent head truncation.

**Why Critical:** Forward: closing the querier makes its `Close()`d resources → the returned `ChunkSeriesSet` is consumed later, lazily, through those same resources → therefore chunk reads run on unmapped memory / against a released truncation guard, which is memory-unsafe (on Linux, access to an unmapped page typically surfaces as a Go runtime **fatal error/SIGSEGV**, which — unlike a panic — is unrecoverable and takes down the whole process, not just the request; I did not execute a live repro of the crash signature itself, so the exact runtime manifestation is [Inference], but the resource-lifecycle violation producing it is directly verified from the code). Backward: for a maintainer to hit this, they need any streamed chunked-read request that reads data from a compacted on-disk block (or races a head truncation) — this is the ordinary, non-broken case for any remote-read spanning historical data, not an edge case. Both directions hold, so this stays Critical rather than being downgraded.

This also means the PR's stated goal is not actually achieved: chunk data is still read throughout the full duration of `StreamChunkedReadResponses` (including while blocked on a slow/broken client's socket, the exact scenario the commit message cites) — the change does not shorten how long those resources are needed, it just makes the handle to them invalid earlier, trading a resource-hold problem for a memory-safety problem.

I ran the existing `TestStreamReadEndpoint` (`storage/remote/read_handler_test.go`) as a targeted, read-only probe — it passes, but its fixture data (`promql.LoadedStorage` with `load 1m ...`) lives entirely in the head and is never compacted to an on-disk block, so it never exercises the mmap'd `chunks.Reader` path described above; this is consistent with the bug being real but uncovered by current tests, not evidence against it.

**Fix:**
```go
// Return the querier (or keep it open) and close it in the caller,
// only after StreamChunkedReadResponses has fully consumed the set —
// mirroring the existing safe pattern in remoteReadSamples.
func (h *readHandler) getChunkSeriesSet(ctx context.Context, query *prompb.Query, filteredMatchers []*labels.Matcher) (storage.ChunkQuerier, storage.ChunkSeriesSet) {
	querier, err := h.queryable.ChunkQuerier(query.StartTimestampMs, query.EndTimestampMs)
	if err != nil {
		return nil, storage.ErrChunkSeriesSet(err)
	}
	var hints *storage.SelectHints
	if query.Hints != nil {
		hints = &storage.SelectHints{ /* ... */ }
	}
	return querier, querier.Select(ctx, true, hints, filteredMatchers...)
}

// in remoteReadStreamedXORChunks:
querier, chunks := h.getChunkSeriesSet(ctx, query, filteredMatchers)
if querier != nil {
	defer func() {
		if err := querier.Close(); err != nil {
			level.Warn(h.logger).Log("msg", "Error on chunk querier close", "err", err.Error())
		}
	}()
}
if err := chunks.Err(); err != nil {
	return err
}
// ... StreamChunkedReadResponses(...) as before, still within this closure ...
```
If the actual intent is to bound memory/resource hold time for broken/slow clients, that needs a different mechanism (e.g. a write/iteration deadline or byte budget on the stream), not an early `Close()` on a lazily-consumed series set.

**Actionability Check:**
- [x] Fix specifies exact change
- [x] Fix requires no additional decisions (aside from optionally addressing the stated OOM goal via a separate mechanism, called out explicitly)

---

### 🟠 High: New comment on `getChunkSeriesSet` documents a false safety guarantee

| | |
|---|---|
| **File** | `storage/remote/read_handler.go:239-241` |
| **Category** | KNOWLEDGE_LOSS / COMPREHENSION_RISK |
| **Confidence** | 100 |
| **Pre-existing** | no — introduced by this changeset |

**Issue:** The doc comment reads: `"getChunkSeriesSet executes a query to retrieve a ChunkSeriesSet, encapsulating the operation in its own function to ensure timely release of the querier resources."` This states the extraction *ensures* correct, timely resource release. As shown in the Critical finding above, it does the opposite for the actual production storage backend (`tsdb.DB`): it releases the querier's resources (mmap'd chunk readers, head isolation registration) *before* they are used, not "timely" but premature. A future maintainer reading this comment has no reason to suspect the lazy-iteration hazard and would reasonably copy this exact pattern (helper-returns-a-lazy-set-after-deferred-Close) elsewhere in the codebase, propagating the same bug.

**Why High:** This is a documented rationale that is factually wrong about the very property it claims to guarantee (correct resource lifecycle), which is exactly the kind of institutional-knowledge loss that misleads rather than informs; it doesn't meet the dual-path bar for Critical on its own (the comment itself doesn't crash anything — the code does), so it's filed as High rather than Critical.

**Fix:** Once the resource-lifecycle bug is fixed (see the Critical finding), rewrite the comment to state what the helper actually does and why (e.g., "centralizes hint construction; the caller is responsible for closing the returned querier only after the ChunkSeriesSet has been fully consumed, since chunk reads happen lazily during iteration"). Do not merge a comment claiming "timely release" is safe until the lazy-consumption hazard is actually resolved.

**Actionability Check:**
- [x] Fix specifies exact change
- [x] Fix requires no additional decisions

---

## Considered But Not Flagged

- **`chunks.Err()` / `ss.Warnings()` calls after the querier is closed** — these are cheap accessors over already-computed state (postings resolution errors / annotations gathered during `Select()`), not chunk-byte reads; they don't touch the closed `ChunkReader`/mmap and are not part of the hazard. Anchor 75 that they're safe, but not a finding since there's no defect.
- **Duplicated `SelectHints` construction between `remoteReadSamples` and `getChunkSeriesSet`** — this block-copy already existed identically in both functions before this PR (verified via `git show 5309112`, which introduces the file with both copies present at introduction); the extraction didn't create or worsen this duplication in a way attributable to this changeset. Pre-existing, not flagged.
- **`Select(ctx, true, hints, ...)` being called with a `ctx` that could already be near cancellation by the time it's consumed** — plausible but speculative without a live reproduction of client-cancellation timing; anchor 25, not reported.
- **`storage.ErrChunkSeriesSet(err)` early-return path when `ChunkQuerier()` itself fails** — no querier exists in that branch, so there's nothing to close prematurely; this path is unaffected by the finding above.

## Positive Observations

- `remoteReadSamples` (the sibling, non-streamed path) gets this exactly right: `querier.Select(...)` is fully drained into a materialized `*prompb.QueryResult` via `ToQueryResult` (which copies every sample via `iter.At()` into `prompb.Sample`/`prompb.Histogram` slices) *inside* the same closure that holds the `defer querier.Close()`, so the resource is never touched after release. This is a good reference implementation for what the streamed path needs to preserve.
- Error handling and logging conventions (`level.Warn` on `Close()` errors, `HTTPError` type-switch translation) are consistent between the new helper and the rest of the file.
- The motivation behind the change (avoid holding heavy query resources open for the duration of a slow/broken streaming client) is a legitimate, real concern worth solving — it's the specific mechanism chosen (`defer Close()` inside a helper that returns a lazily-consumed iterator) that's unsound, not the goal itself.
