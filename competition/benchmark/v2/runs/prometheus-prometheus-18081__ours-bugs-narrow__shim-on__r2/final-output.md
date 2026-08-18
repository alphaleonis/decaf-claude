✅ Review complete: `.decaf/code-reviews/CODE_REVIEW_2026-08-18_22-23-43.md`

**Verdict: ❌ NEEDS_CHANGES** — 3 High, 1 Low. All four were verified empirically by the seat (three by executed probes against both base and head, one by reading).

| # | Severity | Where | What is wrong |
|---|---|---|---|
| 1 | 🟠 High | `promql/engine.go:2145`, `:2183` | `fullWindowCount` is assigned only inside the `@`-reuse guard, so steps that reuse retained data now contribute 0 to the **existing** `totalQueryableSamples` and to `prometheus_engine_query_samples_total`. Measured 20 → 8 on `quantile_over_time(scalar(m), m[60s] @ 30)`. The change claims that statistic is unchanged, and a comment added in the same diff (`util/stats/query_stats.go:276`) now contradicts the code. |
| 2 | 🟠 High | `promql/engine.go:2397` | `NewChildWithStepTracking` sizes two `[]int64` by the **subquery's** step count, which nothing bounds, before any sample is read — so `query.max-samples` cannot stop it. `sum_over_time(m[10000s:1ms])` allocated 152.7 MB at head vs 0.1 MB at base, scaling linearly (`[1000000s:1ms]` ≈ 16 GB). Previously `NewChild()` allocated nothing. |
| 3 | 🟠 High | `promql/engine.go:1874` with `:2184` | `evalSubquery` merges the subquery's `SamplesRead` **and** the outer range-vector loop counts the materialized points again. `max_over_time(m[60s:10s])` reports `SamplesRead=12` against `TotalSamples=6`; nested, 65 vs 5. This falsifies the invariant the same change documents in three places ("for other query types, this equals totalQueryableSamples"). `TotalSamples` deliberately avoids the double count; `SamplesRead` does not. |
| 4 | 🟢 Low | `promql/engine_test.go:1777-1783`, `:1539`, `:1544` | New expectations are characterization values, and the file says so (`// Some sample count calculations may need refinement based on actual query execution`; `TotalSamples: 1, // Actual behavior: …`). This is the mechanism by which #3's inflation ships green — `:1548` asserts `SamplesRead: 2, // subquery + outer`. |

Two things worth flagging about the review itself: the `bugs` preset ran a single seat with no validation wave, so these findings carry no corroboration — the confidence rests on the seat's probes, which are reproducible from the report. And no full build/lint/test gate was run (Step 3.0 does not run on this path); only `TestQueryStatistics` was executed, and it passes at head.
