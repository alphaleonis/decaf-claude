# subagent agent-a31d3338985d3d0be

I have traced the complete lifecycle chain and have all the evidence I need. Here are my complete findings.

---

## Review: PR #13777 "Chunked remote read: close the querier earlier"

**Scope reviewed:** the single changed file `storage/remote/read_handler.go` (extraction of `getChunkSeriesSet`), traced end-to-end through the storage/tsdb read path that backs it: `storage/interface.go`, `storage/merge.go`, `storage/lazy.go`, `storage/remote/codec.go`, `tsdb/db.go`, `tsdb/querier.go`, `tsdb/block.go`, `tsdb/head_read.go`. Handler wiring confirmed at `web/api/v1/api.go:277` (the queryable is the server's local storage, i.e. the TSDB).

---

### Critical

#### 1. Use-after-free / data race: the `ChunkQuerier` is closed before the lazy `ChunkSeriesSet` it returns is consumed
**Severity: Critical** · **Confidence: ~88**
`storage/remote/read_handler.go:242-266` (the whole helper), specifically the `defer querier.Close()` at `read_handler.go:247-251` firing before `return querier.Select(...)` at `read_handler.go:265` is streamed by the caller at `read_handler.go:210-218`.

The PR's premise is that wrapping the query in its own function ensures "timely release of the querier resources." But the returned `storage.ChunkSeriesSet` is **lazy** and reads its chunk bytes on demand *during streaming*, which now happens **after** the querier — and therefore the underlying block/head readers — has already been closed.

Chain of evidence:

- `getChunkSeriesSet` closes the querier via `defer` the instant it returns (`read_handler.go:247-251`), then hands the result to `StreamChunkedReadResponses` (`read_handler.go:210-218`).
- The querier is `db.ChunkQuerier` → `NewMergeChunkQuerier` (`tsdb/db.go:2072`). Its `Select` returns a `lazyGenericSeriesSet` (`storage/merge.go:118-121`, `146-149`) whose child block sets are themselves lazy.
- Each child is a `blockChunkSeriesSet` (`tsdb/querier.go:195`) that reads chunk bytes lazily during iteration: `populateWithDelGenericSeriesIterator.next` calls `p.cr.ChunkOrIterable(...)` at `tsdb/querier.go:721`, driven from `populateWithDelChunkSeriesIterator.Next` (`tsdb/querier.go:877-913`), which runs only when `StreamChunkedReadResponses` iterates (`storage/remote/codec.go:235-266`) and calls `chk.Chunk.Bytes()` (`codec.go:261`). For persistent blocks those bytes point straight into the block's memory-mapped chunk file — they are **not** copied.
- Closing the merge querier cascades `Close()` to every child (`storage/merge.go:255-259`). For a persistent block, `blockBaseQuerier.Close` (`tsdb/querier.go:103-115`) closes the `blockChunkReader`, whose `Close` is exactly `pb.pendingReaders.Done()` (`tsdb/block.go:567-568`).
- `pendingReaders` is the sole mechanism that keeps a block mapped while it is being read: `Block.Close()` sets `closing=true` then blocks on `pb.pendingReaders.Wait()` before unmapping (`tsdb/block.go:378-390`); `startRead` adds the ref (`tsdb/block.go:416-425`). `Block.Close()` is invoked from `deleteBlocks` (`tsdb/db.go:1662`) and post-compaction (`tsdb/db.go:1472`).

**Failure scenario:** A remote read streams historical chunks to a client over the network (slow, unbounded by the client's consume rate). `getChunkSeriesSet` returns and `defer` drops every block's `pendingReaders` ref to 0 *before the first byte is streamed*. A compaction or retention deletion that completes during the stream finds `pendingReaders == 0`, so `Block.Close()`'s `Wait()` returns immediately, `chunkr.Close()` unmaps the file, and `deleteBlocks` removes it. The next lazy `ChunkOrIterable` / `chk.Chunk.Bytes()` in `StreamChunkedReadResponses` reads unmapped memory → SIGSEGV/SIGBUS, or streams corrupted chunk data to the client.

Before this PR the `defer querier.Close()` lived in the per-query closure in `remoteReadStreamedXORChunks` and ran **after** `StreamChunkedReadResponses` returned, so `pendingReaders` stayed at 1 for the whole stream and `Block.Close()` correctly blocked until streaming finished. The refactor reintroduces precisely the race the `pendingReaders` guard exists to prevent.

Notes on scope/likelihood:
- The in-order **head** path is partially shielded: `populateWithDelGenericSeriesIterator.next` deep-copies the in-memory head chunk when `p.cr` is a `*headChunkReader` and `copyHeadChunk==true` (`tsdb/querier.go:712-719`), and `populateWithDelChunkSeriesIterator.Next` passes `true` (`tsdb/querier.go:892`). Persistent blocks and the OOO head (whose reader is not a `*headChunkReader`, so it takes the non-copy branch at `tsdb/querier.go:720-722`) are **not** shielded. Head isolation state is also released early by `headChunkReader.Close` (`tsdb/head_read.go:318-322`).
- This is a race, not a deterministic crash: it requires a block delete/compaction (or head truncation) to land during the streaming window. That window is large for remote read (network-bound streaming of exactly the older blocks that compaction/retention targets), so I rate it Critical despite being probabilistic. [Inference] — the concurrency is expected behavior of the mmap/`pendingReaders` design, not something I executed; I did not reproduce a crash.

**Suggested fix direction:** don't close the querier until the `ChunkSeriesSet` is fully consumed — e.g. return both the series set and a closer and defer the close around `StreamChunkedReadResponses`, or materialize/copy chunk bytes before closing. (The upstream `pendingReaders`/`RangeHead` isolation contract is what the original code respected.)

---

### Informational / clean areas checked

- **`chunks.Err()` addition and placement (`read_handler.go:206-208`) — correct but largely a no-op in the common path; not a bug.** It does correctly preserve the original `ChunkQuerier()`-construction error handling: the old `querier, err := ...; if err != nil { return err }` is now `ErrChunkSeriesSet(err)` (`read_handler.go:243-246`) surfaced via `chunks.Err()`. However, for the normal multi-querier TSDB (head + blocks) `Select` returns a `lazyGenericSeriesSet` whose `Err()` returns `nil` until the first `Next()` (`storage/lazy.go:36-40`), so this check catches only the construction error (and, in the degenerate single-querier case, an eager `PostingsForMatchers` error). Lazy select errors still surface via `ss.Err()` at the end of streaming (`storage/remote/codec.go:296`), exactly as before. No regression, no false early-return.

- **Error-handling equivalence — preserved.** Both construction errors and lazy errors reach the same outer handler (`read_handler.go:227-234`); `errors.As(err, &httpErr)` still works because the error is passed through unwrapped.

- **Behavioral equivalence of the moved code — preserved.** The `hints` construction (`read_handler.go:253-264`) and the `Select(ctx, true, hints, filteredMatchers...)` call (sorted, `sortSeries=true`) are byte-for-byte identical to the deleted inline code. No double-close (guarded at `tsdb/querier.go:104-106`; closed exactly once via the helper's `defer`). The close-error log message is unchanged (`read_handler.go:249`).

- **Go doc-comment convention — compliant.** The unexported `getChunkSeriesSet` doc comment (`read_handler.go:239-241`) starts with the identifier name and ends with a full stop, matching Go/Prometheus style. No issue.

**Bottom line:** the extraction is behavior-preserving in every respect *except* the resource lifetime, and that one exception (finding #1) is a genuine correctness regression — a latent use-after-free/data-corruption race against concurrent compaction and retention. I recommend not treating this refactor as safe as-is.
