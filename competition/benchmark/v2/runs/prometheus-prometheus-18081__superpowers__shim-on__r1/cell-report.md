I'll start by loading the requested skill.
Reviewer subagent's report, verbatim:

---

### Strengths

- **The core idea is sound and the delta computation is correct for plain range selectors.** `matrixIterSlice` retains points with `T > mint` and appends only points newer than the last retained one, so counting points with `T > maxt - ev.interval` (`promql/engine.go:2164`) is genuinely equivalent to "points newly pulled from the iterator this step." That's the right insight, and it's the part of the feature that delivers real value: for `rate(x[1h])` on a 1h-step-1m range query, `samplesRead` reports the actual chunk traversal rather than a 60× inflated window count.
- **The `@`-modifier reuse case is handled deliberately** — `fullWindowCount`/`samplesReadCount` are only set inside the `if ts == ev.startTimestamp || selVS.Timestamp == nil` block, so reused buffers aren't recounted as reads. Same for `StepInvariantExpr` (`promql/engine.go:2472`), where the single evaluation is attributed once at step 0 instead of replicated per step. Both are the semantically right calls.
- **The ceil-based attribution of subquery steps to outer steps** (`promql/engine.go:2432-2441`) is well-reasoned: a subquery point at `tk` first enters an outer range-vector window at the smallest outer step `>= tk`, so `ceil((tk - start)/interval)` is the correct bucket, and the clamping of out-of-window steps to step 0 / last step preserves the invariant `sum(SamplesReadPerStep) == SamplesRead`. I spot-checked several test expectations and that invariant holds.
- **The test harness change is a genuinely good idea**: `runQuery` was parameterized so every case is now also run with per-step stats *disabled* and `SamplesRead`/`TotalSamples` asserted equal (`promql/engine_test.go:2434-2441`). That is exactly the right cross-check for a stat that has two accumulation paths, and it catches a whole class of drift.
- Nil-receiver guards were added consistently (`InitStepTracking`, `StepTrackingEnabled`, `MergeSamplesReadFromSubquery`), API surface is additive (new JSON fields, new counter), OpenAPI golden files were regenerated, and `docs/querying/api.md` gained a real `### Query statistics` section that was missing before. All of `./promql/...`, `./util/stats/...`, and `./web/api/v1/...` pass.

### Issues

#### Critical (Must Fix)

**1. `totalQueryableSamples` silently regresses for `@`-modifier range selectors — an existing user-visible stat and the existing `prometheus_engine_query_samples_total` counter both change.**

`promql/engine.go:2145-2183`. Before this change, the increment was outside the `if ts == ev.startTimestamp || selVS.Timestamp == nil` block:

```go
ev.samplesStats.IncrementSamplesAtStep(step, int64(len(floats)+totalHPointSize(histograms)))
```

so every step added the (reused) window count. Now `fullWindowCount` is a variable that is only assigned *inside* that block, so steps that reuse the buffer add `0`. The inline comment claims the opposite:

```go
// Full window count for TotalSamples (unchanged semantics); delta for SamplesRead.
```

The semantics are not unchanged. This is reachable through any `AtModifierUnsafe` function taking a range vector — in practice `predict_linear` — because those calls are not wrapped in `StepInvariantExpr` and therefore evaluate over all steps with `selVS.Timestamp != nil`. I verified it by running the same query on `3d6fea15a~1` and `ec7157593`:

```
predict_linear(metricWith1SampleEvery10Seconds[60s] @ 100, 60)
  range 201s..220s step 5s

before: TotalSamples=24  perStep=map[201000:6 206000:6 211000:6 216000:6]
after:  TotalSamples=6   perStep=map[201000:6 206000:0 211000:0 216000:0]
```

`TotalSamples` also feeds `ng.metrics.querySamples.Add(...)` at `promql/engine.go:685`, so `prometheus_engine_query_samples_total` changes too — a metric operators alert and capacity-plan on. Whether or not the new value is arguably "better," this is an undeclared behavior change to an existing statistic, made in a commit that advertises only an addition, with no test covering it and a comment asserting it didn't happen. Fix: keep `TotalSamples` on the old code path (`IncrementSamplesAtStep(step, int64(len(floats)+totalHPointSize(histograms)))` unconditionally) and only gate `samplesReadCount`. If the change *is* intended, it needs its own commit, a test, and a CHANGELOG note.

**2. `samplesRead` double-counts every function-over-subquery, making the new metric wrong for the exact query shape it should help with.**

`promql/engine.go:1874` (`MergeSamplesReadFromSubquery`) merges the subquery's `SamplesRead` into the parent, and then the range-vector loop at `promql/engine.go:2184` counts the *materialized subquery result matrix* again as "read". The result matrix is in-memory, not I/O. Measured on `3d6fea15a`:

```
sum_over_time(m[30s:30s])   totalQueryableSamples=1   samplesRead=2
max_over_time(m[60s])       totalQueryableSamples=6   samplesRead=6
max_over_time(m[60s:5s])    totalQueryableSamples=12  samplesRead=24
```

