# Benchmark run: 7__pr-review-toolkit__r2

| field | value |
|---|---|
| tool | pr-review-toolkit |
| subject | 7 (go / small) — prometheus/prometheus#13777 |
| review diff | `d1abc3f2557660728dc6a34eb2da1f32461b6665^1..d1abc3f2557660728dc6a34eb2da1f32461b6665` (merge d1abc3f2557660728dc6a34eb2da1f32461b6665) |
| session model | claude-opus-4-8 |
| status | done (exit 0, is_error=false, subtype=success) |
| **total review time — wall (s)** | 648 |
| longest single subagent (s) | 431 |
| duration_ms (orchestrator self) | 646652 |
| duration_api_ms (summed parallel API time, not wall) | 1492928 |
| num_turns | 13 |
| cost_usd | 7.208898 |
| input_tokens | 15 |
| output_tokens | 21192 |
| cache_creation_tokens | 69883 |
| cache_read_tokens | 428121 |
| total_tokens (orchestrator only) | 519211 |
| **subagents** | 5 |
| **ws output_tokens** | 22175 |
| ws input_tokens | 128 |
| ws cache_creation | 389703 |
| ws cache_read | 3649456 |
| ws total_tokens | 4061462 |
| session_id | 4e629eb9-d897-4ba8-8efb-59569c3f0158 |
| findings (raw lines) | 155 |

> **ws = whole-session** (orchestrator + every subagent transcript, deduped). The non-ws token
> rows are the orchestrator session ONLY — they miss subagent tokens for fan-out tools.
> **`cost_usd` is the authoritative whole-session cost** (Claude Code sums subagents; not an estimate).
> Caveat: `ws total_tokens` is inflated by prompt-cache re-reads (cache_read counted per turn);
> `ws output_tokens` is the clean, cache-independent work signal. Findings files under ./findings/.

### Per-subagent (diagnostic)

Subagents run in PARALLEL — the TOTAL review time is the wall clock above (648s), NOT the sum of these.

| agent | output_tokens | total_tokens | duration_s |
|---|---:|---:|---:|
| agent-a20c656de100ca031 | 30 | 476351 | 165 |
| agent-a31d3338985d3d0be | 378 | 1028592 | 298 |
| agent-a344a1fc940ed7991 | 177 | 751738 | 236 |
| agent-aa6c4baaabf70b7c3 | 377 | 1126833 | 431 |
| agent-acc78426285aab12c | 21 | 158737 | 114 |

## Findings (final result text)

