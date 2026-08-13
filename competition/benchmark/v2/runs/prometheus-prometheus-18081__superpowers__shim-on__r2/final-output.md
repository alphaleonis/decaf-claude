Reviewer subagent's report, verbatim:

---

I reviewed the diff in three passes (engine semantics, `util/stats` API, tests/docs), and verified the significant findings empirically against base and head in throwaway worktrees (now removed; this checkout is untouched).

### Strengths

- **The core delta idea is right and cleanly derived.** In the range-vector loop, "new points at this step" = points with `T > maxt - ev.interval` is exactly correct given the previous window ended at `maxt - interval`, and it handles the boundary correctly (strictly-after, since `maxt_prev` was inclusive). It also stays correct for the `Anchored`/`Smoothed` variants because both windows shift by the same amount. I hand-checked several of the new expectations (`max_over_time(metricWith3SampleEvery10Seconds[60s])` → 18/0/3/0) and they are genuinely right, not just "whatever came out".
- **The strongest thing in the test change** is the added per-step-stats-disabled re-run in `promql/engine_test.go:2432-2440`: asserting `SamplesRead` is identical with per-step tracking on and off is precisely the invariant most likely to break, and it holds across ~120 cases.
- Nil-receiver guards were added consistently (`InitStepTracking`, `StepTrackingEnabled`, the two new `Increment*` methods), matching the existing defensive style in `util/stats`.
- OpenAPI schema additions mirror the existing `totalQueryableSamplesPerStep` shape exactly, and both 3.1 and 3.2 goldens were regenerated. `gofmt` clean; `go vet` shows only pre-existing warnings.
- `promql`, `util/stats`, and `web/api/v1` all pass at head.

### Issues

#### Critical (Must Fix)

**1. `promql/engine.go:2145-2183` — silent regression in the existing `totalQueryableSamples` stat and `prometheus_engine_query_samples_total` metric.**

`fullWindowCount` is now declared outside but only *assigned inside* the `if ts == ev.startTimestamp || selVS.Timestamp == nil` block. The old code computed `len(floats)+totalHPointSize(histograms)` unconditionally after that block, so when the `@` modifier caused data reuse across steps, every step still counted the full window. Now those steps count 0. The inline comment claims "(unchanged semantics)" — it is not unchanged.

This is reachable whenever the enclosing call is in `AtModifierUnsafeFunctions` (`promql/functions.go:2244`), because `preprocessExprHelper` then refuses to wrap the call in a `StepInvariantExpr`, so the multi-step loop runs with `selVS.Timestamp != nil`. `predict_linear` is the concrete case. Measured (range query 201→220, step 5s, one series every 10s):

```
predict_linear(m[60s] @ 30, 60)
  base: TotalSamples=16  perStep={201000:4 206000:4 211000:4 216000:4}
  head: TotalSamples=4   perStep={201000:4 206000:0 211000:0 216000:0}
```

No test covers this, which is why CI is green. Fix: keep `fullWindowCount := int64(len(floats) + totalHPointSize(histograms))` at the point of use (just before `IncrementSamplesAtStep`), and only compute `samplesReadCount` inside the branch.

**2. `promql/engine.go:2397` + `util/stats/query_stats.go:411` — unbounded, query-controlled allocation that is made *before* `query.max-samples` can reject the query.**

`NewChildWithStepTracking` calls `InitStepTracking`, which allocates *two* `[]int64` of `numSteps` for the subquery's own step grid. The subquery step count is entirely user-controlled and is not bounded by `max-samples`, and the arrays are allocated up front, before `newEv.eval` runs. Measured with `MaxSamples=10` (query fails immediately) and per-step stats on:

```
sum_over_time(m[100d:1s])   base: 0 MiB allocated   head: 131 MiB allocated
```

`[1y:1s]` scales this to ~500 MiB per request. Previously `NewChild()` allocated nothing. This is gated behind `--enable-feature=promql-per-step-stats` **and** `stats=all`, so it is not default-on, but for anyone running that flag it is a trivial single-request OOM. At minimum the subquery per-step arrays need a cap (and `InitStepTracking` allocating `TotalSamplesPerStep` here is pure waste — that array is discarded).

