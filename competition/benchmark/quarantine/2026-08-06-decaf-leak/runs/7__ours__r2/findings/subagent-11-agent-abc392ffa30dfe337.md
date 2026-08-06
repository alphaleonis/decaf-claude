# subagent agent-abc392ffa30dfe337

## Performance Review — PR #13777 "Chunked remote read: close the querier earlier"

**Files examined:** `/home/decaf/code/decaf-claude/competition/benchmark/repos/7/storage/remote/read_handler.go`, `storage/remote/codec.go`, `tsdb/querier.go`, `tsdb/block.go`, `tsdb/head_read.go`, `tsdb/isolation.go`, `storage/merge.go`, `tsdb/db.go`, `web/web.go`

### Grounding the mechanism

I traced what `querier.Close()` actually releases, since the querier doesn't hold accumulated chunk bytes (those are read lazily by `series.Iterator()` inside `StreamChunkedReadResponses`, `storage/remote/codec.go:237`, which still runs *after* the new `defer querier.Close()` in `getChunkSeriesSet`):

- For persistent blocks: `blockChunkReader.Close()` / `blockIndexReader.Close()` (`tsdb/block.go:537,558,568`) just call `pb.pendingReaders.Done()` — a refcount that gates `Block.Close()` (`tsdb/block.go:378-390`), which compaction/retention use to actually unmap/delete a superseded block.
- For Head-range queriers: `headChunkReader.Close()` (`tsdb/head_read.go:318-322`) closes the isolation state, which advances the low watermark (`tsdb/isolation.go:106-114`) that gates `Head.gc()`/truncation from reclaiming obsolete series/chunks.

So the fix is legitimate: it unpins these two refcounts earlier, letting concurrent compaction/retention/GC proceed even while a slow/broken client is still being streamed to. That part of the OOM story checks out.

### Finding reported (High, confidence 75)

The reported finding is that this only addresses the *secondary* symptom (GC/compaction being blocked). The *primary* per-connection cost — the live `ChunkSeriesSet` (postings iterator, in-flight chunk state) kept alive by a blocked `stream.Write()` in `StreamChunkedReadResponses` (`codec.go:283`) — is untouched. I verified the HTTP server (`web/web.go:249,618`) configures only `ReadTimeout`, no `WriteTimeout`/write-deadline anywhere on this path. At the default `remote-read-concurrency-limit` of 10 (`cmd/prometheus/main.go:406`), up to 10 concurrent broken clients can each hold this state open indefinitely — which is the literal "broken chunked remote read requests" scenario the commit message describes. Suggested fix: bound the stall with a write deadline (`http.ResponseController.SetWriteDeadline`) or periodic `ctx.Err()` checks in the streaming loop.

## Considered But Not Flagged

- **Extra function-boundary/duplicated `hints` struct construction in `getChunkSeriesSet`** — a single struct allocation per query (bounded by `req.Queries`), not per-row/per-series. Negligible; anchor 0.
- **Mechanism validity of the fix itself (pendingReaders / isolation low-watermark release)** — confirmed real and beneficial via direct code reading (not merely the querier "holding little memory to begin with" — it holds a lifecycle refcount, not bulk data). This is a positive confirmation, not a cost finding, so not reported as a separate item; folded into the rationale of the one finding above.
- **Use-after-"close" read of chunk/index data after `querier.Close()`** — `blockChunkReader`/`headChunkReader` remain functionally readable post-Close in the common case (the real close only happens via `Block.Close()`, gated by the same refcount this PR releases early), so this is a potential correctness/race concern if compaction actually proceeds concurrently with in-flight iteration — out of scope for this persona (belongs to quick-reviewer/adversarial-reviewer as a lifetime-safety/race question), mentioned here only as context for the primary finding's grounding.
- **`chunks.Err()` check added before streaming** — trivial, cold-path, no measurable cost at any scale.
