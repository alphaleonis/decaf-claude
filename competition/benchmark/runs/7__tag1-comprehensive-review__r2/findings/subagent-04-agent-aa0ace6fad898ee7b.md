# subagent agent-aa0ace6fad898ee7b

I have enough evidence. Let me verify the samples-path contrast one more detail is unnecessary — the picture is clear. Writing up findings.

## Architectural Analysis

### Design Assessment

The change extracts querier acquisition + `Select` into `getChunkSeriesSet` so the deferred `querier.Close()` fires when the helper returns. This is a clean-looking refactor, but it inverts a load-bearing invariant: the returned `storage.ChunkSeriesSet` is *lazy*, and it is consumed by `StreamChunkedReadResponses` only *after* the helper has already closed the querier that owns the data it reads from. The refactor couples the querier's lifetime to a stack frame that the produced value outlives, which is architecturally unsound for the TSDB-backed path.

### Findings

#### Critical

- **[coupling / resource ownership]** Querier lifetime is bound to `getChunkSeriesSet`'s stack frame, but the `ChunkSeriesSet` it returns is consumed lazily after the frame (and its `defer Close`) has unwound — `storage/remote/read_handler.go:242-266`, consumed at `:205-218`.
  - Why it matters: `getChunkSeriesSet` returns `querier.Select(...)` (line 265) with `defer querier.Close()` (lines 247-251). The deferred close runs when the helper returns — *before* `StreamChunkedReadResponses` iterates the set (`storage/remote/codec.go:235-296`, which drives `ss.Next()/At()/iter.At()/chk.Chunk.Bytes()` lazily). The in-tree TSDB implementation is demonstrably lazy: `blockChunkQuerier.Select` returns `NewBlockChunkSeriesSet(..., q.chunks, ...)` holding the querier's chunk reader (`tsdb/querier.go:174-196`), `At()` hands that same reader to each `chunkSeriesEntry` (`tsdb/querier.go:1173-1180`), and `blockBaseQuerier.Close()` closes exactly that reader (`q.chunks.Close()`, `tsdb/querier.go:103-115`). So chunk bytes are pulled from a reader that has already been closed — a use-after-close. Contrast the samples path (`remoteReadSamples`), which fully materializes via `ToQueryResult(querier.Select(...))` *inside* the closure before the deferred `Close` runs (`read_handler.go:161`); the new chunk helper breaks that symmetry. The correctness of this design silently depends on an unstated, unenforced assumption that every `queryable` returns an eagerly-materialized set holding no live references to querier resources — an assumption the `ChunkSeriesSet` interface contract (`storage/interface.go:436-446`) never makes and the TSDB violates.
  - Recommendation: Do not close the querier before the set is consumed. Either (a) keep `Select` and consumption inside one scope — pass a closure to run while the querier is open (`func run(ss storage.ChunkSeriesSet) error`), so `Close` defers around the streaming call; or (b) return the querier/closer to the caller as `(storage.ChunkSeriesSet, io.Closer, error)` and defer `Close` in `remoteReadStreamedXORChunks` around `StreamChunkedReadResponses`. Rejected alternative — "leave as-is because the current queryable happens to materialize": rejected because nothing in the interface guarantees this and the primary in-tree implementation does not, so the invariant will silently break as queryables evolve.
  - Confidence: 80/100

#### Medium

- **[public API / interface design]** The `ErrChunkSeriesSet`-as-error-channel shape conflates querier-acquisition failure with query-execution outcome and forecloses lifetime management by the caller — `storage/remote/read_handler.go:242-246`.
  - Why it matters: Folding the acquisition error into `storage.ErrChunkSeriesSet(err)` (line 245) so the caller can uniformly check `chunks.Err()` (line 206) is neat, but it also swallows the `querier` handle entirely. The caller has no way to observe, extend, or scope the querier's lifetime — which is precisely why the close had to be pulled *inside* the helper, creating the problem above. A signature that returns the closer, or a loan/callback pattern, keeps acquisition errors distinct from iteration errors *and* returns lifetime control to the caller. This is the evolution-safety weakness: any future need to keep the querier open during streaming (the actual requirement here) forces re-architecting this helper rather than extending it.
  - Recommendation: Prefer `(storage.ChunkSeriesSet, io.Closer, error)` or a `withChunkSeriesSet(ctx, query, matchers, func(ss) error) error` loan method. Keep `ErrChunkSeriesSet` only for the genuinely lazy in-band error case, not as a substitute for returning the acquisition error and closer.
  - Confidence: 78/100

