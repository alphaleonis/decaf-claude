# subagent agent-ab5ba2199d3095a47

## Finding

**Closing the ChunkQuerier before the stream consumes it caused a production segfault; this exact PR was later reverted.**

- **File/line:** `storage/remote/read_handler.go:242` (the new `getChunkSeriesSet` function; the problematic `defer querier.Close()` is at line 248, consumed by `StreamChunkedReadResponses` at line 210-217)
- **Verdict:** CONFIRMED

**Details:** This is not a hypothetical concern — PR #13777 (the one under review) was merged, ran in production for ~4 months, and was then reverted in [PR #14515](https://github.com/prometheus/prometheus/pull/14515) (revert commit `6e89250a5d`) because it caused SIGSEGV crashes.

`getChunkSeriesSet` calls `querier.Select(...)` to obtain a `ChunkSeriesSet` and then closes the querier via `defer` as soon as `Select` returns — before the caller (`remoteReadStreamedXORChunks`, line 210) has iterated a single series through `StreamChunkedReadResponses`. The `ChunkSeriesSet`'s iterators lazily access memory-mapped TSDB block/chunk data owned by that querier, so closing it early can unmap data still being read mid-stream.

[Issue #14422](https://github.com/prometheus/prometheus/issues/14422) reported this in production (v2.53.0, >1M series instances), with a crash occurring right after block writes:
```
fatal error: fault [signal SIGSEGV ...]
encoding/binary.Uvarint(...)
tsdb/chunks.(*Reader).ChunkOrIterable
tsdb.(*populateWithDelChunkSeriesIterator).Next
storage.(*compactChunkIterator).Next
storage/remote.StreamChunkedReadResponses (codec.go:246)
storage/remote.(*readHandler).remoteReadStreamedXORChunks.func1 (read_handler.go:210)
```

The revert PR's body (by bboreham) states: *"I believe the iterators for the querier can access memory-mapped files, which are closed when the querier is closed. A better fix might be to reference-count the chunk-reader so it is only closed when no longer accessed."* Operators confirmed the revert fixed the crashes ("Haven't seen any crashes in >2d" — issue #14422 comments), and the original author (roidelapluie) approved the revert of his own PR. No subsequent PR reintroduced early-close with the suggested reference-counting fix — the file history shows no further attempt at this optimization.

This means PR #13777, as currently written, reintroduces a change that has a documented production-crash history and an unresolved root cause (mmap'd chunk data being invalidated mid-stream).
