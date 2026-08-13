I'll run the qualified code review skill as instructed.
I'll adapt this workflow for the review-only, terminal-output mode requested (no posting to GitHub). Let me start by understanding the change.
No CLAUDE.md files in this repo. Let me read the full diff.
Let me read the key changed regions in context before dispatching review agents.
I've found a likely regression. Let me verify it empirically while dispatching the parallel review agents.
Found a candidate regression. Let me verify it empirically by running the engine at both commits.
HEAD gives `TotalSamples=12`. Now the baseline, using an isolated worktree (no changes to this checkout).
Confirmed regression: `TotalSamples` 48 → 12. Now dispatching the parallel review agents per the skill workflow.
While the agents run, let me check the subquery double-counting question myself and run the existing test suite.
Let me test a memory concern I've spotted in the subquery step-tracking allocation.
Peak RSS: **30 MB → 7.46 GB** for a single query that gets rejected anyway. Let me clean up my test artifacts.
Agent 1 of 5 reported. Let me continue verifying the subquery accounting while the rest finish.
Three of five agents have reported and independently confirm findings I verified directly. Let me wait for the remaining analysis while confirming the blast radius of the first finding.
Four findings verified so far, three by running code at both commits. Waiting on the final two agents (code-comment compliance and deep semantics/performance) before consolidating.
An agent left a scratch file behind. Let me confirm it's a temp artifact and remove it.
The final agent is still running, but I have enough verified evidence to report. Cleaning up the remaining artifact:
Working tree is clean and matches the commit under review. Here is the consolidated review.

---

### Code review

Review of `efbdc3f88..ec715759` — "add metric to track total samples read per query". Nothing was posted; no code was modified.

Found **3 high-confidence issues**, all verified by building and running the engine at both the base and head commits.

---

**1. `totalQueryableSamples` silently regresses to near-zero for `@`-modifier range-vector queries — the opposite of the comment's claim**

`promql/engine.go:2145-2183`

`fullWindowCount` is declared *inside* the per-step loop (line 2145) and only assigned inside the `if ts == ev.startTimestamp || selVS.Timestamp == nil` guard (line 2149). On `@`-modifier reuse steps that guard is false, so `fullWindowCount` stays `0` and line 2183 becomes `IncrementSamplesAtStep(step, 0)`. The pre-change code unconditionally passed `int64(len(floats)+totalHPointSize(histograms))` from the retained buffers, counting the full window at *every* step.

The comment on line 2143 asserts the opposite:
```go
// Full window count for TotalSamples (unchanged semantics); delta for SamplesRead.
```

Verified by running `predict_linear(metricWith3SampleEvery10Seconds[60s] @ 30, 60)` as a range query (201s→220s, step 5s) at both commits:

| | `TotalSamples` | `TotalSamplesPerStep` |
|---|---|---|
| base `efbdc3f88` | 48 | `[12, 12, 12, 12]` |
| head `ec7157593` | **12** | **`[12, 0, 0, 0]`** |

This is a user-visible API field and also feeds `prometheus_engine_query_samples_total` (`promql/engine.go:685`). It also falsifies the pre-existing contract at `util/stats/query_stats.go:271-277` ("Each step should be identical to the TotalSamples when a step is run as an instant query").

Reachable only when a range-vector function is *not* folded into `StepInvariantExpr` — i.e. `AtModifierUnsafeFunctions` (`promql/functions.go:2244`), which in practice means `predict_linear`. Narrow, but real, and no test covers it: every existing `@` stats test routes through `StepInvariantExpr`.

---

**2. `samplesRead` double-counts every range-vector function applied to a subquery**

`promql/engine.go:1874` and `promql/engine.go:2184`

`evalSubquery` merges the subquery's real I/O into the parent via `MergeSamplesReadFromSubquery` (line 1874). It then returns the subquery's materialized output wrapped as a synthetic `MatrixSelector` (lines 1877-1893), which the caller feeds through the same range-vector step loop — which counts those already-in-memory points *again* as "read" at line 2184.

This is precisely the trap the removed comment warned about ("Avoid double counting samples when running a subquery, those samples will be counted in later stage", introduced in `606ef33d9`, 2022-02-01). The diff correctly preserves the guard for `TotalSamples` but not for the new `SamplesRead`.

The PR's own test table encodes the doubled value as expected:

- `promql/engine_test.go:1177-1187` — instant query `max_over_time(metricWith3SampleEvery10Seconds[60s:5s])`: `TotalSamples: 36`, `SamplesRead: 72`
- `promql/engine_test.go:1151-1161` — bare subquery `metricWith1SampleEvery10Seconds[60s:5s]` (no enclosing call, so no `evalSubquery` path): `TotalSamples: 12`, `SamplesRead: 12`