```
All five agents completed and I did not post anything anywhere. Before the findings, one dispositive fact I verified directly in this checkout:

> **This PR was reverted upstream.** Commit `6e89250a5d` — *Revert "Chunked remote read: close the querier earlier"* by Prometheus maintainer Bryan Boreham (2024-07-26, PR #14515), reason quoted verbatim:
> *"Believed to trigger segmentation faults due to memory-mapped block data still being accessed by iterators after the querier is closed."*

All five agents independently converged on exactly that failure mode by tracing the code — the maintainer's revert corroborates it. Note the reason is the maintainer's own hedge ("Believed to"); the mechanism below is a code-trace **[Inference]**, expected behavior of the mmap/`pendingReaders` design, not something reproduced by execution.

---

# PR #13777 Review — `storage/remote/read_handler.go` (+32/−21, single file)

**The change:** extracts a new helper `getChunkSeriesSet` (read_handler.go:242‑266) that creates a `ChunkQuerier`, calls `Select`, and returns a `storage.ChunkSeriesSet`. Because the `defer querier.Close()` now lives *inside* the helper (read_handler.go:247‑251), the querier is closed **when the helper returns** — i.e. *before* the returned lazy `ChunkSeriesSet` is streamed by `StreamChunkedReadResponses` (read_handler.go:210‑218). That lifetime inversion is the crux every agent hit.

---

## 1. `code-reviewer` — complete findings

### 🔴 Critical — Use-after-free / data race: `ChunkQuerier` closed before its lazy `ChunkSeriesSet` is consumed
**Severity: Critical · Confidence ~88** — `read_handler.go:242‑266` (helper), specifically `defer querier.Close()` at `:247‑251` firing before `return querier.Select(...)` at `:265` is streamed by the caller at `:210‑218`.

Chain of evidence traced end-to-end:
- Helper closes the querier via `defer` the instant it returns (`read_handler.go:247‑251`), then hands the result to `StreamChunkedReadResponses` (`read_handler.go:210‑218`).
- Querier is `db.ChunkQuerier` → `NewMergeChunkQuerier` (`tsdb/db.go:2072`); its `Select` returns a lazy `lazyGenericSeriesSet` (`storage/merge.go:118‑121, 146‑149`).
- Each child `blockChunkSeriesSet` (`tsdb/querier.go:195`) reads chunk bytes lazily during iteration: `populateWithDelGenericSeriesIterator.next` → `p.cr.ChunkOrIterable(...)` at `tsdb/querier.go:721`, driven by `populateWithDelChunkSeriesIterator.Next` (`tsdb/querier.go:877‑913`), which runs only when `StreamChunkedReadResponses` iterates (`storage/remote/codec.go:235‑266`) and calls `chk.Chunk.Bytes()` (`codec.go:261`). For persistent blocks those bytes point straight into the memory‑mapped chunk file — **not copied**.
- Closing the merge querier cascades `Close()` to every child (`storage/merge.go:255‑259`). For a persistent block, `blockBaseQuerier.Close` (`tsdb/querier.go:103‑115`) closes the `blockChunkReader`, whose `Close` is exactly `pb.pendingReaders.Done()` (`tsdb/block.go:567‑568`).
- `pendingReaders` is the sole mechanism keeping a block mapped while read: `Block.Close()` sets `closing=true` then blocks on `pendingReaders.Wait()` before unmapping (`tsdb/block.go:378‑390`); `startRead` adds the ref (`tsdb/block.go:416‑425`). `Block.Close()` fires from `deleteBlocks` (`tsdb/db.go:1662`) and post‑compaction (`tsdb/db.go:1472`).

**Failure scenario:** A remote read streams historical chunks to a slow network client. `getChunkSeriesSet` returns and `defer` drops every block's `pendingReaders` ref to 0 *before the first byte streams*. A compaction/retention deletion completing mid‑stream finds `pendingReaders == 0`, so `Block.Close()`'s `Wait()` returns immediately, unmaps the file, and `deleteBlocks` removes it. The next lazy `ChunkOrIterable` / `chk.Chunk.Bytes()` reads unmapped memory → SIGSEGV/SIGBUS, or streams corrupted chunk data. Before this PR, `defer querier.Close()` lived in the per‑query closure and ran *after* streaming finished, so `pendingReaders` stayed ≥1 for the whole stream.

Scope notes: the in‑order **head** path is partially shielded — `populateWithDelGenericSeriesIterator.next` deep‑copies the in‑memory head chunk when the reader is `*headChunkReader` and `copyHeadChunk==true` (`tsdb/querier.go:712‑719`, `:892`). **Persistent blocks and the OOO head are not shielded** (`tsdb/querier.go:720‑722`); head isolation state is also released early by `headChunkReader.Close` (`tsdb/head_read.go:318‑322`). It's a race (needs a delete/compaction in the streaming window), but that window is large for network‑bound remote read, hence Critical. **Fix direction:** don't close until the set is fully consumed (return the set + a closer and defer around `StreamChunkedReadResponses`), or materialize/copy chunk bytes before closing.

### Areas checked and clean
- **`chunks.Err()` placement (`read_handler.go:206‑208`)** — correct; preserves the original construction‑error handling via `ErrChunkSeriesSet(err)` (`:243‑246`). On the multi‑querier path `Err()` is `nil` until first `Next()` (`storage/lazy.go:36‑40`), so it only catches the construction error; lazy select errors still surface at end of streaming via `ss.Err()` (`codec.go:296`), as before. No regression.
- **Error‑handling equivalence** — preserved; both construction and lazy errors reach the same handler (`read_handler.go:227‑234`), `errors.As` still matches (error passed through unwrapped).
- **Behavioral equivalence of moved code** — `hints` construction (`:253‑264`) and `Select(ctx, true, ...)` are byte‑for‑byte identical to the deleted inline code. No double‑close (guarded at `tsdb/querier.go:104‑106`). Close‑error log message unchanged (`:249`).
- **Go doc‑comment convention** — unexported `getChunkSeriesSet` comment (`:239‑241`) starts with the identifier, ends with a full stop. Compliant.

**Bottom line:** behavior‑preserving in every respect *except* resource lifetime — and that one exception is a genuine correctness regression. Do not treat as safe as‑is.

---

## 2. `silent-failure-hunter` — complete findings

### CLEAN — Concern 1: Error conflation through `ErrChunkSeriesSet`
Construction error is preserved verbatim. `read_handler.go:243‑246` returns `storage.ErrChunkSeriesSet(err)`; `storage/interface.go:392‑404` — `errChunkSeriesSet{err}.Err()` returns it unchanged (no `fmt.Errorf`, no masking). Caller checks `chunks.Err()` (`:206‑208`); downstream `errors.As(err, &httpErr)` (`:228‑234`) still matches. No wrap, downgrade, or drop.

### CLEAN — Concern 3: Close‑error logging
`read_handler.go:247‑251` still logs the close error at `level.Warn` and doesn't return it — identical to pre‑PR and to the sample path (`:141‑145`). The problem is *when* Close runs, not whether the error is logged.

### LOW / informational — Concern 2: `Err()` vs `Select()` semantics
The early `chunks.Err()` check (`read_handler.go:205‑208`) is **additive, not a replacement**, so nothing previously surfaced is lost. It catches only eagerly‑available errors: the construction error, and the single‑querier `PostingsForMatchers` failure (`tsdb/querier.go:185‑188`). In the common multi‑block merge path, `Err()` is `nil` until `Next()` runs `init` (`storage/merge.go:118‑121,146‑149`; `storage/lazy.go:36‑41`). No silent drop — `StreamChunkedReadResponses` triggers `init` via `ss.Next()` and returns `ss.Err()` (`codec.go:296`) + per‑series `iter.Err()` (`codec.go:292‑294`), propagated to HTTP error (`read_handler.go:219‑234`). Suggest a one‑line comment noting the early check only catches eagerly‑available errors.

### 🔴 Critical — Concern 4: Block read‑guard released before the set is consumed (use‑after‑free / truncated‑stream)
`read_handler.go:242‑266` (the `defer` at `:247‑251` vs the lazy read in `StreamChunkedReadResponses` invoked at `:210‑218`). Mechanism verified in this checkout:
1. Helper's `defer querier.Close()` runs on return — before any chunk data is read.
2. The set reads metadata/labels during `blockBaseSeriesSet.Next()` (`tsdb/querier.go:558‑607`), but chunk **bytes** are read lazily later via `p.cr.ChunkOrIterable(...)` (`tsdb/querier.go:721`) inside the streaming loop (`codec.go:235‑291`) — after Close.
3. `querier.Close()` for a persistent block → `blockChunkReader.Close()` → only `r.b.pendingReaders.Done()` (`tsdb/block.go:567‑570`). That guard is the *only* thing keeping the mmap alive: `Block.Close()` unmaps segments (`tsdb/block.go:385‑389`) after blocking on `pendingReaders.Wait()` (`:383`).

**Hidden errors this enables** while `StreamChunkedReadResponses` still reads `sgmBytes.Range(...)` from the mmap (`tsdb/chunks/chunks.go:680‑700`), if a concurrent `Block.Close()` (compaction + `DB.reload()`) proceeds past `Wait()` and unmaps:
- **Process crash** (SIGSEGV/SIGBUS) — ironic given the commit's goal was to avoid OOM/instability.
- **Spurious corruption error** — CRC32 check (`tsdb/chunks/chunks.go:696`) fails on valid data → 500.
- **Silent partial/garbage HTTP 200** — the stream commits `200 OK` + headers on the first `stream.Write` (`codec.go:283`); a mid‑stream error then hits `http.Error(w, ..., 500)` (`read_handler.go:233`) but `WriteHeader(500)` is a no‑op since headers are sent → client gets a **200 with a truncated/corrupt chunk stream** + error string in the body. This PR materially widens the window in which a *read* error (not just network) can occur mid‑stream.

Head path partial protection: chunk iterator calls `p.next(true)` (`tsdb/querier.go:892`) so open in‑memory head chunks are copied (`ChunkWithCopy`, `tsdb/head_read.go:371‑382`); but mmapped head chunks and deletion‑overlap cases return a `safeHeadChunk` bound to an already‑released `isoState` (`tsdb/head_read.go:318‑323,385‑390`). **Recommendation:** querier must outlive consumption — keep `defer querier.Close()` in the caller (pre‑PR ordering), or have `StreamChunkedReadResponses` own and close it after writing; if early release on aborted requests is the real goal, tie close to `ctx` cancellation, not to setup‑function return.

### Clean
`read_handler.go:206‑208` construction‑error propagation; `:227‑234` HTTP mapping; `:223‑225` warnings loop; close‑error logging at `:247‑251`; `StreamChunkedReadResponses` internal handling (`codec.go:252‑296`) returns every read/marshal/write error plus `iter.Err()`/`ss.Err()`.

---

## 3. `pr-test-analyzer` — complete findings

**Does the PR add/change tests? No.** Merge commit touches only `read_handler.go` (+32/−21); no `_test.go` changes. Behavioral/lifecycle change to a hot path with zero test changes.

**The decisive determination:** existing tests **do use a real tsdb‑backed queryable, not a mock** — but the test data lives entirely in the **in‑memory head block**, never compacted into memory‑mapped persistent blocks. The mmapped blocks are exactly the resource the early close releases out from under live iterators, so the tests exercise the path but **cannot** trip the fault.

Evidence:
- Real `*tsdb.DB`: `read_handler_test.go:203‑209` builds the store via `promql.LoadedStorage` → `promql/test.go:59‑72` → `teststorage.TestStorage` (`util/teststorage/storage.go:52‑56`) which **embeds `*tsdb.DB`** opened on disk (`:30‑50`). So `querier.Close()` runs real tsdb cleanup.
- Head‑only data: `TestStreamReadEndpoint`/`BenchmarkStreamReadEndpoint` (`read_handler_test.go:198`, `:134`) only append + commit; nothing calls `Compact`/`CompactHead`/`createBlock` (`teststorage.New` sets 24h block durations to keep data in the head).
- Why that hides the bug: `blockBaseQuerier.Close()` (`tsdb/querier.go:103‑115`) unmaps a *persistent* block's chunk files; a `blockChunkSeriesSet` reads them lazily during iteration → close‑then‑iterate = reading unmapped memory. Head chunks are in‑memory, so head‑only tests iterate safely after close and byte assertions (`read_handler_test.go:296‑431`) still pass.

**Findings (severity‑ranked):**
1. **[CRITICAL, 10]** No test covers the invariant the PR relies on (querier closed before `ChunkSeriesSet` consumed, against persistent/mmapped blocks). `read_handler.go:205‑218` + `:247‑251`. The head‑only `TestStreamReadEndpoint` is structurally incapable of catching it. Would live in a new `TestStreamReadEndpoint_PersistentBlocks` that appends, forces `store.DB.Compact(ctx)`/`CompactHead`, then streams and asserts the full response.
2. **[IMPORTANT, 7]** `ChunkQuerier` construction‑error path (`read_handler.go:243‑245`) untested — no test injects a queryable whose `ChunkQuerier` errors, so the `error → ErrChunkSeriesSet → Err() → HTTP` routing is unverified.
3. **[IMPORTANT, 6]** `Select`‑level error via `chunks.Err()` (`:206‑208`) untested — no test asserts a deferred `Select` error maps to the correct HTTP status (`:228‑234`).
4. **[IMPORTANT, 5]** Close‑error handling (`:247‑251`) untested — no test with a `Close()` that errors verifies the request still succeeds and warns.
5. **[QUALITY]** Existing streamed tests assert exact serialized chunk bytes (`read_handler_test.go:307‑431`) — brittle golden‑byte assertions, yet blind to the lifecycle regression; false sense of thoroughness.
6. **[QUALITY]** Empty‑result and large multi‑block streaming after close uncovered — the multi‑block case is the one most likely to dereference unmapped memory.

**Positive:** harness is genuinely real‑storage‑backed (right foundation; gap is data placement, not a mock); happy path is covered thoroughly (multiple queries, external labels, byte‑frame splitting, float + native‑histogram chunks, `QueryIndex`).

**Verdict: inadequate for this change.** Per Prometheus's own guideline ("if the PR adds or changes a behaviour ... it would need a unit/e2e test"), a test compacting data into a persistent block and streaming it after close was required and absent. The change was reverted in production for exactly this segfault while the suite stayed green — a single persistent‑block test **[Inference — expected, not guaranteed]** would have caught it.

---

## 4. `comment-analyzer` — complete findings

Only one comment is introduced — the `getChunkSeriesSet` doc comment (`read_handler.go:239‑241`):
```
// getChunkSeriesSet executes a query to retrieve a ChunkSeriesSet,
// encapsulating the operation in its own function to ensure timely release of
// the querier resources.
```

**Critical issues: none** — the comment contains no factual error and is not actively misleading.

**Improvement opportunities:**
1. **Missing the load‑bearing invariant (highest value).** `read_handler.go:239‑241`. The comment gives the easy "why" (release resources sooner) but omits the surprising, load‑bearing point: the querier is deliberately closed *before* the returned set is iterated (`defer` at `:247‑251` fires on return `:265`; consumed later by `StreamChunkedReadResponses`, `codec.go:235‑290`). At the call site (`:205‑214`) this reads like a use‑after‑close, and nothing warns that it's only safe if the returned set is self‑contained. **[Inference]** the interface contract doesn't guarantee that; a future lazy querier implementation would silently reintroduce the bug. Suggests expanding the comment to state the invariant and the risk explicitly.
2. **"Timely release" understates the change and uses a guarantee word.** `read_handler.go:240‑241`. The real change is concrete — the querier no longer stays open *throughout response streaming to a possibly‑slow client*. Suggests: "so the querier is released as soon as the result set is obtained, instead of being kept open while the response is streamed to the client." (Also flags "to ensure" against the guarantee‑word convention.)

**Minor / comment‑locality regression:**
3. The surviving `// The streaming API has to provide the series sorted.` comment (`read_handler.go:213`) is now orphaned from the `sortSeries=true` argument it justified — that `Select(ctx, true, ...)` now sits comment‑less at `:265`, while the comment floats above the `chunks` variable. Low impact. Suggests a short note at `:265` next to the `true` argument.

