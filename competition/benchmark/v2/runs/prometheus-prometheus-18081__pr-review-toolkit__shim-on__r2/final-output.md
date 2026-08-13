All six agents have reported. Consolidating.

---

# PR Review Summary

**Range:** `efbdc3f88..ec7157593` (`3d6fea15a add metric to track total samples read per query`)
**Scope:** 11 files, +1409/−34 — adds a `samplesRead` query statistic and `prometheus_engine_query_samples_read_total` counter to the PromQL engine.

Six agents ran in parallel (code, errors, tests, comments, types, simplify). Findings are deduplicated and ordered by severity. Verdicts marked **CONFIRMED** were reproduced by running code; **[Inference]** marks reasoning I could not execute.

---

## Critical (3)

### C1. `SamplesRead` double-counts every subquery — CONFIRMED by 5 agents independently
`promql/engine.go:1874` together with `promql/engine.go:2184`

`evalSubquery` now merges the subquery's read count into the parent. But `evalSubquery` returns a synthetic `*parser.MatrixSelector` whose series are the subquery's *materialized in-memory output* (`promql/engine.go:2008-2017`), and the enclosing range-vector loop then walks those same points and calls `IncrementSamplesReadAtStep` again. Both land in `SamplesRead`.

The diff deleted the comment that explained exactly why this must not happen:
> `// Avoid double counting samples when running a subquery, those samples will be counted in later stage.`

`TotalSamples` is immune because `evalSubquery` still declines to merge it. `SamplesRead` was given the merge without removing the second count.

Measured, and **47 of the 97 new fixtures have `SamplesRead > TotalSamples`** — every one of shape `fn(subquery)`:

| fixture | `TotalSamples` | `SamplesRead` | true reads |
|---|---|---|---|
| `promql/engine_test.go:1177` `max_over_time(m3[60s:5s])` (instant) | 36 | **72** | 36 |
| `promql/engine_test.go:1190` `sum(...) + sum(...)` | 72 | **144** | 72 |
| `promql/engine_test.go:1540` `sum_over_time(m1[30s:30s])` | 1 | **2** | 1 |
| `promql/engine_test.go:2283` `rate(histogram_sum(mH)[2m:30s])` | 4 | **56** | — |

A statistic documented as "samples *read* (I/O)" reporting 2 for a window containing exactly one stored sample is not defensible. This also inflates the new `prometheus_engine_query_samples_read_total` counter for any subquery workload.

**Important nuance on the fix direction.** Simply dropping the merge is wrong. The `rate(histogram_sum(...))` case shows `TotalSamples: 4` against real inner reads of ~52 histogram-sample-equivalents — the merge is capturing genuine I/O that `TotalSamples` misses. The actual defect is that re-scanning an *already-materialized in-memory matrix* is counted as I/O. Suppress the count at `promql/engine.go:2184` when the matrix selector is subquery-derived; keep the merge.

### C2. Pre-existing `totalQueryableSamples` silently regresses — CONFIRMED by A/B execution
`promql/engine.go:2145` (with `:2149`, `:2160`, `:2183`)

`fullWindowCount` is declared *inside* the per-step loop and assigned only inside the `@`-reuse guard. The base code called `IncrementSamplesAtStep(step, int64(len(floats)+totalHPointSize(histograms)))` **unconditionally**, using the slices deliberately retained across steps. So on the reuse path every step after the first now contributes `0`.

I ran this against both commits (`predict_linear` is in `AtModifierUnsafeFunctions`, `promql/functions.go:2248`, so `preprocessExprHelper` does not wrap it — `promql/engine.go:4332`, `:4364-4367`):

| query, `start=201s end=220s step=5s` | base `efbdc3f88` | head `ec7157593` |
|---|---|---|
| `predict_linear(m1[60s] @ 30, 60)` | `16`, `[4,4,4,4]` | **`4`, `[4,0,0,0]`** |

This changes a long-standing public API field and the `prometheus_engine_query_samples_total` counter. The comment two lines above claims **"(unchanged semantics)"**. It is also internally inconsistent: `predict_linear(m1[60s:10s] @ 30, 60)` still reports 16, so the same logical query reports 4 or 16 depending on selector shape.

Two agents rated this unreachable because `@` expressions normally get wrapped in `StepInvariantExpr`; the `predict_linear` A/B run settles it — it is reachable.

### C3. Per-step attribution ignores the subquery offset — CONFIRMED with reproducers
`promql/engine.go:2435-2438`, clamp at `:2440-2442`