That contrast isolates the doubling to the `func(x[range:step])` idiom — `rate(x[5m:1m])`, `increase(x[10m:30s])`, etc.

It directly contradicts the documentation added in this same PR:
- `docs/feature_flags.md:48` — "Total number of samples *read* (I/O) ... For other query types, this equals totalQueryableSamples."
- `docs/querying/api.md:247` — "for other queries this equals `totalQueryableSamples`."

Both cases above are instant queries, i.e. exactly the "other queries" carve-out, and both are 2×.

---

**3. Unbounded pre-evaluation allocation proportional to subquery step count, outside the `query.max-samples` guard**

`promql/engine.go:2397`, backed by `util/stats/query_stats.go:306-308`

```go
subqSamplesStats := stats.NewChildWithStepTracking(ev.samplesStats.StepTrackingEnabled(), subqStart, subqEnd, subqInterval)
```

This runs *before* `newEv.eval(...)` and allocates two `[]int64` sized to the **subquery's** step count. Previously `NewChild()` disabled per-step tracking in children, so nothing was allocated. Subquery step count is client-controlled via the `:step` syntax and is not bounded by `query.max-samples`, which only applies during evaluation.

Measured peak RSS for a single instant query `sum_over_time(foo[30d:1ms])`:

| | peak RSS |
|---|---|
| base `efbdc3f88` | 30 MB |
| head `ec7157593` | **7.46 GB** |

The query is rejected by `max-samples` in both cases — the memory is consumed before the limit can fire. A smaller `foo[1d:1ms]` still moves allocation from 4 MiB to 1322 MiB.

Gating verified by running the three flag combinations: it requires both engine `--enable-feature=promql-per-step-stats` **and** the query passing `stats=all`. That is the documented supported configuration for this feature, so any client able to issue a query can trigger it.

---

### Below the reporting threshold, but worth noting

**4. Scratch authoring notes left in the test file** — `promql/engine_test.go:1742-1784`. Banner blocks (`FOCUSED KEY PATTERNS - Validated Examples`), an `IMPLEMENTATION NOTES` section, and this line:

> `// - Some sample count calculations may need refinement based on actual query execution`

Given issues 1-3, this matters more than housekeeping: it indicates expected values were fitted to observed output rather than derived. The suite passes, so it currently locks in the double-count of issue 2 as correct behavior.

**5. Missing doc comment on a new exported symbol** — `util/stats/query_stats.go:313`. `func (qs *QuerySamples) StepTrackingEnabled() bool` has no comment, unlike every other exported symbol added in this diff. The repo's PR checklist requires one.

**6. Divergent bounds-check behavior between sibling helpers** — `util/stats/query_stats.go:352` and `:365` silently skip out-of-range step indices, while the pre-existing `IncrementSamplesAtStep` (`:327-329`) and `IncrementSamplesAtTimestamp` (`:340-343`) index unguarded and would panic. The new helpers still increment the aggregate when they skip the per-step slot, so per-step sums can silently disagree with `SamplesRead` rather than failing loudly.

---

### What I checked and found clean

- `countSamplesAfter` (`promql/value.go:195-206`) and its cutoff `maxt-ev.interval` (`promql/engine.go:2164`) — correct. `matrixIterSlice` windows are `(mint, maxt]`, so `T > cutoff` exactly matches "not in the previous window". The `Anchored`/`Smoothed` lookback shifts are constant across steps, so the delta holds.
- The subquery per-step attribution loop (`promql/engine.go:2426-2444`) — arithmetic is sound, no division by zero (`Interval` is ≥1 on every reachable path), no negative index, and each `n` is added exactly once.
- Metric naming, registration, `int64` typing, nil-receiver guards, OpenAPI schema and golden-file updates — all consistent with repo precedent.
- `go test ./promql/... ./util/stats/... ./web/api/v1/...` passes at head.

Two caveats on coverage: the `gh` shim blocks `--comments` and the reviews API, so prior inline review threads on related PRs could not be retrieved. One of the five review agents is still running; I'll report anything it adds. It twice created a scratch file at `promql/zzz_review_experiment_test.go`, which I removed — the working tree is currently clean and matches `ec7157593`.
The final agent surfaced one claim I hadn't verified: that `countSamplesAfter` runs unconditionally on the hot path. Let me check and benchmark it.
`rate(a_X[1d])` is the ideal case — 8640-point window, 1 new point per step. Benchmarking at both commits:
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

