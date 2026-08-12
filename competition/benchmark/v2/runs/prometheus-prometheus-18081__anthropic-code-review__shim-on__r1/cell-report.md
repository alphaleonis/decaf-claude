I'll invoke the qualified skill as instructed.
I'll start by getting an overview of the change under review.
No CLAUDE.md files exist in this repo. Let me examine the change.
Let me look at the key code sections in detail before dispatching review agents.
Confirmed the code layout. Let me dispatch the parallel review agents while I verify a suspected regression myself.
While those run, let me verify the suspected `@` modifier regression empirically.
These `@` cases are instant queries. Let me check for range queries with `@` and write a targeted verification.
Confirmed the path is reachable. Let me prove the regression empirically with a temporary test (removed afterward).
`predict_linear` is at-modifier-unsafe, so it is never wrapped in a StepInvariantExpr. Let me test it.
At HEAD: `totalQueryableSamples: 4`, per-step `[4,0,0,0]`. Now the baseline.
Confirmed a real regression. Let me test the subquery double-counting question.
Confirmed double-counting. Let me check whether the PR's tests bake in these doubled values.
The tests bake in exactly 2× (6→12, 39→78, 9→18), locking in the double-count. Cleaning up my temp artifacts.
`promql/engine_test.go` shows as modified — I didn't touch it. Let me check before restoring.
A review agent added a debug test case. Backing it up, then restoring the tree.
Tree is clean. Let me test one more suspected issue: unbounded up-front allocation for subquery step tracking.
Allocation scales linearly with step count, unbounded by `MaxSamples: 50`, and the query still succeeds in 0.1s. Let me confirm the baseline.
Baseline allocates 0 MiB; the change allocates 54/109 MiB. All three findings confirmed. Cleaning up.
All three agents are still running. Let me use the time to check per-step sum consistency for range queries with subqueries.
Confirmed again — and note `samplesRead` (72) exceeds `totalQueryableSamples` (36), which is semantically backwards for an I/O counter.
The agent listing isn't advancing; I have three findings verified by direct execution, which is stronger evidence than agent reports. Let me pin exact line numbers.
I have three findings verified by direct execution against both the base and head commits. (The three supplementary review agents were still running when I finalized; everything below is from my own verification, not agent reports.)

No `CLAUDE.md` exists in this repository, so there were no project-specific conventions to check against.

---

### Code review

Found 4 issues:

**1. Regression: `TotalSamples` (and `prometheus_engine_query_samples_total`) undercounts for range queries with an `@` modifier on a range-vector selector**

`promql/engine.go:2145` declares `var fullWindowCount, samplesReadCount int64` *outside* the `if ts == ev.startTimestamp || selVS.Timestamp == nil` block, so when data is reused across steps (the `@` modifier path) both stay `0`, and `promql/engine.go:2183` adds `0` to `TotalSamples`. The previous code computed `len(floats)+totalHPointSize(histograms)` from the retained slices at the increment site, counting the full window on every step.

The change's own comment at `promql/engine.go:2143` claims *"Full window count for TotalSamples (unchanged semantics)"* — that is not what the code does.

This is reachable whenever the enclosing call is not wrapped in a `StepInvariantExpr`, e.g. any function in `AtModifierUnsafeFunctions` (`promql/functions.go:2244`) such as `predict_linear`. Verified by running the same query against both commits:

```
query: predict_linear(m[60s] @ 30, 60)   range 201s→220s, step 5s

base efbdc3f88:  "totalQueryableSamples":16, perStep [[201,4],[206,4],[211,4],[216,4]]
head ec7157593:  "totalQueryableSamples":4,  perStep [[201,4],[206,0],[211,0],[216,0]]
```

No existing test covers this path — the `@` cases at `promql/engine_test.go:1034-1082` are instant queries, and `promql/engine_test.go:1352` goes through `StepInvariantExpr`, which still counts per step at `promql/engine.go:2469`.

https://github.com/prometheus/prometheus/blob/ec715759357ab2230118539062a37a3cb051645c/promql/engine.go#L2143-L2167
https://github.com/prometheus/prometheus/blob/ec715759357ab2230118539062a37a3cb051645c/promql/engine.go#L2181-L2186