**3. `promql/value.go:195` + `promql/engine.go:2164` — ~25% throughput regression in the range-vector hot loop, incurred unconditionally.**

`countSamplesAfter` does a full linear scan of the retained window at every step of every series, even when the caller requested no stats at all (`SamplesRead` always feeds the new counter, so the code path is never skipped). Measured on a 1h window / 10s step / 2000 steps, `-count 4`:

| query | base | head |
|---|---|---|
| `rate(a_hundred[1h])` | ~76 ms/op | ~96 ms/op |
| `rate(a_one[1h])` | ~773 µs/op | ~987 µs/op |

I isolated the cause by stubbing the `countSamplesAfter` call to `0` in the head tree: timings returned to base exactly (77 ms / 765 µs). So it is entirely this scan.

Both `floats` and `histograms` are sorted by timestamp, so this should be a `sort.Search` for the cutoff index (`len(floats)-idx` for floats; sum `size()` only over the histogram tail). Better still, `matrixIterSlice` already knows how many points it appended and could return that count directly, making it free.

#### Important (Should Fix)

**4. `samplesRead` double-counts subqueries, so it can be 2× `totalQueryableSamples`.** In `evalSubquery` (`promql/engine.go:1874`) the subquery's storage reads are merged into the parent, and then the outer range-vector loop counts the subquery's *output* points as "read" again. The new tests encode this: instant `max_over_time(metricWith3SampleEvery10Seconds[60s:5s])` expects `TotalSamples: 36, SamplesRead: 72`; the range-query case `histogram_quantile(0.9, rate(...[2m:30s]))` expects 364 vs 416. For a stat documented and named as I/O, being consistently larger than the "loaded" stat is the opposite of what a user will expect. Either the outer pass over subquery output should not contribute to `SamplesRead`, or the merge should be dropped — not both.

