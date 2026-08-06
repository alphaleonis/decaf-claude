# subagent agent-a2e501b33f72831ba

## Sibling-Consistency Review — `storage/remote/read_handler.go`

**Sibling census.** The file has two per-query handlers with a historically identical construction sequence (querier → hints → `Select`): `remoteReadSamples` (lines 117-187, untouched by this diff) and `remoteReadStreamedXORChunks` (lines 189-237, refactored). I diffed against the pre-PR version (commit `d1abc3f~1`) to separate genuinely new drift from content that was merely relocated unchanged.

Verified via `git diff d1abc3f~1 d1abc3f -- storage/remote/read_handler.go`: the hints-building block and the `"Error on chunk querier close"` log message are **byte-identical** to the pre-PR inline code — they were moved into `getChunkSeriesSet`, not altered. The only functionally new element is the querier-creation error path, which switched from `return err` to `return storage.ErrChunkSeriesSet(err)` — this matches the established codebase convention for lazily-erroring `SeriesSet`/`ChunkSeriesSet` returns (`tsdb/querier.go:138` `storage.ErrSeriesSet(err)`, `tsdb/querier.go:187` `storage.ErrChunkSeriesSet(err)`, `storage/remote/read.go:165,170` `storage.ErrSeriesSet(...)`), so that is correct, not drift.

```json
[
  {
    "file": "storage/remote/read_handler.go",
    "line": 249,
    "severity": "Low",
    "category": "naming",
    "issue": "[CONS_NAMING] getChunkSeriesSet logs \"Error on chunk querier close\" while the sibling remoteReadSamples logs \"Error on querier close\" for the analogous querier.Close() failure (storage/remote/read_handler.go:143), so the two nearly-identical defer/close blocks in the same file use different message vocabulary for the same event.",
    "fix": "Align the log message text with the sibling (\"Error on querier close\") or, if the \"chunk\" qualifier is intentional, apply the same qualifier convention to the sample-path message for symmetry.",
    "confidence": 100,
    "pre_existing": true
  },
  {
    "file": "storage/remote/read_handler.go",
    "line": 205,
    "severity": "Low",
    "category": "design",
    "issue": "[CONS_SYMMETRY] remoteReadStreamedXORChunks now delegates its querier+hints+Select construction to the extracted getChunkSeriesSet helper (storage/remote/read_handler.go:205, 242-266), while the sibling remoteReadSamples still performs the identical construction pattern inline inside its per-query closure (storage/remote/read_handler.go:137-161). Before this change both paths used the same inline convention; the refactor leaves only one of the two sites following it, which a future maintainer could read as inconsistent structure for what is otherwise the same operation (build querier, build hints, call Select).",
    "fix": "If the sample path genuinely doesn't benefit from early-close (ToQueryResult fully drains the SeriesSet before the closure returns), consider a brief comment noting why only the chunk path needed extraction, so the asymmetry reads as intentional rather than incomplete.",
    "confidence": 75,
    "pre_existing": false
  }
]
```

## Considered But Not Flagged

- **Hints-building block duplicated between `remoteReadSamples` (lines 147-158) and `getChunkSeriesSet` (lines 253-264):** confirmed via `git diff` against the pre-PR version that this duplication already existed before the PR (both functions had separate inline copies); the PR only relocated the chunk-path copy verbatim. Not new drift, and duplication itself is a DRY/simplify concern, not a sibling-convention mismatch — both sides agree, they just agree redundantly. Outside this lane.
- **`return storage.ErrChunkSeriesSet(err)` on querier-creation failure (line 245) vs sibling's `return err` (line 138-140):** initially looked like an inconsistency, but verified it is the codebase's canonical pattern for propagating an error through a function whose return type is a lazy `SeriesSet`/`ChunkSeriesSet` rather than `error` — confirmed at `tsdb/querier.go:138`, `tsdb/querier.go:187`, and `storage/remote/read.go:165,170`. The change follows convention; not flagged.
- **Comment "The streaming API has to provide the series sorted." (line 213) now sits above the `chunks` variable rather than the `querier.Select(ctx, true, ...)` call where the `sortSeries=true` decision now actually lives (getChunkSeriesSet:265):** the comment is still accurate where it sits (chunks passed to StreamChunkedReadResponses must be sorted), so it doesn't contradict the code it's attached to — it's a comprehension/context-loss concern (comment separated from the decision it explains), which is knowledge-reviewer's domain, not a sibling-convention mismatch.
- **Doc comment style of `getChunkSeriesSet` ("// getChunkSeriesSet executes a query to retrieve a ChunkSeriesSet...")**: checked against sibling doc comments in the same file — `NewReadHandler` ("// NewReadHandler creates a http.Handler...", line 47-48) and `filterExtLabelsFromMatchers` ("// filterExtLabelsFromMatchers change equality matchers...", line 268-270) — both start with the function name per Go convention; the new comment matches this. No drift.
- **Naming of the new helper `getChunkSeriesSet`:** no other `getXxxSeriesSet`-style helper exists elsewhere in the repo to compare against (grep confirms only one hit, itself); first-of-kind, nothing to cite.
- **Error-check shadowing style `if err := chunks.Err(); err != nil` (line 206) vs plain `if err != nil` reuse elsewhere in the same closure:** both are idiomatic Go and consistent with how `remoteReadSamples`'s closure structures its own error checks (e.g. lines 133-135, 162-164); no meaningful deviation.
