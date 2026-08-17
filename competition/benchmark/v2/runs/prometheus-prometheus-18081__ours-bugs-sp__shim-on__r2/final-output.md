✅ Review complete: `.decaf/code-reviews/CODE_REVIEW_2026-08-17_08-57-15.md`

**Verdict: ❌ NEEDS_CHANGES** — `bugs-sp` (single-seat, `reach=narrow`), 2 High · 2 Low · 2 Minor. No prior reviews exist in this repo, so Step 7 (recurring findings) was skipped. Working tree verified unchanged.

The two blocking findings, both verified by execution:

**#1 — `promql/engine.go:2145`: the change breaks the *existing* `totalQueryableSamples` statistic.** `fullWindowCount` is declared inside the per-step loop but only assigned inside the `if ts == ev.startTimestamp || selVS.Timestamp == nil` block. For an `@`-anchored matrix selector under a non-step-invariant call, that block is skipped after step 0, so `IncrementSamplesAtStep(step, fullWindowCount)` adds 0 where the old code added the retained window size. Measured on `predict_linear(m[60s] @ 30, scalar(m))`: `TotalSamplesPerStep` goes from `[5 5 5 5]` before to `[5 1 1 1]` after. This also moves `prometheus_engine_query_samples_total`, contradicting the change's own stated invariant that total-samples semantics are unchanged.

**#2 — `promql/engine.go:1874`: `samplesRead` double-counts subqueries.** The new `MergeSamplesReadFromSubquery` in `evalSubquery` re-introduces exactly the double count the pre-change comment guarded against ("Avoid double counting samples when running a subquery, those samples will be counted in later stage") — the materialized subquery matrix is then counted again by the range-vector loop at `:2184`. A mutation probe in an isolated worktree (only that line commented out) turned `SamplesRead: 72` into `36`, which is precisely `TotalSamples` for that query. The inflated numbers are baked into the new test expectations, and it makes `samplesRead > totalQueryableSamples` for instant subqueries, contradicting `docs/feature_flags.md:48`.

Lower severity: per-step arrays are now allocated for every subquery evaluation sized by the *subquery's* step count (~1.4 MB for `foo[1d:1s]`, uncharged against `max-samples`), and the new `web/api/v1/api_test.go:983` assertion `GreaterOrEqual(SamplesRead, 0)` is tautological — it passes if the feature is wired to nothing.

One caveat on interpretation: `bugs-sp` is the experimental single-seat path, so these results carry one agent's variance with no corroboration, screen, or validation wave behind them.
