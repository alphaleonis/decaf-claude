# subagent agent-af5d758b504c6c735

# Sibling-Consistency Review: `storage/remote/read_handler.go` (PR #13777)

## Sibling Census

True siblings for this change are the other functions in `storage/remote/read_handler.go` and its companion `storage/remote/read.go` (same package, same job class — building/returning `SeriesSet`/`ChunkSeriesSet` from a `Querier`):

- `remoteReadSamples` (read_handler.go:117-187) — the non-streamed twin of the changed path, same "create querier → defer Close → build hints → Select" shape.
- `remoteReadStreamedXORChunks` (read_handler.go:189-237) — caller of the new helper.
- `filterExtLabelsFromMatchers` (read_handler.go:271) — the file's other unexported package-level helper, carries a doc comment.
- `storage.ErrSeriesSet` / `storage.ErrChunkSeriesSet` (storage/interface.go:381,402) and their established use at `storage/remote/read.go:165,170` — the codebase's canonical pattern for smuggling an error through a lazy `SeriesSet`/`ChunkSeriesSet` return value.

## Comparison Sweep — the three requested points

**1. Querier lifetime asymmetry (intentional, not drift).**
`remoteReadSamples` closes its querier only after full consumption, inside the same closure:
```go
// read_handler.go:141-145
defer func() {
    if err := querier.Close(); err != nil { ... }
}()
...
// read_handler.go:161
resp.Results[i], ws, err = ToQueryResult(querier.Select(ctx, false, hints, filteredMatchers...), h.remoteReadSampleLimit)
```
`getChunkSeriesSet` closes its querier as soon as the helper returns, i.e. before the caller ever touches the `ChunkSeriesSet`:
```go
// read_handler.go:247-251, 265
defer func() {
    if err := querier.Close(); err != nil { ... }
}()
...
return querier.Select(ctx, true, hints, filteredMatchers...)
```
Confirmed via `git diff 1580922 d1abc3f -- storage/remote/read_handler.go`: before this PR, the streamed path had the *same* symmetric shape as `remoteReadSamples` (inline querier + defer Close + inline hints, closed only after `StreamChunkedReadResponses` had already consumed the set within the same closure). This PR deliberately breaks that symmetry, and says so in the new doc comment: `// getChunkSeriesSet executes a query to retrieve a ChunkSeriesSet, encapsulating the operation in its own function to ensure timely release of the querier resources.` (read_handler.go:239-241). Given the commit message ("close the queries used by the streamed remote read requests earlier" — the stated purpose of the whole PR) and the self-documenting comment, this asymmetry is **intentional, not accidental drift**. Whether closing before consumption is *safe* for the underlying `ChunkSeriesSet` implementation is a correctness/lifecycle question outside this lane (quick-reviewer/adversarial-reviewer/design-reviewer territory) — I flag the divergence here only to confirm it is deliberate, not a convention violation.

**2. Duplicated `hints` construction block.**
The block at read_handler.go:253-264 (`getChunkSeriesSet`) is byte-for-byte identical to read_handler.go:147-158 (`remoteReadSamples`). The pre-PR diff shows this duplication already existed: the identical block was already inline in the old `remoteReadStreamedXORChunks` before this PR simply relocated it into the new helper. So duplication of this literal block **is the established, pre-existing norm** in this file — this PR did not introduce new drift, it preserved existing practice while relocating code. A shared `buildSelectHints(*prompb.Query) *storage.SelectHints` extraction was a real opportunity, but since it was equally available (and equally skipped) before this PR, it's a general simplification opportunity rather than a consistency deviation caused by this changeset — out of my lane (would belong to `simplify`/design-reviewer if raised at all).

**3. Naming of the new helper vs. surrounding code.**

```json
[
  {
    "file": "storage/remote/read_handler.go",
    "line": 242,
    "severity": "Low",
    "category": "naming",
    "issue": "[CONS_NAMING] New helper `getChunkSeriesSet` uses a `get`-prefix, but every other helper/method in this exact file/package doing the same class of job (execute-a-query-and-return-a-set) is named for the action itself, without a `get` prefix: `remoteReadSamples` (read_handler.go:117), `remoteReadStreamedXORChunks` (read_handler.go:189), `filterExtLabelsFromMatchers` (read_handler.go:271), and the wrapped interface method itself, `Select` (storage/remote/read.go:141, read.go:236) — none of which use `Get`/`get`.",
    "fix": "Rename to something action-based matching the file's vocabulary, e.g. `selectChunkSeriesSet`, to mirror the `querier.Select(...)` call it wraps and the naming style of its siblings in this file.",
    "confidence": 75,
    "pre_existing": false
  }
]
```

## Considered But Not Flagged

- **Querier-close timing asymmetry** (getChunkSeriesSet closes before consumption vs. remoteReadSamples closes after) — examined in depth above. The doc comment at read_handler.go:239-241 and the commit message both explicitly state this is the deliberate purpose of the PR, so it is not unflagged drift; it is a documented, intentional design change. Whether it is *safe* for the ChunkSeriesSet implementation is a correctness question for another reviewer, not a consistency question — sibling comparison here confirms intent, it doesn't reveal a defect.
- **Duplicated `hints`-construction block** (read_handler.go:147-158 vs. 253-264) — confirmed via `git diff 1580922 d1abc3f` that this exact duplication existed before the PR (inline in the old `remoteReadStreamedXORChunks`). The PR relocated, not duplicated, the block. Duplication is the pre-existing norm here, so no new drift; missed-extraction is a general simplification opportunity, not sibling-consistency drift.
- **Error propagation via `storage.ErrChunkSeriesSet(err)`** (read_handler.go:245) instead of a `(ChunkSeriesSet, error)` return — looked like a possible deviation from `remoteReadSamples`'s plain `if err != nil { return err }` (read_handler.go:138-140), but this is in fact the established codebase idiom: `storage.ErrSeriesSet`/`storage.ErrChunkSeriesSet` are purpose-built (storage/interface.go:381,402) and already used identically at `storage/remote/read.go:165,170` to smuggle an error through a lazy set-typed return. Matches convention; not flagged.
- **Log message wording** ("Error on querier close" at read_handler.go:143 vs. "Error on chunk querier close" at read_handler.go:249) — appropriately differentiated (plain vs. chunk querier), not a deviation.
- **Doc comment present on `getChunkSeriesSet` but absent on sibling methods `remoteReadSamples`/`remoteReadStreamedXORChunks`** — technically an asymmetry, but it's *additional* documentation, not missing/misleading documentation; no plausible maintainer harm, so not reportable as drift (would be knowledge-reviewer's domain if anything, and there it'd be a non-issue since more docs is strictly fine).
- **`get`-prefix usage repo-wide** — grepped broadly (`tsdb/head.go`, `promql/engine.go`, `discovery/ovhcloud/vps.go`, etc.) and found `get`-prefixed functions are common elsewhere in this codebase. Those are all accessor/cache-lookup roles in unrelated packages, not siblings of `getChunkSeriesSet`'s "execute a query" role, so they don't invalidate the file-local naming finding above, but they do temper it to Low/confidence-75 rather than a hard rule violation.

### Probe Requests
None — all verification was done read-only via `git diff 1580922 d1abc3f -- storage/remote/read_handler.go` (to recover the true pre/post diff around a shallow-clone grafted commit) and `grep`/`git show`; no build or test probes needed for this consistency-only lane.