`sum_over_time(m[30s:30s])` performs exactly one selector evaluation reading exactly one sample, and reports `samplesRead=2`. Every subquery is reported at exactly 2× (or more when nested).

This directly contradicts the documentation added in the same commit — `docs/feature_flags.md:48` and `docs/querying/api.md:247` both say "Total number of samples *read* (I/O) … for other queries this equals `totalQueryableSamples`" — and the metric help text at `promql/engine.go:428` ("The total number of samples read by all queries"). A counter named `query_samples_read_total` that exceeds `query_samples_total` will be read as a bug by every operator who sees it.

The existing `TotalSamples` path already solved this: `evalSubquery`'s original comment was *"Avoid double counting samples when running a subquery, those samples will be counted in later stage."* The fix is to apply the same rule to `SamplesRead` — either drop the `MergeSamplesReadFromSubquery` call at `promql/engine.go:1874` and let the outer loop account for it, or keep the merge and suppress the outer loop's increment when the matrix arg came from a subquery. The test expectations bake the double count in (`// subquery + outer` at `promql/engine_test.go:1548`), so they would need to be re-derived, not just re-run.

#### Important (Should Fix)

**3. `countSamplesAfter` adds an O(window) scan per step per series to the range-vector hot path, for information `matrixIterSlice` already has for free.**

`promql/value.go:195`, called at `promql/engine.go:2164`. `ev.samplesStats` is never nil, so this scan runs on every range query regardless of whether the client asked for stats. Isolated benchmark, `3d6fea15a` vs its parent `5d3f9ee39` (`-benchtime 300x -count 3`):

```
parent:  842508 / 874758 / 853411 ns/op
commit:  934645 / 930264 / 893237 ns/op     ≈ +7%
```

on `BenchmarkRangeQuery/expr=rate(a_one[1m]),steps=10000`, where the window holds only ~6 points. The cost is `O(window × steps × series)` and scales with window size, so a `rate(x[1h])` at a 15s scrape interval (≈240 points per window, ~1 new) pays ~240 comparisons per step to learn a number `matrixIterSlice` computes as a side effect. `matrixIterSlice` (`promql/engine.go:~2900`) already knows `drop` and the retained length; returning the count of newly appended points (and their histogram size) makes this O(1).

**4. `promql/engine.go:2423-2446` reaches into `stats.QuerySamples` internals instead of going through the package's API, and duplicates a merge that already exists as a method.**

The block mutates `ev.samplesStats.SamplesRead` and indexes `ev.samplesStats.SamplesReadPerStep[outerStep]` directly, while every other mutation in the engine goes through `Increment*`/`Update*`/`Merge*`. It also reads `ev.samplesStats.Interval` for the bucket math but `ev.startTimestamp` for the origin — two sources for what must be the same step layout. They happen to agree today only because `NewChildWithStepTracking` is always constructed from `ev.startTimestamp/interval`; nothing enforces it, and a future evaluator that sets one without the other silently misattributes. Move this into `util/stats` as e.g. `MergeSamplesReadFromSubqueryAtSteps(child *QuerySamples, outerStart, outerInterval int64)` so the layout comes from one place and `SamplesReadPerStep` can stay unexported-by-convention.

**5. Delta accounting undercounts after a gap in the series.**

`promql/engine.go:2164` uses `maxt - ev.interval` as the cutoff, which assumes the previous step's window overlapped and was populated. When the previous step's window was empty, `matrixIterSlice` takes the `else` branch and re-reads the whole window from the iterator, but `countSamplesAfter` still only counts points newer than `maxt - ev.interval`, so points in `[mint, maxt-interval]` are read and not counted. Sparse or intermittently-scraped series with `selRange > interval` will under-report. The `matrixIterSlice`-returns-the-count fix in issue 3 also fixes this, since it counts what was actually appended.

**6. Test expectations were derived from the implementation's output, not from the expected semantics.**

`promql/engine_test.go:1508-2405`. The ~1100 added lines are captured golden values, and the file says so:

```
// IMPLEMENTATION NOTES:
// - Some sample count calculations may need refinement based on actual query execution
```

with individual cases annotated `// corrected values`, `// Actual behavior: single step shows 1 effective sample`, and `// subquery + outer`. Tests written this way cannot fail on a semantic bug — they encode it, which is precisely what happened with issue 2 (the `SamplesRead: 72` vs `TotalSamples: 36` case at `promql/engine_test.go:1184` locks in the double count). These need re-deriving from first principles once issue 2 is fixed. The scaffold comment block, the `PHASE 2` / `PHASE 3` / `PHASE 4` / `PHASE 5` section banners, and the `ENHANCED SUBQUERY TESTING - Focused on key patterns` header should be removed before merge.

Related: five of the cases are exact duplicates of each other — `sum_over_time(metricWith1SampleEvery10Seconds[30s:30s])` at `Start: time.Unix(90, 0)` appears at lines 1541, 1590, and 1639; `sum(max_over_time(metricWith3SampleEvery10Seconds[20s:10s]))` at `Start: time.Unix(201, 0)` at lines 1556 and 1624.

