# subagent agent-a1bf30e753b07e328

I have everything I need. Here is my type-design analysis.

---

# Type / API Design Review — PR #13777 "Chunked remote read: close the querier earlier"

No new type is introduced, so this is an evaluation of how the change *uses* the existing `storage.ChunkQuerier` / `storage.ChunkSeriesSet` / `storage.ErrChunkSeriesSet` / `storage.SelectHints` contracts. All line references are to the merged tree.

## Focal type / contract: `storage.ChunkSeriesSet` as returned by `getChunkSeriesSet`

`storage/remote/read_handler.go:242-266`

### Invariants Identified

1. **(New, load-bearing, implicit) The returned `ChunkSeriesSet` must be fully consumable after its backing `ChunkQuerier` has been `Close()`d.** The `defer querier.Close()` at `read_handler.go:247-251` runs when `getChunkSeriesSet` *returns*, i.e. before the caller ever iterates the set in `StreamChunkedReadResponses` (`read_handler.go:210-218`, consumed at `codec.go:235-296`). This is the central invariant the PR silently introduces.
2. **(Enforced, clean) The querier is closed exactly once on every path.** `defer` guarantees close whether `Select` panics-free-returns or an error set is returned. This is a genuine improvement in resource-lifetime cohesion over inline handling.
3. **(Pre-existing) Query-construction failure is representable as a value.** A failed `ChunkQuerier(...)` is folded into the return via `storage.ErrChunkSeriesSet(err)` (`read_handler.go:245`) and surfaced through `chunks.Err()` (`read_handler.go:206`).

### The central tension: the type system does not express "ChunkSeriesSet outlives its querier"

This is the crux and it is a real type-design defect, not a stylistic one.

The interface contract points the *opposite* way from what the new code assumes:

- `LabelQuerier.Close()` is documented only as "releases the resources of the Querier" (`storage/interface.go:171-172`). There is no statement that objects previously returned by `Select` remain valid afterward.
- The sibling method `LabelValues` explicitly warns "It is not safe to use the strings beyond the lifetime of the querier" (`storage/interface.go:161-162`). The established convention in this interface family is therefore that **results are bounded by querier lifetime.**
- `ChunkSeriesSet.At()` documents one lifetime extension only: "Returned series should be iterable even after `Next` is called" (`storage/interface.go:438`). It deliberately says *after `Next`*, not *after the querier is closed*. The absence is telling.

So the invariant the new code leans on is nowhere in the type contract. Worse, the first-party TSDB implementation **actively violates it**, which is the strongest possible evidence that it is not part of the contract:

- `blockChunkQuerier.Select` returns a **lazy** `NewBlockChunkSeriesSet(...)` that stores live references to `q.index`, `q.chunks`, `q.tombstones` (`tsdb/querier.go:174-196`).
- `blockBaseQuerier.Close()` closes exactly those: `q.index.Close(), q.chunks.Close(), q.tombstones.Close()` (`tsdb/querier.go:103-115`).
- `blockChunkSeriesSet.At()` hands out a `chunkSeriesEntry{chunks: b.chunks, ...}` holding the `ChunkReader` (`tsdb/querier.go:1173-1180`), and chunk *bytes* are pulled lazily during iteration (`codec.go:250-262`, `iter.At().Chunk.Bytes()`).

[Inference] For any TSDB-block-backed `ChunkSeriesSet`, closing the querier before iteration closes the chunk reader out from under the still-lazy set; consuming it afterward reads from released resources. Whether the exact remote-read queryable path materializes enough to mask this in practice is a *correctness* question I'm leaving to the code-review / silent-failure agents — but from a **type-design** standpoint the conclusion is unconditional: the code now depends on an invariant that (a) the interface does not state, (b) the interface's neighboring docs contradict, and (c) at least one concrete implementation does not uphold. That is a leaky, unenforced, implementation-fragile contract.