`tk` is a subquery-space timestamp, but the outer step that consumes it is at `tk + offsetMillis`. `offsetMillis` is computed at `promql/engine.go:2383` and never used in the mapping. The `outerStep := 0` initializer and the `>= numOuterSteps` clamp then silently absorb everything that falls outside.

| query (11 outer steps, correct = 24/step) | result |
|---|---|
| `sum_over_time(m[1m:10s] offset 10m)` | step 0 = **124**, steps 1-10 = 12 |
| `sum_over_time(m[1m:10s] offset -10m)` | steps 0-9 = 12, last step = **144** |

For a negative offset, **100% of the subquery's I/O is dumped on the final step**. Totals stay correct, so nothing signals the distortion. Negative offsets are enabled unconditionally (`cmd/prometheus/main.go:944`). Since `samplesReadPerStep` exists precisely so operators can find the expensive step, this points them at the wrong one.

---

## High (2)

### H1. Unguarded O(window) scan on the hottest loop — **+36% latency, CONFIRMED by benchmark**
`promql/value.go:195`, called from `promql/engine.go:2164`

`countSamplesAfter` runs inside `for series { for step { … } }` and is **not gated on `EnablePerStepStats`** or on stats being requested at all — `SamplesRead` feeds an always-on counter. For floats this replaces an O(1) `len(floats)` with a full linear pass over the retained window on every step of every series.

I benchmarked `BenchmarkRangeQuery/expr=rate(a_one[1d]),steps=1000` (6 runs each, stats disabled):

| | ns/op | B/op |
|---|---|---|
| base `efbdc3f88` | ~6,850,000 | 879,668 |
| head `ec7157593` | ~9,330,000 | 879,710 |

**~+36% wall time, identical allocations** — pure added CPU, paid by every range query using a range-vector function whether or not anyone asked for stats. Both slices are timestamp-ascending, so a reverse scan or `sort.Search` makes this O(new points) instead of O(window); an isolated micro-benchmark measured ~350× on the inner loop.

### H2. Unbounded pre-evaluation allocation driven by user input — [Inference], code path verified
`promql/engine.go:2397` → `util/stats/query_stats.go:306-308`

`NewChildWithStepTracking` is called **before** the subquery is evaluated (I confirmed the ordering at `promql/engine.go:2397` vs `:2419`), and allocates two `[]int64` of `numSteps = (subqEnd-subqStart)/subqInterval + 1` — sized purely from the user-supplied subquery step, and regardless of whether the selector matches any series.

`max_over_time(does_not_exist[30d:1ms])` implies ~2.6e9 steps ≈ 41 GB allocated up front on a query that previously returned instantly. Before this change subquery children were `NewQuerySamples(false)` and allocated nothing, so this is a new exposure, not an existing one. It requires `--enable-feature=promql-per-step-stats` plus `stats=all`, which bounds the blast radius. Not executed — deliberately, to avoid OOMing the host.

---

## Important (4)

### I1. No test asserts `SamplesRead == sum(SamplesReadPerStep)`, and three paths can break it
`util/stats/query_stats.go:352`, `:365`, `:428`

All three increment the scalar unconditionally but write the per-step array conditionally. Verified by direct probe: `IncrementSamplesReadAtStep(7, 100)` on a 3-step array yields `SamplesRead=105`, `SamplesReadPerStep=[5 0 0]` — 100 counts vanish, no log, no error. `MergeSamplesReadFromSubquery` adds the child's full scalar but clamps the per-step loop to `min(len)`.

All 97 fixtures currently balance, but the invariant is asserted nowhere. One line after `promql/engine_test.go:2431` converts three silent-divergence classes into test failures. This is the single highest-value addition to the change.

### I2. Inconsistent bounds policy across four sibling methods
`util/stats/query_stats.go:321-369`

Three different out-of-range policies for the same index, computed from the same inputs, called on adjacent lines: `IncrementSamplesAtStep` panics; `IncrementSamplesReadAtStep` checks `i < len` but **not** `i >= 0` (so it silently drops high, panics low); `IncrementSamplesReadAtTimestamp` checks both. The new guards are currently dead code — the unguarded sibling panics first — so they buy nothing while establishing that per-step counts may be quietly dropped.

Related contradiction: `InitStepTracking`/`StepTrackingEnabled` gained `if qs == nil` guards, yet `promql/engine.go:2426-2443` dereferences `ev.samplesStats` fields raw. Either nil is possible and that line crashes, or it isn't and the guards are cargo cult.

### I3. Vacuous assertions are the only API-boundary coverage
`web/api/v1/api_test.go:983` and `:999`

```go
require.GreaterOrEqual(t, qs.Samples.SamplesRead, int64(0))
```

A monotonically incremented count is always ≥ 0. This passes if the field is never wired up, always zero, or wildly wrong.

