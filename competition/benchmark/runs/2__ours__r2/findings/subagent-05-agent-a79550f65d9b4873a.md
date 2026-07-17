# subagent agent-a79550f65d9b4873a

## Performance Review — EditContextDataAnnotationsExtensions.cs

**Scope:** `TryGetValidatableProperty` change (single `GetProperty` call → up to two, gated by `BindingFlags.DeclaredOnly` then `FlattenHierarchy`).

### Analysis

- **Hot path identification confirmed**: `TryGetValidatableProperty` is called from `OnFieldChanged` (line 94), which fires on every field-change notification — effectively per-keystroke for text inputs. This is a legitimate hot path.
- **But the added cost sits entirely behind the cache miss branch** (lines 366-383). The `ConcurrentDictionary.TryGetValue` at line 366 is O(1) and unconditional on every call; the new second `GetProperty` call only executes when (a) the cache misses (first time this exact `(ModelType, FieldName)` pair is seen in process lifetime) AND (b) the `DeclaredOnly` lookup returned `null` (property inherited rather than declared on the leaf type).
- **Multiplication bound**: cost repeats at most once per **unique `(ModelType, FieldName)` pair**, not per field-change event, not per row, not per form instance. For a typical Blazor app the distinct-type × distinct-field-name space is small (tens to low hundreds) and bounded by the app's own type/view-model surface — it does not grow with data volume, request volume, or keystroke count. Once cached, every subsequent `OnFieldChanged` for that model type / field (arbitrarily many keystrokes, arbitrarily many component instances sharing that runtime type) pays only the O(1) dictionary lookup, identical to before the change.
- **Reflection cost itself**: `Type.GetProperty` with explicit `BindingFlags` is a bounded, single-type metadata scan (not proportional to any collection the app manages); doubling it from one call to two on a first-miss-only path is negligible even before considering the cache.
- **Cache growth**: the `_propertyInfoCache` is static/process-lifetime and unbounded in principle (unchanged by this diff — it was already unbounded pre-change), evicted only by `ClearCache()` on hot-reload metadata updates (dev-time only). This is pre-existing behavior, not something this diff introduces or amplifies, and the key space (type × field name) is inherently small in realistic apps, not correlated with row/record counts.
- **Cheaper single-call formulation**: none that preserves the fix's semantics. `DeclaredOnly` and `FlattenHierarchy` are not meaningfully combinable in one call to get "prefer most-derived declaration, else search hierarchy" — the two-step precedence is the standard reflection idiom for resolving property-hiding ambiguity. Since the extra call is cache-gated, there's no performance reason to compress it into one call at the cost of correctness (that tradeoff is dotnet-reviewer's territory, not mine).

No finding clears the anchor-75 bar. The doubled reflection call is a textbook case of a cache fully amortizing added per-miss cost out of a hot path.

```json
[]
```

## Considered But Not Flagged

- **Doubled `GetProperty` call on cache miss** (lines 370-379): cost repeats once per unique `(ModelType, FieldName)` pair for the life of the process, gated behind a static cache that's hit on every subsequent `OnFieldChanged` call for that pair. Not hot at any realistic scale — anchor 0 (false positive; cache clearly amortizes).
- **Unbounded static cache (`_propertyInfoCache`)**: real cost category (`PERF_MEMORY`) in principle, but pre-existing (the cache existed, unbounded, before this diff) and not amplified by the diff — the diff doesn't add new keys or change key cardinality, only what happens once per key on first miss. Out of scope as "not introduced/amplified by this changeset."
- **Speculative exception-storm scenario**: if a model has 3+ level inheritance with property hiding at a non-leaf level (return-type-covariant hiding below the runtime leaf type), the second `GetProperty(..., FlattenHierarchy)` call could itself throw `AmbiguousMatchException`, which would propagate uncaught out of `TryGetValidatableProperty` before the cache write at line 382 — meaning the double-reflection cost (and the exception) would repeat on every keystroke for that field instead of being cached. This is a real theoretical multiplication (per keystroke, unbounded), but (a) requires a specific multi-level hiding shape not established as present in any real model in this codebase or its test suite, and (b) the actual defect here is an unhandled exception (correctness), not a cost decision — belongs to dotnet-reviewer/quick-reviewer if pursued. Anchor 25, not reported.