The doc comment at `read_handler.go:239-241` compounds this: it explains the *motive* ("ensure timely release of the querier resources") but never states the *precondition that makes it safe* — that the returned set must not depend on those resources. A future reader is told the dangerous thing is intentional without being told what makes it valid.

## The four evaluation axes

### 1. Load-bearing lifetime invariant — assessment and alternatives

The problem is that "close the querier" and "hand the set to a caller who reads it later" are pulled apart across a function boundary with nothing tying them together. Three candidate designs, in order of how honestly they express the invariant:

- **(A) Materialize before Close (makes the invariant *real*).** Drain the set into an owned, in-memory representation before `Close`, then return that. Building blocks exist (`storage.ChunkSeriesEntry`, `storage.NewListChunkSeriesIterator`, `storage/series.go:61,180`) though no ready-made "collect a `ChunkSeriesSet` into a list set" helper does. Cost: this copies chunk bytes into the heap, which **directly conflicts with the PR's OOM-avoidance motive** — you cannot both bound memory by releasing early *and* keep a lazy set alive. Naming this tradeoff explicitly is the single most valuable outcome of this review: the current design appears to get both, but only because the invariant is unchecked.
- **(B) Keep querier ownership with the streaming call (the pre-PR design).** Before this PR the `defer Close` lived in the per-query closure and ran *after* `StreamChunkedReadResponses` — correct by construction. The PR's goal was to shorten that window; option (A) is the only way to shorten it safely.
- **(C) Return the resource handle alongside the value.** Change the signature to `(storage.ChunkSeriesSet, func() error)` (a close func) or a small wrapper type that owns both set and querier and exposes `Close()`. The caller then `defer close()`s after consuming. This makes the lifetime coupling explicit in the type and keeps laziness — but it does **not** close earlier than the old code, so it doesn't serve the OOM goal either. It is strictly a clarity improvement over the pre-PR inline defer.

If the OOM win is worth keeping, (A) is the only design that is both safe and honest, and its memory cost should be measured and stated. If it is not, the change is trading a real (if implicit) correctness guarantee for a resource-timing optimization whose safety rests on an unenforced invariant.

### 2. Error channeling through the value — idiomatic, low concern

Folding the construction error into `storage.ErrChunkSeriesSet(err)` (`read_handler.go:245`) is **the established Prometheus idiom.** Every first-party `Select` does the same: `tsdb/querier.go:138,187` and `storage/remote/read.go:165,170` all return `ErrSeriesSet`/`ErrChunkSeriesSet` rather than a separate error. Surfacing it via `chunks.Err()` at the call site (`read_handler.go:206`) is consistent with how a real select error would surface, and the caller maps both to the same HTTP response anyway (`read_handler.go:227-235`). No `HTTPError` distinction is lost that wasn't already collapsed. This is the well-designed part of the change — accept it as-is. The only minor point: unlike the sample path (`read_handler.go:161`, `ToQueryResult`), warnings from a construction failure can't be carried, but a construction failure has no warnings to carry, so this is moot.

### 3. Hints construction duplication — a real (pre-existing, now worsened) smell

The `prompb.Query.Hints → storage.SelectHints` field-by-field copy is now duplicated verbatim between `remoteReadSamples` (`read_handler.go:147-158`) and `getChunkSeriesSet` (`read_handler.go:253-264`). This is a mapping between two types that belong to two packages, and it is exactly the kind of thing that silently rots when `SelectHints` gains a field. Note that both copies already **omit** `ShardCount`, `ShardIndex`, and `DisableTrimming` (`storage/interface.go:200-217`) — the duplication has already produced a maintenance liability where a reader must check two sites to confirm the omission is intentional in both. Recommend a single unexported helper in this file:

```go
func toSelectHints(h *prompb.ReadHints) *storage.SelectHints // nil-in, nil-out
```

used by both paths. Small, mechanical, removes a class of drift. This is the highest-value low-risk cleanup in the PR.

