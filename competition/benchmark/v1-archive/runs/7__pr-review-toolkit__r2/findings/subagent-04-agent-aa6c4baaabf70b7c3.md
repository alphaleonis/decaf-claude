# subagent agent-aa6c4baaabf70b7c3

I now have the complete picture, traced end to end. Let me compile the findings.

## Error-Handling Audit: PR prometheus/prometheus #13777 — "Chunked remote read: close the querier earlier"

Primary file: `/home/decaf/code/decaf-claude/competition/benchmark/repos/7/storage/remote/read_handler.go`

I traced the full call graph: `getChunkSeriesSet` → `blockChunkQuerier.Select` / `mergeGenericQuerier.Select` → `blockBaseSeriesSet` → `populateWithDelChunkSeriesIterator` → `Reader.ChunkOrIterable` (mmap read), plus `StreamChunkedReadResponses`, the `errChunkSeriesSet`/`lazyGenericSeriesSet` contracts, and the block `pendingReaders` read-guard. Verdicts below, with the two named concerns that are CLEAN first, then the one real regression.

---

### Concern 1 — Error conflation through `ErrChunkSeriesSet`: CLEAN (ruled out)

The querier-construction error is preserved verbatim.

- `read_handler.go:243-246` — on `ChunkQuerier()` failure the code returns `storage.ErrChunkSeriesSet(err)`.
- `storage/interface.go:392-404` — `errChunkSeriesSet{err}` stores the error and `Err()` returns it unchanged (`func (s errChunkSeriesSet) Err() error { return s.err }`). `ErrChunkSeriesSet` is a plain struct wrap, no `fmt.Errorf`, no masking.
- `read_handler.go:206-208` — the caller checks `chunks.Err()` and returns it. Downstream at `read_handler.go:228-234`, `errors.As(err, &httpErr)` still matches because the error identity/chain is intact.

No wrapping, no downgrade, no drop. The distinction the original `if err != nil` check made is fully retained for the construction error.

### Concern 3 — Close-error logging: CLEAN as to logging, but see Concern 4 for the ordering

- `read_handler.go:247-251` — the close error is still logged at `level.Warn` and not returned, identical to the pre-PR behavior (and identical to the sample path at `read_handler.go:141-145`). The close error itself is not swallowed any *differently* than before. No regression in how the close error is handled. The problem is not *whether* close errors are logged — it is *when Close runs* (Concern 4).

### Concern 2 — `Err()` vs `Select()` error semantics: NO error is dropped, but the early check is partly ineffective (LOW / informational)

Location: `read_handler.go:205-208`

The new early `chunks.Err()` check is **additive**, not a replacement, so nothing that was previously surfaced is now lost:

- It catches errors only when the set has them immediately available: the top-level `ChunkQuerier()` construction error, and the single-querier direct-`Select` case where `PostingsForMatchers` fails and returns `storage.ErrChunkSeriesSet(err)` (`tsdb/querier.go:185-188`).
- In the common **multi-block merge path**, `mergeGenericQuerier.Select` returns a `lazyGenericSeriesSet` (`storage/merge.go:118-121, 146-149`). Its `Err()` returns `nil` until `Next()` runs `init` — `storage/lazy.go:36-41` explicitly short-circuits to `nil` when `c.set == nil`. So `chunks.Err()` immediately after `getChunkSeriesSet` returns `nil` here even if init would fail.
- No silent drop results, because `StreamChunkedReadResponses` triggers `init` via `ss.Next()` and returns `ss.Err()` (`storage/remote/codec.go:296`) and per-series `iter.Err()` (`codec.go:292-294`); the caller propagates those to an HTTP error (`read_handler.go:219-234`).

Net: the early check is a redundant fast-path for the construction error and does little for the merge path, but it does not hide anything. Worth a one-line comment noting it only catches eagerly-available errors, so future readers do not assume it validates the whole Select.

---

### Concern 4 — CRITICAL: the querier's block read-guard is released before the series set is consumed (use-after-free / truncated-stream regression)

Location: `read_handler.go:242-266` (the `defer querier.Close()` at 247-251 relative to the lazy read in `StreamChunkedReadResponses`, invoked at `read_handler.go:210-218`)

This is the substantive finding, and it is exactly the hazard Concern 4 asks about.

**Mechanism (verified in this checkout):**
1. `getChunkSeriesSet` calls `querier.Select(...)` and returns the resulting `ChunkSeriesSet`. Its `defer querier.Close()` runs **when the function returns — before any chunk data is read.**
2. The returned set reads chunk **metadata/labels** from the index during `blockBaseSeriesSet.Next()` (`tsdb/querier.go:558-607`), but the chunk **bytes** are read lazily, later, via `p.cr.ChunkOrIterable(...)` (`tsdb/querier.go:721`) which only executes inside `StreamChunkedReadResponses`' iteration loop (`codec.go:235-291`) — i.e. **after** Close.
3. `querier.Close()` for a persistent block resolves to `blockChunkReader.Close()`, which does **not** unmap anything — it only calls `r.b.pendingReaders.Done()` (`tsdb/block.go:567-570`). That `pendingReaders` guard is the *only* thing that keeps the block's shared mmap alive: `Block.Close()` unmaps the chunk segments (`tsdb/block.go:385-389`) but first blocks on `pendingReaders.Wait()` (`tsdb/block.go:383`).

Before this PR, `defer querier.Close()` lived in the inner closure of `remoteReadStreamedXORChunks` and ran *after* `StreamChunkedReadResponses` finished streaming, so `pendingReaders > 0` for the entire duration chunk bytes were read from the mmap. This PR drops that guard to zero **before** the first byte is streamed.