**Convention check — PASS:** starts with the identifier name (lowercase correct for an unexported func), ends with a full stop, complete sentence.

**Comment‑rot scan elsewhere — CLEAN:** `remoteReadSamples` (`:141‑145`) still creates its querier inline correctly; comments at `:47‑48`, `:61`, `:112`, `:268‑270` untouched and unaffected; no orphaned/false comment introduced beyond #3.

**Bottom line:** the comment is accurate and convention‑compliant but documents the easy half of the "why" and omits the hard, non‑obvious half — adding that invariant is the highest‑value improvement.

---

## 5. `type-design-analyzer` — complete findings

No new named type; evaluates the new method signature and the invariant it silently depends on.

**1. The new signature** — `read_handler.go:242`: `getChunkSeriesSet(ctx, query *prompb.Query, filteredMatchers []*labels.Matcher) storage.ChunkSeriesSet`
- **Error‑in‑return‑value vs explicit `error`:** construction failure is folded into the return via `storage.ErrChunkSeriesSet(err)` (`:245`), recovered by the caller with `chunks.Err()` (`:206`). *In favor:* idiomatic within the package — `Select` itself folds errors the same way (`tsdb/querier.go:187`). *Against:* it folds a *different class* of error — a resource‑acquisition failure ("couldn't even start") — that the original code returned as a clean `(nil, err)` early return. The signature `... storage.ChunkSeriesSet` advertises total success and nothing forces the caller to call `.Err()` before iterating; a `(ChunkSeriesSet, error)` return would make the compiler enforce that check. Trades a compile‑time guarantee for a documented‑only convention. Minor on its own.
- **Parameter granularity:** body uses only `query.StartTimestampMs`, `query.EndTimestampMs` (`:243`) and `query.Hints` (`:254`), deliberately not `query.Matchers` (pre‑filtered into `filteredMatchers`). Passing the whole `*prompb.Query` leaves `query.Matchers` as a latent trap — a future edit reaching for it would silently bypass external‑label filtering. Passing `(start, end int64, hints *prompb.ReadHints)` would remove the trap. Low severity.

