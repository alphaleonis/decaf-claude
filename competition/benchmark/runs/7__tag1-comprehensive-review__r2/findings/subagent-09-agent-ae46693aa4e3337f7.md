# subagent agent-ae46693aa4e3337f7

## Edge Case Analysis

### Pass 1: Path Walk

Traced 2 functions across 1 file (`storage/remote/read_handler.go`): `remoteReadStreamedXORChunks` (the per-query closure inside its loop) and the new `getChunkSeriesSet` helper. Found 4 branching constructs: querier-creation error vs. success, `query.Hints` nil vs. non-nil, `chunks.Err()` error vs. nil, and `StreamChunkedReadResponses` error vs. nil. 1 candidate identified in Pass 1 (the defer/lazy-consumption interaction); confirmed as a finding after Pass 2 by tracing the actual concrete `ChunkQuerier` implementation used in this codebase (not speculation about Go semantics in the abstract).

### Pass 2: Validated Findings

#### Critical

- **[Resource cleanup gap / use-after-close]** `getChunkSeriesSet` closes the querier (and the mmap-backed chunk/index/tombstone readers it owns) via `defer` at its own return — before the caller ever iterates the `ChunkSeriesSet` it returns — `storage/remote/read_handler.go:247-251,265` (consumed at `storage/remote/read_handler.go:205-214`)
  - **Unhandled path:** `querier.Select(ctx, true, hints, filteredMatchers...)` (line 265) is lazy: it eagerly evaluates postings (`PostingsForMatchers`, in `tsdb/querier.go:182`) but returns a `blockChunkSeriesSet`/`chunkSeriesEntry` that stores a direct reference to the querier's `ChunkReader` (`tsdb/querier.go:1158-1171`, `tsdb/querier.go:1173-1180`) and only reads actual chunk bytes lazily, on `Next()`/`At()`/`Iterator()`. The Go `defer` in `getChunkSeriesSet` runs at that function's return — i.e., immediately after `Select()` produces the set, not after the set is drained. `defer querier.Close()` therefore executes before `StreamChunkedReadResponses` (`storage/remote/read_handler.go:210-218`) ever calls `ss.Next()`/`ss.At()`/`iter.At()`/`chk.Chunk.Bytes()` (`storage/remote/codec.go:235-261`).
  - **Consequence:** For any query that touches on-disk (non-head) blocks — the normal case for anything but the very latest in-memory samples — `querier.Close()` (`tsdb/querier.go:103-115`) closes the block's `chunks.Reader`, whose `Close()` (`tsdb/chunks/chunks.go:656-658`) closes the underlying `fileutil.MmapFile`s, which calls `munmap` (`tsdb/fileutil/mmap.go:56-58`). The chunk bytes handed back by `Reader.ChunkOrIterable` (`tsdb/chunks/chunks.go:697-700`, `chkData := sgmBytes.Range(...)`) are a zero-copy slice directly into that mmap'd region — no copy is made. When `StreamChunkedReadResponses` later calls `chk.Chunk.Bytes()` to serialize the frame, it reads from memory that has already been unmapped, producing a crash (SIGSEGV/fatal runtime error) or, best case, corrupted/garbage chunk data silently streamed to the remote-read client — this can occur partway through streaming a large response, after some frames have already been flushed to the client. The `mergeGenericQuerier` composing multiple on-disk block queriers (`storage/merge.go:255-263`, used by `tsdb.DB.ChunkQuerier` at `tsdb/db.go:2067-2073`) makes this apply to essentially any remote-read query spanning more than the head block.
  - **Remediation:** Don't close the querier inside `getChunkSeriesSet`. Either return the querier alongside the `ChunkSeriesSet` and defer `Close()` in the outer per-query closure (after `StreamChunkedReadResponses` returns), or restructure `getChunkSeriesSet` to fully materialize/copy the series data before closing the querier, so the caller never touches querier-owned resources after they're released.
  - **Confidence:** 90/100

### Positive Observations

- The querier-creation error path (`storage.ErrChunkSeriesSet(err)` at line 245) is fully handled: no querier exists yet to leak/close, `chunks.Err()` at line 206 correctly surfaces it, and `StreamChunkedReadResponses` is never invoked in that case.
- The `query.Hints == nil` vs. non-nil branch (lines 253-264) has no gap — both paths correctly feed into `Select`, and `hints` remaining `nil` is a valid, accepted value for `Select`.
- Each loop iteration (`for i, query := range req.Queries`) creates and releases its own querier independently via a fresh `getChunkSeriesSet` call — no cross-iteration accumulation/leak of querier handles.

```json-findings
[{"severity":"Critical","confidence":90,"category":"edge-case","file":"storage/remote/read_handler.go","line":247,"finding":"getChunkSeriesSet's defer closes the ChunkQuerier (and its mmap-backed block readers) at the helper's own return, before the caller iterates the lazily-evaluated ChunkSeriesSet it returns via StreamChunkedReadResponses, causing reads of unmapped memory for any query touching on-disk blocks.","remediation":"Keep the querier open until StreamChunkedReadResponses has fully consumed the ChunkSeriesSet — return the querier alongside the set and defer Close() in the outer per-query closure, or fully materialize series data before closing.","source":"edge-case-hunter"}]
```