**Hidden errors this enables:** while `StreamChunkedReadResponses` is still reading `sgmBytes.Range(...)` from the block mmap (`tsdb/chunks/chunks.go:680-700`), a concurrent `Block.Close()` (triggered by compaction completing and `DB.reload()` dropping the now-obsolete source blocks) sees `pendingReaders == 0`, proceeds past `Wait()`, and unmaps the segment files out from under the in-flight read. Possible outcomes:
- **Process crash** — SIGSEGV/SIGBUS reading unmapped memory. Ironic, given the commit message says the goal was to avoid OOM/instability from broken chunked reads.
- **Spurious read error surfaced as a corruption** — if the region is remapped to other data, the CRC32 check at `tsdb/chunks/chunks.go:696` fails and returns an error, which flows out via `iter.Err()` → HTTP error for data that was actually valid.
- **Silent partial/garbage response with HTTP 200** — the streaming path commits `200 OK` + Content-Type and flushes frames on the first `stream.Write` (`codec.go:283`). Any error surfacing *mid-stream* reaches `http.Error(w, err.Error(), http.StatusInternalServerError)` at `read_handler.go:233`, but `WriteHeader(500)` is then a no-op because the header is already sent. The remote-read client therefore receives a `200` with a **truncated/corrupt chunk stream** and an error string appended to the body — the classic silent failure Concern 4 describes. This 200-then-fail shape is pre-existing to the streaming design, but this PR materially widens the window in which a *read* (not just a network) error can occur mid-stream.

For the head path there is partial protection: the chunk-series iterator calls `p.next(true)` (`tsdb/querier.go:892`), so an *open* in-memory head chunk with no deletion overlap is copied via `ChunkWithCopy` (`tsdb/head_read.go:371-382`). But mmapped head chunks and deletion-overlap cases still return a `safeHeadChunk` bound to the `isoState` that `headChunkReader.Close()` already released (`tsdb/head_read.go:318-323, 385-390`), so the head is not fully safe either.

**User impact:** intermittent, load- and compaction-timing-dependent failures on streamed remote read — process crashes, spurious "chunk corruption" 500s, or truncated 200 responses — none reproducible on demand and all extremely hard to attribute back to "we closed the querier too early." This is precisely the obscure, hard-to-debug class of failure to reject.

**Recommendation:** the querier must outlive consumption of the series set it produced. Do not close inside `getChunkSeriesSet`. Either (a) keep the `defer querier.Close()` in the caller so it runs after `StreamChunkedReadResponses` returns (the pre-PR ordering), or (b) have `StreamChunkedReadResponses` take ownership and close the querier only after the stream is fully written. If the goal is genuinely to release resources early on *broken/aborted* requests, tie the close to `ctx` cancellation rather than to the return of the setup function — closing on setup-return is unconditional and applies to the healthy path too.

**Labeling per my verification directive:** the *mechanism* above (guard released before lazy read; block mmap kept alive only by `pendingReaders`) is directly verified from the code in this checkout. The claim that this specific PR was later reverted/reworked upstream for this reason is **[Unverified]** — I did not confirm it from this checkout and am not relying on it; the finding stands on the traced code alone.

---

### Areas checked and found clean
- `read_handler.go:206-208` construction-error propagation — error preserved and returned (Concern 1). CLEAN.
- `read_handler.go:227-234` HTTP error mapping (`errors.As(err, &httpErr)`) — intact; unaffected by the refactor. CLEAN.
- `read_handler.go:223-225` warnings logging loop — unchanged. CLEAN.
- Close-error *logging* at `read_handler.go:247-251` — still logged at Warn, behavior-equivalent to before (Concern 3). CLEAN (the ordering is the issue, not the logging).
- `StreamChunkedReadResponses` internal error handling (`codec.go:252-296`) — every read/marshal/write error and both `iter.Err()` and `ss.Err()` are returned, not swallowed. CLEAN (this is what still catches the mid-stream failures the PR makes more likely).

### Bottom line
Concerns 1 and 3-as-to-logging are clean; Concern 2 surfaces no dropped error (minor: the early `chunks.Err()` is largely a no-op on the merge path). Concern 4 is a real, CRITICAL correctness/reliability regression: closing the querier before the chunk series set is consumed releases the block read-guard early, creating a use-after-free window whose failure modes range from a process crash to a silent truncated HTTP-200 stream. I recommend the change not ship in this form without moving the close back to after consumption or gating it on context cancellation.

Relevant files (all absolute):
- `/home/decaf/code/decaf-claude/competition/benchmark/repos/7/storage/remote/read_handler.go`
- `/home/decaf/code/decaf-claude/competition/benchmark/repos/7/storage/remote/codec.go`
- `/home/decaf/code/decaf-claude/competition/benchmark/repos/7/storage/interface.go`
- `/home/decaf/code/decaf-claude/competition/benchmark/repos/7/storage/lazy.go`
- `/home/decaf/code/decaf-claude/competition/benchmark/repos/7/storage/merge.go`
- `/home/decaf/code/decaf-claude/competition/benchmark/repos/7/tsdb/querier.go`
- `/home/decaf/code/decaf-claude/competition/benchmark/repos/7/tsdb/block.go`
- `/home/decaf/code/decaf-claude/competition/benchmark/repos/7/tsdb/chunks/chunks.go`
- `/home/decaf/code/decaf-claude/competition/benchmark/repos/7/tsdb/head_read.go`