**2. The core invariant (decisive).** The returned `ChunkSeriesSet` must stay usable *after* its `ChunkQuerier` is `Close()`d — but the `defer` (`:247‑251`) closes it before the caller streams it (`:210‑218`).
- **Expressed anywhere? No.** `ChunkQuerier` contract (`storage/interface.go:148‑156`) is silent on result lifetime vs `Close()`. `Close()` doc (`:171‑172`) says the opposite of what's needed: *"Close releases the resources of the Querier."* `ChunkSeriesSet` doc (`:436‑446`) only promises `At()` is iterable after `Next` — about order, not survival past `Close()`. **Direct contradicting precedent in the same interface:** `LabelQuerier.LabelValues` (`:161`) is documented *"It is not safe to use the strings beyond the lifetime of the querier."* The established package contract is that querier outputs do **not** outlive the querier; the PR bets on the opposite for `Select`'s output with nothing backing it.
- **Implementation honors it? No — relies on incidental, in fact false, behavior.** `blockChunkQuerier.Select` (`tsdb/querier.go:174‑196`) returns a lazy set reading from `q.index`/`q.chunks` on demand; `blockBaseQuerier.Close` (`:103‑115`) closes those readers (mmap unmapped for persistent blocks). DB path compounds it: `DB.ChunkQuerier` → `NewMergeChunkQuerier` (`tsdb/db.go:2067‑2072`), `mergeGenericQuerier.Select` returns a `lazyGenericSeriesSet` whose `init` runs only on first consumption (`storage/merge.go:118‑121,146‑149`); `Close` tears down all sub‑queriers (`:255`). Close‑before‑consume → iterators read closed/unmapped block data → use‑after‑free/segfault.
- **Contrast with the correct sibling path:** `remoteReadSamples` (`read_handler.go:137‑164`) calls `ToQueryResult(querier.Select(...), limit)` (`:161`) which *fully drains* the set into memory *while the querier is open*; `defer querier.Close()` (`:141‑145`) runs after materialization. The chunked path broke that symmetry by moving consumption to after Close.
- **Encapsulation angle:** by pulling the querier entirely inside the helper and returning only the set, the method makes it *structurally impossible* for the caller to keep the producer alive during consumption — two objects with a hard producer→consumer dependency given disjoint lifetimes. Encapsulation that makes correct use unrepresentable. The doc comment (`:239‑241`) compounds it by advertising the hazard as a feature.

