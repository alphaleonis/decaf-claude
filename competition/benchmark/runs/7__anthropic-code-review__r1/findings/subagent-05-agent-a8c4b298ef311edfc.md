# subagent agent-a8c4b298ef311edfc

## Summary

The exact concern you're investigating was **not caught during PR #13777's review**, but it later caused production SIGSEGV crashes and the change was **reverted three months later**. This is a directly on-point precedent, not just a related concern.

### PR #13777's own review — nothing caught the problem

- The PR had a single review, from `machine424`: *"Good catch! Clearer, indeed."* — approving without commenting on querier/mmap lifetime. (https://github.com/prometheus/prometheus/pull/13777)
- PR #13777 is explicitly described as *"alternative to #13762"* — an earlier attempt at the same change by the same author (`roidelapluie`), which was closed unreviewed. In #13762 the author himself wrote: *"Maybe I can totally split that to another function to clarify that the goal is to call the defer asap."* (https://github.com/prometheus/prometheus/pull/13762#issuecomment-1996998312) — confirming the intent was exactly what this diff does: call `querier.Close()` (the `defer`) as soon as possible, i.e. immediately after `Select()` returns rather than after the `ChunkSeriesSet` is consumed. Neither PR's discussion considered whether `Select()` is lazy and whether the returned iterator still depends on querier-owned resources after `Close()`.

### It was reverted — issue #14422 / PR #14515

- **Issue #14422**, "SIGSEGV after writing block" (opened 2024-07-05): production Prometheus 2.53 crashed with `SIGSEGV` inside `tsdb/chunks.(*Reader).ChunkOrIterable` while streaming a remote-read response, always right after a block was written/mmap'd. Stack trace goes through `storage/remote.(*readHandler).remoteReadStreamedXORChunks` → `StreamChunkedReadResponses` → `compactChunkIterator.Next` → `populateWithDelChunkSeriesIterator.Next` → `chunks.Reader.ChunkOrIterable`.
- A community member (`fbs`) bisected the regression to exactly this commit: *"commit 53091126c28f518c154c365a47d617c9ee7634de <-- the one you reverted"* — i.e., PR #13777's merge.
- Maintainer `bboreham` diagnosed it: *"I theorise that closing the querier closes the memory-mapped file, which then makes it possible to get a memory fault."* (https://github.com/prometheus/prometheus/issues/14422#issuecomment-2252253613) and *"a new block would be a reason for Linux to be changing memory mappings which could invalidate memory that otherwise contained useable data."*
- **PR #14515**, "Revert 'Chunked remote read: close the querier earlier'" (merged 2024-07-29): *"Reverts prometheus/prometheus#13777. Fixes #14422. I believe the iterators for the querier can access memory-mapped files, which are closed when the querier is closed. A better fix might be to reference-count the chunk-reader so it is only closed when no longer accessed."* — approved by `roidelapluie` (the original author) himself.
- Backported to release branches: **#14523** (2.53) and **#14524** (2.54); a fixed 2.53.2 was released because 2.53 is an LTS branch.
- `machine424` (who had approved #13777) later wrote on the issue: *"Nice catch! Thanks for this. It'd be great to have a regression test for this, I'll think about one."* and added one in **PR #14599**, `TestBlockClosingBlockedDuringRemoteRead` (`tsdb/db_test.go`), which asserts that closing a TSDB block blocks while the remote-read streaming handler is still reading from it — i.e. blocks have reference-counted "pending readers" and querier `Close()` is exactly what's supposed to release that reference, so releasing it before the `ChunkSeriesSet` is drained defeats the mechanism that keeps mmap'd chunk data alive during the stream.

### Applicability to the current change

The diff you're reviewing (`getChunkSeriesSet` helper, `storage/remote/read_handler.go`) is functionally identical to what #13777 did: `querier.Close()` runs via `defer` when `getChunkSeriesSet` returns — i.e., immediately after `querier.Select(...)` — **before** the returned `storage.ChunkSeriesSet` is iterated by `StreamChunkedReadResponses` later in `remoteReadStreamedXORChunks`. Since `Select()` on TSDB queriers is lazy (returns iterators, doesn't materialize chunk bytes), closing the querier at that point releases the underlying block's mmap reference while later iteration still dereferences it — the exact defect diagnosed in #14422 and reverted in #14515.

If this PR is (re-)introducing this pattern, it reintroduces a known, previously-shipped, production-crashing bug (LTS-backported fix). The safe pattern — confirmed by the revert — is to keep the querier open (and `defer querier.Close()` at the same scope as the consumer) until `StreamChunkedReadResponses` has fully drained the `ChunkSeriesSet`, or to adopt the reference-counting fix `bboreham` suggested instead of closing early.

### Files/lines of interest
- `storage/remote/read_handler.go` — the `getChunkSeriesSet` extraction (current PR) and the equivalent `defer querier.Close()` block in `remoteReadStreamedXORChunks` (pre-#13777 / post-#14515 code).
- `tsdb/db_test.go` (added by PR #14599) — `TestBlockClosingBlockedDuringRemoteRead`, the regression test that would catch this exact pattern; worth checking whether the current change still passes it, or whether it was itself reverted/removed alongside this PR.
