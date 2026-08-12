All six agents reported. Working tree is clean at `ec7157593`; nothing was modified or posted.

# PR Review Summary — `SamplesRead` query statistic (`efbdc3f88..ec7157593`)

11 files, +1409/−34. Adds a `samplesRead` PromQL statistic intended to count samples actually read from storage, plus `prometheus_engine_query_samples_read_total`.

The core idea works for the simple case — `rate(m[300s])` over 400→500s@10s reports `SamplesRead=40` (exactly the 40 distinct samples in the union of windows) against `TotalSamples=330`. But three defects below are confirmed by execution, and two of them change behavior the PR claims is unchanged.

---

## Critical (2)

### C1. `samplesRead` double-counts every subquery; compounds with nesting
`promql/engine.go:1874` (`MergeSamplesReadFromSubquery`) + `promql/engine.go:2184` (`IncrementSamplesReadAtStep`)

`evalSubquery` merges the child's `SamplesRead` into the parent, and then the outer range-vector loop counts the *same, already-materialized in-memory* points again. `TotalSamples` deliberately avoids this — the comment this diff deleted said so explicitly: `// Avoid double counting samples when running a subquery, those samples will be counted in later stage.`

Measured with storage wrapped in a counting iterator — **identical underlying I/O (21 iterator advances) in all four rows**:

| query (instant @ t=201) | real reads | `samplesRead` | `totalQueryableSamples` |
|---|---|---|---|
| `m[20s:10s]` | 2 | 2 | 2 |
| `max_over_time(m[20s:10s])` | 2 | **4** | 2 |
| `last_over_time(last_over_time(m[10s:10s])[10s:10s])` | 2 | **3** | 1 |
| …三-deep nesting | 2 | **4** | 1 |

My own run: `sum_over_time(m[60s:10s])` instant → `totalQueryableSamples: 6`, `samplesRead: 12`.

This inverts the invariant an operator relies on (read ≤ loaded) and makes `prometheus_engine_query_samples_read_total` a function of query *syntax* rather than work done — fatal for the cost-attribution use case that motivates the feature. Fix by picking one accounting point: either drop the merge at `:1874`, or suppress `:2184` when the series came from a subquery (more truthful — the outer pass is not I/O).

### C2. Undeclared regression of the pre-existing `totalQueryableSamples` for `@`-modified range selectors
`promql/engine.go:2145`, `:2160`, `:2183`

`fullWindowCount` is declared fresh each step and assigned **only** inside `if ts == ev.startTimestamp || selVS.Timestamp == nil`. The pre-change code incremented unconditionally from the *retained* slices. On `@`-reuse steps the count is now 0.

Reachable because `preprocessExprHelper` never wraps a `MatrixSelector` (`engine.go:4364-4367`), so an `AtModifierUnsafeFunctions` range-vector function — `predict_linear` (`promql/functions.go:2248`) — keeps the per-step loop. I verified this by checking out the base files and re-running the identical query:

```
predict_linear(m[60s] @ 30, 3600)   range 201→220 @5s
BASE  totalQueryableSamples=16   perStep=[4,4,4,4]
HEAD  totalQueryableSamples=4    perStep=[4,0,0,0]
```

This hits the stable v1 API field, `totalQueryableSamplesPerStep`, and `prometheus_engine_query_samples_total`. The inline comment at `engine.go:2143` asserts *"unchanged semantics"*, and the docs added in the same diff assert the opposite of the new behavior. No test covers it — the suite is green. Fix: hoist `fullWindowCount` out of the `if`; only `samplesReadCount` should be 0 on reuse.

---

## High (1)

### H1. `countSamplesAfter` adds an unconditional O(window) rescan per step per series — measured +36%
`promql/value.go:192-207`, called at `promql/engine.go:2164`

The old per-step count was O(1) in the float count (`len(floats)`). The new call linearly scans the whole retained window every step, of every series, **with no gate on whether stats were requested**. `BenchmarkRangeQuery/expr=rate(a_one[1d]),steps=1000`, 30x × count=5, identical alloc counts:

- base: 6.78 / 7.44 / 7.25 / 7.03 / 7.16 ms/op
- head: 9.65 / 9.80 / 9.82 / 9.78 / 9.64 ms/op → **~+36%**