### I4. Docs assert an equality that is false in **both** directions
`docs/feature_flags.md:48`, `docs/querying/api.md:247`, `util/stats/query_stats.go:279-281`, and the `Help` string at `promql/engine.go:428`

> "For other query types, this equals totalQueryableSamples."

| instant query | `TotalSamples` | `SamplesRead` |
|---|---|---|
| `promql/engine_test.go:994` `max_over_time(m1[60s])[20s:5s]` | 24 | **8** (under) |
| `promql/engine_test.go:1177` `max_over_time(m3[60s:5s])` | 36 | **72** (over) |

The real determinant is expression shape, not query type. Anyone computing `samplesRead / totalQueryableSamples` as a reuse ratio gets values > 1. Also: `docs/feature_flags.md:44-51` places `samplesRead`, `peakSamples`, and both counters under the `promql-per-step-stats` heading, but only the two `*PerStep` arrays are flag-gated — the counters are registered unconditionally (`promql/engine.go:424-430`, `:464`).

---

## Suggestions

- **Coverage gaps:** no range query with an offset on a range-vector function (which is exactly C3); no range query with a nested subquery; no series mixing floats and histograms, so the two loops in `countSamplesAfter` are never both non-empty; `countSamplesAfter` has no direct unit test despite a classic `>` / `>=` boundary at `promql/value.go:198`.
- **Recorded-output testing:** `promql/engine_test.go:1539` `// - corrected values` and `:1544` `// Actual behavior:` describe fitting expectations to the implementation. Every fixture explains its `TotalSamples` derivation; **none** explains `SamplesRead` — the one number that is new and non-obvious.
- **Duplicate fixtures:** `promql/engine_test.go:1540`, `:1589`, `:1638` are byte-identical (as are `:1555` and `:1623`), colliding into `#01`/`#02` under `t.Run`.
- **Harness coupling:** `promql/engine_test.go:2437` reassigns `stats` to the per-step-*disabled* run, so the max-samples check at `:2448` now derives its threshold from an unasserted value.
- **Structure:** three independent implementations of "keep total and per-step in sync" (two methods plus the inline loop at `promql/engine.go:2426-2444`), and the inline loop uses *ceiling* mapping while the type's own method uses *floor*. The `SubqueryExpr` restructuring (`promql/engine.go:2382-2419`) is largely churn that hides the substantive change and dropped the comment explaining the step-alignment computation.
- **Doc-comment errors:** `NewChildWithStepTracking` says "outer query step layout" but `promql/engine.go:2397` passes the *subquery's*; `promql/engine.go:2471` says "Subquery ran once" inside `case *parser.StepInvariantExpr`, where the expression is usually not a subquery.
- **Scope creep:** `defaultEpsilon` removal at `promql/engine_test.go:48` is correct (genuinely dead) but unrelated.

---

## Strengths

- The dual-mode harness at `promql/engine_test.go:2434-2441`, re-running every case with per-step stats off and asserting `SamplesRead` matches, is the best thing in the diff — it pins the two structurally different attribution branches against divergence.
- `promql/engine_test.go:1393` is a genuine delta assertion on the raw storage path that three plausible wrong implementations would each fail.
- `countSamplesAfter`'s cutoff (`maxt - ev.interval`) is **correct** — verified for range-shorter-than-step, and for `Anchored`/`Smoothed` where both bounds shift equally.
- No divide-by-zero and no negative-index panic: `ev.interval` is never 0 (`promql/engine.go:805`, `:865`) and `numOuterSteps ≥ 1`.
- Both OpenAPI goldens regenerate cleanly and all updated tests pass.

---

## Recommended action

1. Fix **C1** by suppressing the outer re-count, not by dropping the merge — then regenerate the 47 affected fixtures.
2. Fix **C2** by hoisting `fullWindowCount` out of the `@` guard; drop the "unchanged semantics" comment either way.
3. Fix **C3** by adding `offsetMillis` to the outer-step mapping; keep the clamp only as a true boundary guard.
4. Gate or optimize **H1** — a 36% regression on the default path for an opt-in statistic is the finding most likely to block merge independent of correctness.
5. Add the `SamplesRead == sum(SamplesReadPerStep)` assertion (**I1**) before anything else lands.
6. Re-derive the docs from the fixed behavior; they are currently falsified by the PR's own tests.

**Note on process:** I created one scratch test file and two throwaway worktrees to run the A/B comparisons and benchmarks. All are removed — `git status --porcelain` is empty and `git worktree list` shows only the repo. Two agents observed that file mid-run and flagged it; it was my verification artifact, not part of the change.