- **[maintainability]** The doc comment states an intent that is the opposite of what is safe — `storage/remote/read_handler.go:239-241`.
  - Why it matters: "encapsulating the operation in its own function to ensure timely release of the querier resources" tells a future maintainer the early release is the *goal*, hiding that the release is premature relative to the lazy consumer. Anyone trusting this comment will not realize the returned set must be fully materialized before return. If the design in finding 1 is kept for a specific eager queryable, the comment must document that hard precondition instead.
  - Recommendation: Replace the comment with the actual invariant the code relies on (e.g., "the returned set must be fully materialized; the querier is closed on return, so lazy sets that read from querier resources are unsafe here"), or remove the early-close design per finding 1.
  - Confidence: 76/100

### Positive Observations

- Unifying acquisition and query errors behind `chunks.Err()` reduces branching at the call site and mirrors how `Select` already surfaces errors in-band via `ErrChunkSeriesSet` — a reasonable local idiom.
- Extracting the `hints` construction and `Select` call out of the loop body improves readability of `remoteReadStreamedXORChunks`.

### Recommendations

1. Address finding 1 before merge: move `querier.Close()` so it defers around the *consumption* of the set (closure/loan pattern) or hand the closer back to the caller. As written, the TSDB-backed path reads chunk bytes from a closed reader.
2. Reshape the helper to `(ChunkSeriesSet, io.Closer, error)` or a callback form so the querier lifetime is caller-controlled and acquisition errors stay distinct from iteration errors.
3. Correct the doc comment to state the real precondition (full materialization) rather than "timely release."

```json-findings
[{"severity":"Critical","confidence":80,"agent":"architecture-reviewer","file":"storage/remote/read_handler.go","line":265,"finding":"getChunkSeriesSet closes the ChunkQuerier via defer-on-return (lines 247-251) but returns a lazy storage.ChunkSeriesSet that StreamChunkedReadResponses consumes afterward. The in-tree TSDB blockChunkQuerier.Select returns a set holding the querier's chunk reader (tsdb/querier.go:174-196, 1173-1180), which blockBaseQuerier.Close() closes (tsdb/querier.go:103-115). Iterating the set therefore reads chunk bytes from an already-closed reader (use-after-close). Correctness silently depends on an unstated assumption that Select eagerly materializes, which the ChunkSeriesSet contract does not guarantee and the TSDB violates. Contrast the samples path, which materializes via ToQueryResult before Close.","remediation":"Do not close the querier before the set is consumed: pass a closure that runs while the querier is open, or return (ChunkSeriesSet, io.Closer, error) and defer Close in remoteReadStreamedXORChunks around StreamChunkedReadResponses.","category":"architecture-coupling"},{"severity":"Medium","confidence":78,"agent":"architecture-reviewer","file":"storage/remote/read_handler.go","line":242,"finding":"The helper returns only a ChunkSeriesSet (folding acquisition errors into ErrChunkSeriesSet), swallowing the querier handle so the caller cannot manage querier lifetime. This error-channel shape conflates acquisition failure with query execution and is the direct cause of the premature-close design; it is not evolution-safe — any need to keep the querier open during streaming forces re-architecting the helper.","remediation":"Return (storage.ChunkSeriesSet, io.Closer, error) or use a loan/callback form withChunkSeriesSet(ctx, query, matchers, func(ss) error) error so acquisition errors stay distinct and querier lifetime is caller-controlled.","category":"architecture-coupling"},{"severity":"Medium","confidence":76,"agent":"architecture-reviewer","file":"storage/remote/read_handler.go","line":239,"finding":"The doc comment claims the helper exists 'to ensure timely release of the querier resources,' but the release is premature relative to the lazy consumer, actively misleading a future maintainer into thinking early close is the goal rather than a hazard requiring full materialization.","remediation":"Restate the actual precondition (the returned set must be fully materialized before return; lazy sets reading from querier resources are unsafe) or remove the early-close design.","category":"docs"}]
```