### 4. Function signature / cohesion

`getChunkSeriesSet(ctx, query, filteredMatchers)` (`read_handler.go:242`) reads cleanly and its parameters are fine — `query` and `filteredMatchers` are distinct concerns and don't need grouping. The cohesion problem is not the parameters but the **return type under-communicating ownership**: returning a bare `storage.ChunkSeriesSet` hides that the value's validity is coupled to a resource the function has already released. A signature that returned the set *plus* a `Close` func (option C above), or that returned a materialized set (option A), would make the return type tell the truth about lifetime. As written, the signature's honesty depends entirely on an invariant it does not encode.

## Ratings

- **Encapsulation: 4/10.** The querier object is well-hidden — it never escapes the function, and it's closed exactly once. But encapsulation is undermined by leaking a *dependency* on the closed resource through the returned value: the caller unknowingly depends on state the callee has torn down. Good object hiding, poor invariant hiding.
- **Invariant expression: 2/10.** The load-bearing "set outlives closed querier" invariant is entirely implicit; the type signature is silent and the doc comment (`read_handler.go:239-241`) states the motive but omits the precondition. Neighboring interface docs (`interface.go:161-162,171-172`) actively imply the opposite.
- **Invariant usefulness: 5/10.** The *goal* (bound memory by releasing queriers promptly) is legitimate and valuable, and the "closed exactly once via defer" property is genuinely clean. But the specific invariant the code relies on isn't the one that's enforced, and it collides with the laziness the type family is built around.
- **Invariant enforcement: 2/10.** Nothing — compile-time or runtime — prevents handing out a set whose backing resources are gone. The only enforced invariant is single close-on-all-paths (defer). The load-bearing one has no guard, and a first-party implementation (`tsdb/querier.go`) demonstrably breaks it.

## Recommended improvements (ranked, pragmatic)

1. **Resolve the lifetime invariant deliberately, not implicitly.** Either (A) materialize the set before `Close` and measure/accept the memory cost — the only design that keeps the OOM win *and* is safe — or (C) return the set together with a `Close` func / owning wrapper so the coupling is in the type. Do not leave it as a bare `ChunkSeriesSet` over a closed querier.
2. **At minimum, document the precondition.** If the team keeps the current shape pending a correctness verdict, the comment at `read_handler.go:239-241` must state that callers may only use the returned set if it does not retain references to querier resources, and that this holds for the specific queryable wired into remote read. An undocumented, implementation-dependent lifetime contract is the worst of the options.
3. **Extract a shared `toSelectHints` helper** to kill the `read_handler.go:147-158` / `253-264` duplication (and surface the `ShardCount`/`ShardIndex`/`DisableTrimming` omission in one place).
4. **Keep the `ErrChunkSeriesSet` error channeling** — it is idiomatic and correct; no change needed.

Files inspected: `/home/decaf/code/decaf-claude/competition/benchmark/repos/7/storage/remote/read_handler.go`, `/home/decaf/code/decaf-claude/competition/benchmark/repos/7/storage/interface.go`, `/home/decaf/code/decaf-claude/competition/benchmark/repos/7/storage/generic.go`, `/home/decaf/code/decaf-claude/competition/benchmark/repos/7/storage/remote/codec.go`, `/home/decaf/code/decaf-claude/competition/benchmark/repos/7/tsdb/querier.go`.

One caveat under my verified-truth constraint: the claims about the interface contract, the `defer`-close ordering, the idiomatic `ErrChunkSeriesSet` usage, and the TSDB lazy-set-holding-closed-resources structure are all **verified from the code above**. The statement that this *breaks at runtime* for the remote-read path is **[Inference]** — it depends on the exact queryable wired in, which I did not trace end-to-end; that runtime correctness question belongs to the code-review / silent-failure agents. My conclusion here is scoped to type design, where it holds regardless: the design depends on an invariant the types neither express nor enforce.
