All three agents are done and the working tree is clean at `ec7157593`. Final consolidated review.

The third agent independently reproduced **finding #1** via a different reachability route than mine — a two-argument function whose sibling argument is non-invariant, which blocks `StepInvariantExpr` promotion:

```
quantile_over_time(scalar(other)/100, metricWith1SampleEvery10Seconds[60s] @ 30)
  base efbdc3f88:  TotalSamples=15, perStep [5,5,5]
  head ec7157593:  TotalSamples=7,  perStep [5,1,1]
```

Two independent routes (`predict_linear` via `AtModifierUnsafeFunctions`, and a non-invariant sibling arg) reaching the same defect, each differentially tested against the base commit. It also confirmed the `SamplesRead=0` half of that branch is correct and intentional — the bug is specifically `TotalSamples`.

It found no panics, division-by-zero, or off-by-one in `evalSubquery`, the subquery step-attribution loop, `StepInvariantExpr`, or `countSamplesAfter` after exercising nested subqueries, negative offsets, `offset`+`@`, histograms, and huge-step/tiny-range subqueries. That matches my own reading, so I'm treating those areas as clear.

---

### Code review

Found 4 issues:

**1. `TotalSamples` / `prometheus_engine_query_samples_total` undercounts when a range-vector selector carries `@` and the enclosing call isn't step-invariant** — `promql/engine.go:2145`, `:2183`

`var fullWindowCount, samplesReadCount int64` is declared outside the `if ts == ev.startTimestamp || selVS.Timestamp == nil` block, so on reused steps it stays `0` and `IncrementSamplesAtStep(step, 0)` drops the window. The prior code computed the count at the increment site, unconditionally. Contradicts the change's own comment at `:2143` ("unchanged semantics") and the field doc at `util/stats/query_stats.go:276`. Untested — every `@` case in `TestQueryStatistics` is either single-step or gets promoted to `StepInvariantExpr`.

https://github.com/prometheus/prometheus/blob/ec715759357ab2230118539062a37a3cb051645c/promql/engine.go#L2143-L2167
https://github.com/prometheus/prometheus/blob/ec715759357ab2230118539062a37a3cb051645c/promql/engine.go#L2181-L2186

**2. `SamplesRead` counts subquery samples twice** — `promql/engine.go:1874` and `:2184`

`MergeSamplesReadFromSubquery` merges the subquery's reads, then the materialized matrix is re-scanned by the range-vector loop and counted again. The deleted comment ("Avoid double counting samples when running a subquery") came from `606ef33d9` and guarded exactly this. Verified at exactly 2× across every `func_over_time(metric[range:step])` shape; `samplesRead` ends up *exceeding* `totalQueryableSamples`, which is backwards for an I/O counter. The new tests encode the doubled values (`promql/engine_test.go:1177`, `:1810`, `:1826`, `:1841`) rather than catching them.

https://github.com/prometheus/prometheus/blob/ec715759357ab2230118539062a37a3cb051645c/promql/engine.go#L1866-L1877
https://github.com/prometheus/prometheus/blob/ec715759357ab2230118539062a37a3cb051645c/util/stats/query_stats.go#L418-L434

**3. Unbounded up-front allocation from subquery step tracking** — `promql/engine.go:2397`, `util/stats/query_stats.go:411`

Allocates two `[]int64` sized by `range/step` before evaluation, controlled entirely by query text and unconstrained by `query.max-samples`. Measured 0 MiB → 54/109 MiB for `m[1h:1ms]`/`m[2h:1ms]` with `MaxSamples: 50`; both queries succeed in ~0.1s, so neither the sample limit nor the timeout engages. Flag-gated behind `promql-per-step-stats` + `stats=all`.

https://github.com/prometheus/prometheus/blob/ec715759357ab2230118539062a37a3cb051645c/promql/engine.go#L2395-L2399

**4. Vacuous test assertions** — `web/api/v1/api_test.go:983`, `:999`

`require.GreaterOrEqual(t, qs.Samples.SamplesRead, int64(0))` holds unconditionally for a monotonic counter and would pass if the field were never populated.

https://github.com/prometheus/prometheus/blob/ec715759357ab2230118539062a37a3cb051645c/web/api/v1/api_test.go#L979-L1001

Plus two documentation corrections: `docs/feature_flags.md:44-48` presents `samplesRead` as part of the per-step-stats feature when it is unconditional, and the "for other queries this equals totalQueryableSamples" claim (`docs/querying/api.md:246`) is overbroad — it is legitimately unequal for step-invariant expressions, where the code is correct.

**Blocking issue: #1**, with **#2** close behind. Both affect the aggregate counters and the `stats=true` API response on every server, independent of any feature flag — I verified this with `EnablePerStepStats: false`. #1 silently changes an existing user-visible metric the change claims to leave alone; #2 ships a new I/O counter that is systematically ~2× actual reads for subquery workloads.

Nothing was posted and no code was modified; the tree is clean at `ec7157593`.
