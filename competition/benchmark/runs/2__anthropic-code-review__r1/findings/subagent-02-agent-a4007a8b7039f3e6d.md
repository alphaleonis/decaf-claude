# subagent agent-a4007a8b7039f3e6d

I've read the full file and analyzed the changed method against the cost-at-scale questions.

## Cost analysis

The changed code is `TryGetValidatableProperty` at `src/Components/Forms/src/EditContextDataAnnotationsExtensions.cs:362-386`, reached from `OnFieldChanged` (line 94).

**Scale and multiplication.** `OnFieldChanged` fires once per field-change event — one call, not a loop over a collection, so there is no per-item fan-out. The result is memoized in a `static ConcurrentDictionary<(Type, string), PropertyInfo?>` (line 46), keyed by (runtime model type, field name), and `null` is cached too (line 382). The reflection block (lines 370-379) runs **only on a cache miss**. The number of distinct (type, field) keys is bounded by the app's form-model schema — a small, fixed set — and the cache is static (shared across every `EditContext`/circuit in the process), so each key misses **at most once for the whole process lifetime**. Amortized reflection cost per field change trends to zero.

**Q1 — is the added second `GetProperty` material?** No. It is a single extra `GetProperty` call, paid at most once per (type, field) key ever, on the cold first-edit path. Fully bounded by the cache.

**Q2 — the inherited-property common path now does two reflection calls (call 1 DeclaredOnly → null, call 2 FlattenHierarchy → hit) instead of one.** Real, but the doubling applies only to cache **misses**, i.e. once per (type, field) key across the process. It is strictly bounded by the cache; no user perceives a per-keystroke or per-request cost. A one-time extra `GetProperty` at microsecond scale on a cold path is not a reportable regression.

**Q3 — concurrency cost of the cache write.** The write `_propertyInfoCache[cacheKey] = propertyInfo;` (line 382) is a striped-lock `ConcurrentDictionary` indexer set that executes only on a miss. The hot path (cache hit, line 366 `TryGetValue`) is lock-free. Concurrent misses on the same key would at worst repeat the (idempotent) reflection and write the same value — the comment at line 381 is correct. Blazor processes field changes on a per-circuit sync context, so contention is unlikely anyway. No hot-path concurrency cost.

**Memory.** The static cache is never evicted except on hot-reload (`ClearCache`, line 390). Its size is bounded by the number of validated (type, field) pairs — the app's schema, not user/request volume. This is the pre-existing cache design, unchanged and unamplified by this PR; not an unbounded-growth leak.

## Verdict

No material performance issue. This is a cached, cold-path reflection lookup: the added second `GetProperty` runs miss-only, once per (type, field) key for the process lifetime, and is off the lock-free hot path. The author's DeclaredOnly→FlattenHierarchy choice also avoids the `GetProperties()` allocation/sort and the BaseType-walk overhead the prior reviewers weighed, so it is the cheaper of the alternatives considered.

```json
[]
```

## Considered But Not Flagged

- **Second `GetProperty` (FlattenHierarchy) call on cache miss** (line 376-378) — Cost repeats per (type, field) key, at most once per process lifetime because of the static cache; off the hot path. Bounded, cold, sub-millisecond total. Anchor 0 (not a finding: bounded input on a cold path).
- **Inherited-property path now costs two reflection calls instead of one** (lines 370-379) — Same reasoning: doubling applies only to misses, fully bounded by the cache. Not a scale regression. Anchor 0.
- **`ConcurrentDictionary` indexer write under concurrent misses** (line 382) — Striped-lock write, miss-only; hot path is lock-free `TryGetValue`. Redundant work on simultaneous same-key miss is idempotent and bounded to once per key. Anchor 0.
- **Static cache never evicted (except hot-reload)** (lines 46, 388-391) — Pre-existing design, unchanged by this PR. Bounded by app model-schema size, not by request/user volume; not an unbounded-growth leak. Not amplified by the change, so not reportable even as pre-existing. Anchor 0.

## Probe Requests
None — analysis is static and conclusive; no .NET SDK or execution needed.