**2. Subquery samples are counted twice in `SamplesRead`**

`promql/engine.go:1874` merges the subquery's `SamplesRead` into the parent via `MergeSamplesReadFromSubquery`, but the subquery result is then materialized into a matrix and walked again by the range-vector loop, which increments `SamplesRead` a second time at `promql/engine.go:2184`. The comment deleted by this change (`"Avoid double counting samples when running a subquery, those samples will be counted in later stage"`) was guarding exactly this.

Verified — every subquery reports exactly 2×:

```
instant sum_over_time(m[60s:10s]) → totalQueryableSamples:6,  samplesRead:12
instant rate(m[60s:10s])          → totalQueryableSamples:6,  samplesRead:12
range   sum_over_time(m[60s:10s]) → totalQueryableSamples:36, samplesRead:72
```

`samplesRead` exceeding `totalQueryableSamples` is backwards for a counter documented as I/O — a point can be read at most as often as it is loaded. It also contradicts the documentation added in this change (`docs/querying/api.md:246`, `docs/feature_flags.md:48`): *"For other query types, this equals totalQueryableSamples."*

The new tests encode the doubled values rather than catching them — `promql/engine_test.go:1810` (6→12), `:1826` (39→78), `:1841` (9→18) — so this locks the behavior in.

https://github.com/prometheus/prometheus/blob/ec715759357ab2230118539062a37a3cb051645c/promql/engine.go#L1866-L1877
https://github.com/prometheus/prometheus/blob/ec715759357ab2230118539062a37a3cb051645c/util/stats/query_stats.go#L418-L434

**3. Unbounded up-front allocation proportional to subquery step count, not to data read**

`promql/engine.go:2397` calls `stats.NewChildWithStepTracking(...)` with the *subquery's* step layout, which allocates two `[]int64` of `numSteps` (`util/stats/query_stats.go:306-317`) before any evaluation happens. `numSteps` is `range/step`, fully controlled by the query text and unconstrained by `query.max-samples`. Previously `NewChild()` allocated nothing.

Measured, with `MaxSamples: 50` and a 3-sample series:

```
                            base efbdc3f88    head ec7157593
sum_over_time(m[1h:1ms])        0 MiB            54 MiB
sum_over_time(m[2h:1ms])        0 MiB           109 MiB
```

Both queries return `err=<nil>` in ~0.1s — the sample limit and timeout never engage, because the allocation precedes evaluation. Extrapolating, `m[30d:1ms]` is ~2.6e9 steps ≈ 41 GiB. Gated behind `--enable-feature=promql-per-step-stats` plus `stats=all`, which limits exposure, but it is a new denial-of-service surface that the existing limits do not cover.

https://github.com/prometheus/prometheus/blob/ec715759357ab2230118539062a37a3cb051645c/promql/engine.go#L2395-L2399
https://github.com/prometheus/prometheus/blob/ec715759357ab2230118539062a37a3cb051645c/util/stats/query_stats.go#L405-L417

**4. Vacuous test assertions**

`web/api/v1/api_test.go:983` and `:999` assert `require.GreaterOrEqual(t, qs.Samples.SamplesRead, int64(0))`. `SamplesRead` is a monotonically incremented `int64` sample count, so this holds unconditionally and would pass even if the field were never populated. Minor, but these are the only API-level assertions the change adds for the new field.

https://github.com/prometheus/prometheus/blob/ec715759357ab2230118539062a37a3cb051645c/web/api/v1/api_test.go#L979-L1001

---

Issue 1 is the one I would block on: it silently changes an existing, user-visible metric and API field that this change explicitly claims to leave alone.

Note on housekeeping: one of the review agents wrote a debug test case into `promql/engine_test.go`. I reverted it (backup at `/tmp/agent-debug-change.patch`) and removed my own temporary test files and git worktrees. `git status` is clean and nothing was posted anywhere.
The historical-context agent finished. It independently confirms finding #2 and adds useful evidence.