**3. Is `ErrChunkSeriesSet` appropriate?** Yes, in isolation. `storage/interface.go:401‑404` exists to surface an error to a consumer that only checks `.Err()`, and the consumer does exactly that (`:206`). Used as intended; the problem is the lifetime bet, not this construct.

**Ratings (of the `getChunkSeriesSet` design + the lifetime invariant):**
- **Encapsulation — 3/10** — clean hiding of hint‑mapping/construction, but encapsulates the querier's *lifetime* so aggressively the caller can't honor the set↔querier dependency.
- **Invariant Expression — 2/10** — the load‑bearing invariant is expressed nowhere; the signature implies a self‑contained set, the comment frames the dangerous ordering as a benefit, and the nearest precedent (`LabelValues`, `:161`) states the opposite rule.
- **Invariant Usefulness — 3/10** — motivation legitimate (release gate/reader resources before slow streaming), but the invariant the mechanism depends on is false (goal ~7, realized invariant ~1).
- **Invariant Enforcement — 1/10** — none; the type system permits (and the design encourages) use‑after‑close; surfaced only empirically as segfaults, resolved by reverting.
- **Error‑folding sub‑design — 7/10** — correct, intended use of the sentinel; loses points only for folding a *construction* error into a set‑typed return, dropping compile‑time forcing.

