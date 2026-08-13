The final agent has reported. It independently confirmed findings 1 and 2, and raised one claim I hadn't checked — which benchmarking confirms as a **fourth high-confidence issue**.

---

### Addendum to the review

**4. `countSamplesAfter` adds an ungated O(window) scan to the PromQL hot path — ~34% slowdown on wide-window range queries**

`promql/engine.go:2164`, `promql/value.go:192-205`

```go
samplesReadCount = countSamplesAfter(floats, histograms, maxt-ev.interval)
```

This is not gated behind `EnablePerStepStats` or any feature flag — the aggregate `SamplesRead` field is tracked unconditionally, so the scan runs on **every step of every range-vector function evaluation, for every query**.

The cost is asymptotic, not constant. `matrixIterSlice` is specifically optimized to retain overlapping points and append only new ones, so its incremental per-step cost is O(new points). `countSamplesAfter` then linearly scans the *entire* retained window from the front. For `rate(foo[1d])` at 10s steps that is ~8640 comparisons per step to discover ~1 new point. The slices are time-sorted, so a reverse scan or binary search would make this O(new points) and remove the regression.

Measured with the repo's own `BenchmarkRangeQuery/expr=rate(a_one[1d]),steps=1000` (`promql/bench_test.go:336`), `-benchtime 10x -count 5`, engine and query opts both with per-step stats **disabled**:

| | ns/op (5 runs) | B/op |
|---|---|---|
| base `efbdc3f88` | 6831k, 6937k, 6976k, 6793k, 6810k | ~880k |
| head `ec7157593` | 9199k, 9551k, 9085k, 9143k, 9220k | ~880k |

**~34% slower**, non-overlapping distributions, allocations unchanged — so the delta is pure CPU from the added scan. Notably this penalizes exactly the wide-window `rate()`/`increase()` queries that `samplesRead` is meant to help diagnose, and it is paid by every Prometheus user regardless of whether they enable `promql-per-step-stats`.

---

### Revised summary

Four high-confidence issues, all verified by building and running at both commits:

1. `promql/engine.go:2145-2183` — `totalQueryableSamples` regresses to `[12,0,0,0]` from `[12,12,12,12]` for `@`-modifier range-vector queries; contradicts the comment claiming "unchanged semantics"
2. `promql/engine.go:1874` + `:2184` — `samplesRead` double-counts range-vector functions over subqueries (36 → 72 in the PR's own test table); contradicts the docs added in the same PR
3. `promql/engine.go:2397` — subquery step-tracking allocation is unbounded and pre-evaluation; peak RSS 30 MB → 7.46 GB on a query that `max-samples` rejects anyway
4. `promql/engine.go:2164` — ungated O(window) hot-path scan; ~34% slowdown on `rate(a_one[1d])`

Plus three below-threshold notes (leftover test scaffolding at `promql/engine_test.go:1742-1784`, missing doc comment at `util/stats/query_stats.go:313`, divergent bounds-check behavior at `util/stats/query_stats.go:352,365`).

Issues 1 and 4 are unintended side effects of restructuring the existing `IncrementSamplesAtStep` call rather than of the new feature itself, so both affect users who never enable `promql-per-step-stats`. All five review agents completed; the working tree is clean and matches `ec7157593`, and all worktrees and scratch files created during review have been removed. Nothing was posted anywhere.