**Corroboration for finding #2 (subquery double-count):**
- It traced the invariant to commit `606ef33d9` ("Track and report Samples Queried per query"), which introduced the very comment this change deletes — confirming the "avoid double counting" rule was deliberate, and that the "later stage" it refers to is exactly the range-vector loop at `promql/engine.go:2143`.
- It found more baked-in doubled expectations in `promql/engine_test.go` beyond the three I cited: `max_over_time(metricWith3SampleEvery10Seconds[60s:5s])` at `:1177` (36 → 72), `sum_over_time(...[30s:30s])` (1 → 2), `increase(...[5m:1m])[30m:10m]` (10 → 26), `histogram_sum(rate(...[5m:1m]))[30m:10m]` (130 → 338).
- It confirmed the split cleanly: every `func_over_time(metric[range:step])` shape (which routes through `evalSubquery`) has `SamplesRead > TotalSamples`, while subqueries used directly at top level do not.

One correction to that agent's report, which I'm not taking at face value: it concluded the change is "behavior-preserving for `TotalSamples`," reasoning that `git diff` of `engine_test.go` shows zero removed `TotalSamples:` lines. That inference is unsound — absence of changed test expectations only shows no *test* covers the path, which is precisely the situation in finding #1. My differential run of the same query against both commits (16 → 4) refutes it directly. Finding #1 stands as reported.

It also checked two things I had flagged as worth examining and found them sound, which I agree with:
- The `subqStart`/`subqEnd`/`subqInterval` extraction at `promql/engine.go:2385-2411` computes identical values to the prior inline code.
- The ceiling-division outer-step attribution at `promql/engine.go:2422-2437` is intentional and consistent with the `countSamplesAfter` delta model, not an off-by-one.

Two agents (shallow bug scan, comments/docs compliance) are still running. My review as delivered above is unchanged; I'll report anything further if they surface something new.
The docs-compliance agent finished, confirming finding #2 with four more test cases. It also raised that `samplesRead` is not gated by the feature flag — which, if true, materially widens the blast radius of findings #1 and #2. Let me verify that directly.
Confirmed, and this materially raises the severity. With `EnablePerStepStats: false` (a default server, no feature flag):

```
sum_over_time(m[60s:10s])        TotalSamples=6  SamplesRead=12   ← double-count
predict_linear(m[60s] @ 30, 60)  TotalSamples=4  SamplesRead=4    ← was 16 at base
```

**Scope correction to my review above:** I had implied the feature flag limited exposure. That is only true for finding #3. Findings #1 and #2 are **not** gated — `SamplesRead` accumulates unconditionally in `IncrementSamplesReadAtStep` (`util/stats/query_stats.go:347`), only the `*PerStep` arrays are flag-gated, and both counters are added unconditionally at `promql/engine.go:685-686`. So:

- **Finding #1** corrupts `prometheus_engine_query_samples_total` and the `stats=true` API field on **every** Prometheus server, not just flag-enabled ones.
- **Finding #2** ships a brand-new `prometheus_engine_query_samples_read_total` counter that reads ~2× actual I/O for any subquery workload, to **all** users. Since the metric's stated purpose is capacity and cost accounting, a systematically doubled value is worse than no metric.
- **Finding #3** (unbounded allocation) remains flag-gated, as I described.

The docs agent also raised two points I'd weigh differently than it did:

1. It flagged `StepInvariantExpr` (`promql/engine.go:2472`) adding `SamplesRead` once at step 0 while `TotalSamples` accrues per step as a code/docs contradiction. The code there is correct and is the feature working as designed — a step-invariant expression genuinely is read once. What's wrong is only the docs sentence *"for other queries this equals totalQueryableSamples"* (`docs/querying/api.md:246`, `docs/feature_flags.md:47`), which is overbroad. A wording fix, not a defect.

2. It flagged `docs/feature_flags.md:44-48` presenting `samplesRead` under the `promql-per-step-stats` heading when the field is actually unconditional. That one I agree is a real doc/behavior mismatch, and my verification above confirms the underlying behavior. Worth correcting alongside finding #2.

The remaining agent (shallow bug scan) is still running. The working tree is clean and nothing has been posted anywhere.
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

