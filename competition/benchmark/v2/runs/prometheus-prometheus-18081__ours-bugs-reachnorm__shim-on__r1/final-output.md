✅ Review complete: `.decaf/code-reviews/CODE_REVIEW_2026-08-18_22-08-04.md`

**Verdict: ❌ NEEDS_CHANGES** — 4 High, 2 Medium, 3 Low, 4 Minor. Preset `bugs` (single seat, `reach=norm`); no validation wave on this path. Working tree verified clean; nothing was posted or modified.

The four High findings, all verified by execution:

1. **`promql/engine.go:2145` — existing metric regresses.** `fullWindowCount` is only assigned inside the `@`-modifier reuse guard, so for `@`-modified matrix selectors it stays 0 and `totalQueryableSamples` / `prometheus_engine_query_samples_total` under-counts. Measured: `predict_linear(x[60s] @ 30, 3600)` over a 4-step range query reports `TotalSamples` 4 at head vs 16 at base. The inline comment claiming "unchanged semantics" is false, and no test covers the shape.

2. **`promql/engine.go:1874` — the new counter double-counts subqueries.** `MergeSamplesReadFromSubquery` folds in subquery reads, then the per-step loop counts the materialized matrix again. Measured: `max_over_time(m3[60s:5s])` gives `TotalSamples` 36, `SamplesRead` 72. The 2× ratio is baked into the diff's own new expectations.

3. **`promql/engine.go:2397` — unbounded allocation before `query.max-samples` applies.** Subquery children now init step tracking at *subquery* resolution: `max_over_time(foo[10m:1ms])` allocates 9.7 MB even when the query aborts after 10 samples (base: 96 KB). Requires `promql-per-step-stats` plus `stats=all`.

4. **`promql/value.go:195` — O(window) scan per step in the hot loop**, paid even with stats disabled. `BenchmarkRangeQuery` `rate(a_one[1d]), steps=1000`: ~5.80 ms → ~9.09 ms (+57%). The slices are sorted; binary search suffices.

Medium findings cover a documented invariant that is false for `@` expressions, and a ~90-case test table whose numbers were read off the implementation (including a committed "may need refinement" note) — which is why #1 and #2 pass green.