A CPU profile attributes 7.4% of the whole profile to `countSamplesAfter`. Mechanism confirmed: `bench_test.go:349-351` loads a 1d window at 10s = 8640 points × 1000 steps ≈ 8.6M added comparisons. The points are sorted — scan backwards and stop at the first `T <= cutoff`, or better, have `matrixIterSlice` return the count it already knows (it appends only `t > mint`), which is both O(1) and more accurate than the `maxt - ev.interval` heuristic.

---

## Medium (6)

- **M1. The documented invariant is false, in five places.** *"For other query types, this equals totalQueryableSamples"* — `docs/feature_flags.md:48`, `docs/querying/api.md:247`, `util/stats/query_stats.go:279-281`. Violated in **both** directions: subqueries give read > total (C1); step-invariant `@` expressions give read < total (`metricWith1SampleEvery10Seconds @ 100` over 4 steps: total=4, read=1, via `engine.go:2471`).
- **M2. Feature-flag gating in the docs is wrong for 3 of 5 fields.** `docs/feature_flags.md:44-51` lists `totalQueryableSamples`, `samplesRead`, `peakSamples` under `--enable-feature=promql-per-step-stats`. All three ship for any non-empty `stats` value regardless of the flag (`query_stats.go:105-111` — `samplesRead` has no `omitempty`; `:156-164` unconditional). Only the two `*PerStep` fields are gated. `prometheus_engine_query_samples_read_total` is also registered unconditionally (`engine.go:464`).
- **M3. Silent bounds-guard drops break `SamplesRead == sum(SamplesReadPerStep)` with no signal.** `query_stats.go:352`, `:365`, `:429` swallow out-of-range indices *after* incrementing the scalar, so the JSON reports a total that disagrees with its own breakdown. The adjacent legacy twins (`:327-329`, `:340-343`) panic on the same condition. Also internally inconsistent: `:352` checks only the upper bound (so a negative index still panics), `:365` checks both. Currently unreachable — a 33-query × 6-range sweep found zero divergences — but this is dead defensive code whose only possible effect is to hide the bug.
- **M4. Subquery per-step attribution clamping produces per-step values that describe nothing real.** `engine.go:2435-2442`. `sum_over_time(m[30s:10s] offset -30s)` over 201→231@30s → `samplesReadPerStep = {201000: 3, 231000: 9}` for uniformly-spaced data. Scalar conservation holds; the distribution does not. `samplesReadPerStep` is documented as "per-step count" with no approximation caveat.
- **M5. `samplesRead` isn't an I/O count for plain vector selectors either.** `engine.go:1818`, `:1841`. With step < scrape interval, `vectorSelectorSingle`'s memoized iterator returns the same stored sample at consecutive steps and it's charged each time — `metricWith3SampleEvery10Seconds` over 201→220@5s reports 12 for 6 real reads. The delta treatment was applied to range-vector windows only.
- **M6. HELP string of a pre-existing metric changed** (`engine.go:422`), and the new parenthetical ("full window per step for range-vector") is exactly the claim C2 breaks.

---

## Test quality (5) — the suite locks in the bugs rather than catching them

Mutation testing (11 mutants, run against a throwaway copy) killed every mutant including "feature reverted", so the tests aren't tautological in the mechanical sense. They are self-confirming in the semantic sense — the numbers were read off the implementation:

- **T1. Goldens encode the C1 double-count as correct.** `promql/engine_test.go:1184` (`TotalSamples: 36` / `SamplesRead: 72`), `:1197` (72/144), `:1548` — `SamplesRead: 2, // subquery + outer`, a comment that names the bug and treats it as spec.
- **T2. Authoring scratch left in the shipped file.** `engine_test.go:1775-1783` is an `IMPLEMENTATION NOTES` block including *"Some sample count calculations may need refinement based on actual query execution"*; `:1539` `// ... - corrected values`; `:1544` `// Actual behavior: ...`; `PHASE 2/3/3/4/5` banners at `:2047, :2066, :2135, :2218, :2327` (PHASE 3 twice); `:1743` `// FOCUSED KEY PATTERNS - Validated Examples`.
- **T3. Vacuous API assertions.** `web/api/v1/api_test.go:983`, `:999`: `require.GreaterOrEqual(t, qs.Samples.SamplesRead, int64(0))` passes for an implementation that never sets the field — verified by hardcoding `SamplesRead: 0` and watching `TestStats` still pass. Also missing the `require.Nil(t, qs.Samples.SamplesReadPerStep)` symmetry at `:982`.
- **T4. Peak-samples max-check regressed by this diff.** `engine_test.go:2437` reassigns `stats` from the new per-step-*disabled* run, so `:2448` (`PeakSamples-1`) now derives its limit from a value never asserted against `c.PeakSamples`. The base version used the asserted run.
- **T5. Duplicates and gaps.** `sum_over_time(metricWith1SampleEvery10Seconds[30s:30s])` @90 appears **3×** (`:1541`, `:1590`, `:1639`), byte-identical; `sum(max_over_time(...[20s:10s]))` @201 twice. Untested: every new `util/stats` export (`NewChildWithStepTracking`, `MergeSamplesReadFromSubquery`, `StepTrackingEnabled`, nil-receiver paths); step > range at the top level; nested subquery inside a range query; irregular/gapped series; windows with floats and histograms simultaneously.

**The single highest-value addition** is two invariant assertions in the existing `TestQueryStatistics` loop: `SamplesRead <= TotalSamples` and `SamplesRead == sum(SamplesReadPerStep)`. Both fail today — which is the point — and they're worth more than the ~900 lines of golden numbers.

---

## Low (5)

- `query_stats.go:402` `NewChild()` (method, always drops per-step) vs `:411` `NewChildWithStepTracking()` (free function, inherits) — same concept, opposite defaults, different shapes. `NewChild` is still live at `engine.go:2458`.
- `engine.go:2426-2444` mutates `ev.samplesStats.SamplesRead` / `SamplesReadPerStep[...]` directly, bypassing the four methods added in this diff to maintain that pairing; creates two competing merge policies (index-aligned `MergeSamplesReadFromSubquery` vs timestamp-aligned inline loop) with nothing on the type saying which applies when.
- `SamplesReadPerStepMap()` (`query_stats.go:183`) returns `nil` where its sibling `TotalSamplesPerStepMap()` (`:174`) returns a non-nil empty map — nil-panic risk for Go consumers. Neither has a production caller.
- `StepTrackingEnabled()` (`:314`) has no doc comment and is a misnomer — it returns `EnablePerStepStats`, not whether tracking was initialized, which is the stronger predicate the rest of the file actually needs (`:184`, `:208`).
- Comment inaccuracies: `engine.go:1861-1864` says only `SamplesRead` is merged but `:1873` also merges peak; `engine.go:2471` says "Subquery ran once" inside `case *parser.StepInvariantExpr` (most step-invariant subtrees aren't subqueries); `engine.go:2439` "disk reads" is unverifiable (head-block data isn't disk). `openapi_schemas.go:599` describes gating accurately while its sibling `:584` now reads as a contradiction.

---

## Strengths

- The delta idea is sound and correct outside subqueries; the `maxt - ev.interval` cutoff lines up with `matrixIterSlice`'s `(mint, maxt]` retention rule across every overlap regime checked, including `selRange < interval`, empty intermediate windows, and the `Anchored`/`Smoothed` shifts (which cancel).
- `countSamplesAfter`'s strict `>` and `h.size()` handling are correct for left-open windows.
- The per-step-enabled vs per-step-disabled cross-check (`engine_test.go:2434-2441`) is the strongest thing here — a ×2 mutant on the `else` branch produced 61 failures.
- Zero-new-point steps are asserted *and* independently derivable (`engine_test.go:1392-1412`) — that's the standard the rest of the goldens should meet.
- OpenAPI schema, golden files, and docs were all updated in step; `TestOpenAPI` and `TestStats` pass.

---

## Recommended action

1. Fix **C1** and **C2** — both are wrong numbers on stable API surface, and C2 is a silent regression to an existing field. Neither has a test.
2. Fix **H1** — a 36% hot-path cost paid by every user, including those who never request stats.
3. Add the two invariant assertions (T-section) and reconcile the goldens against them rather than against the implementation.
4. Correct the docs (**M1**, **M2**) once C1 is settled — right now the shipped default value contradicts its own documentation.
5. Strip the authoring scratch (**T2**) and the duplicate cases (**T5**).