**7. No test covers the new counter, and the API test assertion is vacuous.**

`prometheus_engine_query_samples_read_total` (`promql/engine.go:424-429`, `685`) has no test asserting it is registered or that it accumulates — same gap as the pre-existing `query_samples_total`, but this is the commit introducing it. And `web/api/v1/api_test.go:983` asserts `require.GreaterOrEqual(t, qs.Samples.SamplesRead, int64(0))`, which is true for any `int64` count including a never-populated zero; it would pass if the field were never wired up at all. Assert the concrete expected value for the fixture query.

**8. Per-step mode now allocates two `[]int64` per subquery where it previously allocated none.**

`promql/engine.go:1869` and `2397`. `NewChild()` returned `NewQuerySamples(false)`, so subquery children never allocated step arrays; `NewChildWithStepTracking` allocates `TotalSamplesPerStep` *and* `SamplesReadPerStep` sized to the subquery's own step count. For a 6h range query with `[1h:1s]`, that's ~25200 steps × 8 bytes × 2 ≈ 400 KB per subquery, outside the `query.max-samples` accounting. Only reachable with `promql-per-step-stats` enabled, so it's bounded exposure — but `TotalSamplesPerStep` is allocated purely as a side effect and is discarded unread (`evalSubquery` deliberately does not merge totals). Allocate only `SamplesReadPerStep` when the caller is a subquery child.

#### Minor (Nice to Have)

**9.** `util/stats/query_stats.go:347` — `IncrementSamplesReadAtStep` bounds-checks `i < len(qs.SamplesReadPerStep)` while its sibling `IncrementSamplesAtStep` (line 320) does not. If an index ever goes out of range, `IncrementSamplesAtStep` panics and `IncrementSamplesReadAtStep` silently increments the scalar without the per-step array, breaking the `sum(perStep) == total` invariant. Pick one convention; if the guard is wanted, make it symmetric and make the drop loud.

**10.** `docs/feature_flags.md:44-52` documents `samplesRead` (the scalar) and both server counters under the `promql-per-step-stats` heading, but neither is gated by that flag — `samplesRead` is returned whenever `stats` is set, and the counters are always exported. Move the counter paragraph and the scalar-field descriptions out of the feature-flag section; keep only `*PerStep` there.

**11.** `util/stats/query_stats.go:313` — `StepTrackingEnabled()` is a getter over the already-exported `EnablePerStepStats` field; its only added value is the nil-receiver guard. Fine, but worth a one-line comment saying that's the point, otherwise it reads as redundant.

**12.** `promql/engine_test.go:51` — removing the unused `defaultEpsilon` const is unrelated cleanup in a feature commit. Harmless (the live copy is in `promql/promqltest/test.go:59`), but it's scope creep.

**13.** No CHANGELOG entry for a new exported metric and two new API response fields.

**14.** Naming: `query_samples_total` ("loaded") vs `query_samples_read_total` ("read") is not self-describing, and with issue 2 unfixed the "read" counter can exceed the "loaded" one. Consider `query_samples_scanned_total` / `query_samples_fetched_total`, or at minimum expand both help strings to state the relationship explicitly.

### Recommendations

- Split this into two commits: (a) the `TotalSamples` behavior change (issue 1) with its own test and CHANGELOG entry, or a revert of it; (b) the `SamplesRead` addition. Right now a semantic change to an existing metric is hidden inside an "add a metric" commit, which is how it survived to review.
- Fix issue 2 first, then re-derive the test expectations from the semantics rather than re-recording output. Consider adding a counting `storage.Querier` wrapper to the test that tallies actual `Next()`/`Seek()` sample yields, and assert `samplesRead == actual iterator yield` for a handful of representative queries. That turns the whole suite from "asserts what the code does" into "asserts what the code should do," and would have caught the subquery double count automatically.
- Have `matrixIterSlice` return the newly-appended float count and histogram size. That single change fixes issue 3 (perf) and issue 5 (gap undercount) at once and removes `countSamplesAfter` entirely.
- Add one property-based or invariant test asserting `SamplesRead <= TotalSamples` across the existing corpus. That invariant follows from the stated model ("delta ≤ full window") and currently fails for every subquery case.

### Assessment

**Ready to merge?** No.

**Reasoning:** Two confirmed correctness defects — an unintended regression of the existing `totalQueryableSamples` stat and `prometheus_engine_query_samples_total` counter for `@`-modifier range selectors (verified: 24 → 6 on `predict_linear(m[60s] @ 100, 60)`), and a 2× double count of `samplesRead` for every function-over-subquery (verified: `sum_over_time(m[30s:30s])` reads 1 sample, reports 2) that contradicts the documentation and metric help text added in the same commit. The test suite passes only because its expectations were recorded from the implementation rather than derived from the intended semantics, so it cannot detect either defect.