**5. `docs/feature_flags.md:48` and `docs/querying/api.md:247` state a claim the code contradicts:** "For other query types, this equals totalQueryableSamples." That is false for subqueries (issue 4, 2×) and false for `@`-modifier / step-invariant expressions, where `IncrementSamplesReadAtStep(0, …)` at `promql/engine.go:2472` adds the value once while `TotalSamples` is added per step (the diff's own test expects `SamplesRead: 12` vs `TotalSamples: 48` for `max_over_time(m[60s] @ 30)` over 4 steps). Since the docs are the only specification here, they need to match.

**6. The "read = I/O" framing overclaims for plain vector selectors.** `evalSeries` (`promql/engine.go:1817`, `1840`) increments `SamplesRead` once per step per point, so lookback re-counting is untouched: the new test for `metricWith3SampleEvery10Seconds` over 201→216 at 5s expects `SamplesRead: 12` from ~6 raw stored samples. The result is that `prometheus_engine_query_samples_read_total` is neither "samples loaded" nor "samples read from storage" but a third quantity that dedupes exactly one of the several over-counting paths. The counter `Help` string ("The total number of samples read by all queries") should say what it actually measures, or the dedup should be applied consistently.

**7. `promql/engine.go:2424-2445` — the per-step attribution heuristic is arbitrary and undocumented at the API surface.** Subquery steps before the outer start are folded into outer step 0 and steps past the last outer step are clamped onto the final step ("steps after last outer → last step" appears in ~10 test expectations). The totals are preserved, but `samplesReadPerStep` then has spikes at the first and last step that do not correspond to work done in those steps. `docs/querying/api.md:248` describes it only as "delta semantics for range-vector", which does not prepare a consumer for this. Also note this block reaches into `ev.samplesStats.SamplesReadPerStep[...]` directly rather than going through the accessors introduced two files over — worth keeping the encapsulation.

**8. `util/stats/query_stats.go:423` — `MergeSamplesReadFromSubquery` merges index-wise with no check that the two layouts agree.** It silently truncates to `min(len)` and ignores `StartTimestamp`/`Interval` entirely. It happens to be safe at the single call site because the child is constructed from the parent's layout, but this is an exported method in a package consumed downstream (Thanos/Cortex/Mimir all import `util/stats`). A mismatched caller gets silently wrong numbers rather than an error. Either unexport it, or compare `StartTimestamp`/`Interval` and no-op/panic on mismatch.

**9. Test expectations were derived from observed output rather than reasoned about, and the scratch notes shipped.** `promql/engine_test.go:1777-1783` still contains:

```
// IMPLEMENTATION NOTES:
// - Some sample count calculations may need refinement based on actual query execution
```

with sibling comments "corrected values" and "Actual behavior: single step shows 1 effective sample". A table of ~120 golden numbers whose own comments say they may be wrong is a change-detector, not a specification — and it is exactly why issue 1 slipped through. This block must go, and the subquery expectations that encode issue 4 need to be re-derived once that is settled.

**10. Duplicate test cases.** `sum_over_time(metricWith1SampleEvery10Seconds[30s:30s])` at `Start: time.Unix(90, 0)` appears three times with byte-identical expectations; `sum(max_over_time(metricWith3SampleEvery10Seconds[20s:10s]))` at `Start: time.Unix(201, 0)` twice. They also produce colliding `t.Run` names.

**11. `web/api/v1/api_test.go:983` — `require.GreaterOrEqual(t, qs.Samples.SamplesRead, int64(0))` cannot fail** for a monotonically-incremented counter; it asserts nothing. The `stats=all` case one block down at least checks `SamplesReadPerStep` is non-nil. Assert an actual expected value, or drop it.

#### Minor (Nice to Have)

**12. `util/stats/query_stats.go:401-417` — two child-creation APIs with divergent semantics.** `(*QuerySamples).NewChild()` is a method that ignores its receiver and always disables per-step stats; `NewChildWithStepTracking` is a package function that inherits it. `StepInvariantExpr` still uses the former and subqueries the latter, so per-step attribution silently collapses to step 0 under any `@`. If that is deliberate it deserves a comment; otherwise make them one API.

**13. `promql/engine_test.go:51` — removing `defaultEpsilon` is unrelated to this change.** It is genuinely dead (the live one is in `promql/promqltest/test.go:59`), but it is scope creep in a diff that is already hard to review.

**14. `docs/feature_flags.md:44-50` documents `peakSamples` and both server counters inside the `promql-per-step-stats` section,** though neither is gated by that flag. Readers will reasonably infer they need the flag.

**15. `promql/engine_test.go:2432` — the second `runQuery` reassigns `stats`,** so the subsequent `stats.Samples.PeakSamples-1` max-samples check uses the peak from the per-step-*disabled* run, which is never asserted. Harmless today (peaks match) but it makes the max check depend on an unverified value.

### Recommendations

- Split this into two changes. The `evalSubquery`/`SubqueryExpr` restructuring (new child stats layout, cross-grid attribution) is the source of issues 2, 4, and 7 and is the part that needs design discussion; the range-vector delta (issues 1 and 3) is self-contained and nearly landable once the two bugs are fixed.
- Decide and write down what `samplesRead` *is* before refining the numbers. Right now it is "totalQueryableSamples, except deduped for range-vector selectors and double-counted for subqueries" — that is not a quantity anyone can act on. If the goal is "storage reads", the natural instrumentation point is the querier/`storage.Buffer`, not the evaluator.
- Add a direct test for the `@`-modifier path (`predict_linear(m[…] @ ts, …)` over multiple steps) asserting `TotalSamples` is unchanged from base — the whole class of stats regressions is currently untested.
- Run `BenchmarkRangeQuery` with a wide window (`rate(x[1h])`) as part of this PR's evidence; the default bench cases use a 1m window (~6 points) and hide the regression at ~2%.

### Assessment

**Ready to merge?** No.

**Reasoning:** Three verified blockers: a silent regression in the pre-existing `totalQueryableSamples` stat and `prometheus_engine_query_samples_total` metric for `@`-modifier range-vector functions (16 → 4, untested), a ~131 MiB up-front allocation for a subquery that `max-samples` would have rejected instantly (0 → 131 MiB, unbounded by query input), and a measured ~25% throughput regression in the core range-vector loop from an unconditional linear scan that a binary search would make free. Underneath those, the semantics of the new `samplesRead` stat need to be pinned down before the ~120 golden test expectations are worth anything — several of them currently encode a 2× subquery double-count that the accompanying docs explicitly deny.