**Recommended improvements:**
- **Don't decouple the two lifetimes** — keep `defer querier.Close()` in the caller (the reverted/pre‑PR ordering). To keep the readability win, extract a helper returning **both** the set and a closer: `getChunkSeriesSet(...) (storage.ChunkSeriesSet, io.Closer, error)`, and `defer` the close after streaming.
- Early resource release during streaming would require **materializing** the set before Close (copying chunks) — which defeats the streaming/memory goals, so not viable here; the trade‑off should be explicit.
- **Encode the invariant in the interface docs** (`storage/interface.go:436‑446`, `:337‑348`): "results are only valid while the producing querier is open; do not use after `Close`," matching the `LabelValues` note at `:161`.
- **Tighten the signature** to `(start, end int64, hints *prompb.ReadHints, matchers []*labels.Matcher)` to remove the unused‑`query.Matchers` trap.

---

## Consolidated takeaway

The refactor is clean and behavior‑preserving on every axis **except the one that matters**: it inverts the querier↔result‑set lifetime, closing the `ChunkQuerier` before the lazy `ChunkSeriesSet` it produced is streamed. For persistent (memory‑mapped) blocks and the OOO head, the returned iterators read chunk bytes straight from mmap that `Close()` releases (via `pendingReaders.Done()`), opening a use‑after‑free window against concurrent compaction/retention → segfault, spurious corruption 500s, or silent truncated HTTP‑200 streams. The single existing test can't catch it (head‑only data), and no new test was added. All five agents reached this independently, and the upstream maintainer revert (`6e89250a5d` / PR #14515) confirms the segfault outcome. Nothing was posted anywhere.
```
