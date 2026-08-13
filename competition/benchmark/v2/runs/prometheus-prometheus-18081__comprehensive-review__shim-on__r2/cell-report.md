I'll start by invoking the requested skill.
I'll run the review workflow. Starting with pre-flight context gathering.
No git remote — running in local mode as instructed. Building the diff and manifest.
Now launching the review agents in parallel.
Continuing my own verification while agents run.
Confirmed a regression empirically. Now probing the subquery paths.
Confirmed double-counting. Now testing the subquery per-step allocation.
Two subagents created scratch test files in the repo despite the review-only instruction. Moving them out to restore a clean tree.
Strong evidence gathered. Cleaning up my probe artifacts while the remaining agents finish.
That worktree belongs to a still-running agent; I'll clean it up at the end. Waiting on the remaining four agents.
~13% slowdown confirmed on a hot path, with stats disabled. Cleaning up.
Three agents still running. Let me verify the double-count arithmetic precisely while waiting.
All existing tests pass, so the regressions I found are uncovered. Waiting on the last three agents.
Three agents still running. While they finish, verifying the remaining subquery attribution edge case.
Solid evidence base assembled. Waiting for the final three agents to report.
Repo tree is clean. Waiting on the last agent.
The adversarial agent is still working. Everything else is in. Let me do a final consolidation check.
I'll wait for the adversarial agent to finish before consolidating the final report.
Review complete — 8 agents plus my own empirical verification against the base commit. Nothing was posted anywhere; the working tree is clean and unmodified.

## Summary

Adds a `samplesRead` / `samplesReadPerStep` query statistic and a `prometheus_engine_query_samples_read_total` counter, intended to measure samples actually **read** (I/O) as distinct from the existing `totalQueryableSamples`, which charges the full range-vector window at every step. Threads a parallel `SamplesRead` accounting axis through `promql/engine.go` and `util/stats/query_stats.go`, with bespoke merge logic for subqueries and step-invariant expressions.

**Type:** feature · **Effort:** 5/5 — the diff is mostly tests and docs, but the core accounting logic is subtle and, as verified below, incorrect in three separate ways.

| File | Summary |
|---|---|
| `promql/engine.go` | New counter; paired `SamplesRead` increments; rewritten subquery/step-invariant stat merging; delta counting in the range-vector loop |
| `promql/value.go` | New `countSamplesAfter` helper |
| `util/stats/query_stats.go` | `SamplesRead`/`SamplesReadPerStep` fields + 6 new methods |
| `web/api/v1/openapi_schemas.go` + 2 golden YAMLs | Additive schema for the new fields |
| `promql/engine_test.go` (+1135) | ~97 new `SamplesRead` expectations |
| `docs/feature_flags.md`, `docs/querying/api.md` | New semantics documentation |

**Overall risk: Critical.** The full test suite (`./promql`, `./util/stats`, `./web/api/v1`) passes, so none of the findings below are caught by the tests.

---

## Review Findings

### Critical (1)

**1. Unbounded, user-controlled heap allocation from subquery per-step stats — `promql/engine.go:2397`, `util/stats/query_stats.go:306-308`**

`NewChildWithStepTracking(…, subqStart, subqEnd, subqInterval)` reaches `InitStepTracking`, which does `make([]int64, numSteps)` **twice**, sized by the *subquery's* step count over the *outer* query's whole range. The pre-image called `NewChild()` → `NewQuerySamples(false)`, which allocated nothing. The API's 11,000-point guard (`web/api/v1/api.go:631`) bounds only the outer query, and the allocation happens *before* evaluation so `query.max-samples` cannot stop it.

Measured, same query on both commits (`sum_over_time(m[1h:1s])`, 365-day range, 1h step — 8,760 points, well inside the API cap):

| | TotalAlloc delta | Samples actually loaded |
|---|---|---|
| base `efbdc3f88` | **0.2 MiB** | 1200 (peak 1500) |
| this change `ec7157593` | **481.8 MiB** | 1200 (peak 1500) |

Scaling is linear in subquery step count. Gated behind `--enable-feature=promql-per-step-stats` + `stats=all`, which bounds the blast radius but does not remove it. Half the allocation is pure waste: the child's `TotalSamplesPerStep` is written and never read, since `MergeSamplesReadFromSubquery` deliberately doesn't merge it.

---

### High (3)

**2. Undisclosed regression to the *existing* `totalQueryableSamples` and `prometheus_engine_query_samples_total` — `promql/engine.go:2145`, `:2183`**

`var fullWindowCount, samplesReadCount int64` is declared fresh each loop iteration and assigned only inside `if ts == ev.startTimestamp || selVS.Timestamp == nil`. The pre-image incremented **outside** that guard, from the `floats`/`histograms` buffers that persist across steps. So when an `@` modifier causes buffer reuse, steps > 0 now contribute **0** instead of the full window.

Reachable in production: `preprocessExprHelper` never wraps a `MatrixSelector` on its own (`engine.go:4364-4367`), and `AtModifierUnsafeFunctions` (`promql/functions.go:2244`) forces `isStepInvariant=false` — `predict_linear` is the member that takes a range-vector argument.

Measured, `predict_linear(metricWith1SampleEvery10Seconds[60s] @ 30, 60)`, range 200s→220s step 5s:

| | `TotalSamples` | `TotalSamplesPerStep` |
|---|---|---|
| base `efbdc3f88` | **20** | `[4, 4, 4, 4, 4]` |
| this change | **4** | `[4, 0, 0, 0, 0]` |

The inline comment at `engine.go:2143` asserts "*Full window count for TotalSamples (unchanged semantics)*" — that is false. This contradicts the surviving doc comment at `util/stats/query_stats.go:266-276`, the newly written `docs/feature_flags.md:47`, and the counter's own updated help text at `engine.go:419`. No test covers it (`predict_linear` appears nowhere in `engine_test.go`) and there is no CHANGELOG entry. Query results and `max-samples` enforcement are unaffected — `ev.currentSamples` is computed independently.

**3. `samplesRead` double-counts subqueries — the new metric reports ~2× actual I/O — `promql/engine.go:1874` + `:2184`**

`evalSubquery` now merges the child's `SamplesRead` into the parent, and the synthetic `MatrixSelector` it returns is then re-scanned by the range-vector loop, which increments `SamplesRead` again over the same in-memory points. The deleted comment stated exactly why the child was discarded before: *"Avoid double counting samples when running a subquery, those samples will be counted in later stage."*

Measured, instant query `rate(m[60s:10s])` at t=600s over 10s-resolution data:

- Real storage reads: **6** (6 inner subquery steps × 1 sample)
- `totalQueryableSamples`: **6**
- `samplesRead`: **12**

The inflation is baked into the new test table rather than caught by it — **60 of 97** new cases have `SamplesRead != TotalSamples`, and ~30 have `SamplesRead` at 2–3× `TotalSamples`, e.g. `engine_test.go:1180/1184` (36 vs 72), `sum by (a) (rate(...[2m:30s]))[15m:5m]` (36 vs 108), `histogram_sum(rate(...[5m:1m]))[30m:10m]` (130 vs 338). A counter named "samples read (I/O)" can never legitimately exceed samples loaded.

**4. The documented invariant is false in both directions — `docs/feature_flags.md:48`, `docs/querying/api.md:247`**

Both docs promise "*For other query types, this equals totalQueryableSamples*". Counterexamples from this PR's own tests: subquery `max_over_time(...[60s:5s])` → 36 vs **72**; step-invariant `max_over_time(...[60s] @ 30)` → 48 vs **12**. `docs/feature_flags.md:47` also claims "step 0: full window", but `engine_test.go:1428` asserts step 0 = 72 where the full window is 36.

---

### Medium (6)

5. **Hot-path slowdown, paid even when stats are disabled — `promql/value.go:195`, called at `promql/engine.go:2164`.** `countSamplesAfter` linearly rescans the whole window every step to derive a count `matrixIterSlice` already knows (it appends only new points). There is no `StepTrackingEnabled()` guard. Benchmarked `BenchmarkRangeQuery/expr=changes(a_one[1d]),steps=1000`, 6 runs each, no overlap in ranges, identical allocations: base **39.1–41.0 ms**, this change **44.8–45.7 ms** → **~13% regression** on every range query over a range-vector function, for a statistic nobody requested.

6. **Committed scratch note admitting the expectations are unverified — `promql/engine_test.go:1777-1784`.** `// - Some sample count calculations may need refinement based on actual query execution`. Given findings 3 and 4 are encoded as *expected* values in this table, that caveat is load-bearing.

7. **Two divergent implementations of the same merge — `promql/engine.go:2424-2445` vs `util/stats/query_stats.go:423`.** The `SubqueryExpr` case hand-rolls attribution by mutating `ev.samplesStats.SamplesRead`/`SamplesReadPerStep` and reading `ev.samplesStats.Interval` directly, while `MergeSamplesReadFromSubquery` does an index-aligned merge for the same concept at `engine.go:1874`. The index math silently depends on an unenforced invariant that the stats layout matches `ev.interval`/`ev.startTimestamp`.

8. **Counters documented only under an experimental flag — `docs/feature_flags.md:51`, `docs/querying/api.md:251`.** `SamplesRead` accrues regardless of `EnablePerStepStats` (`query_stats.go:347-355`) and the counter is registered next to its sibling (`engine.go:464`), so `prometheus_engine_query_samples_read_total` works without `promql-per-step-stats`. Operators reading only the flag section will conclude it is unavailable.

9. **The counter wiring is untested — `promql/engine.go:686`.** `TestQueryStatistics` reads `qry.Stats()` directly and never touches a registry. Of 1135 added test lines, none assert `querySamplesRead`. Symmetry with `querySamples` no longer proves anything now that the two carry different values.

10. **Tautological API assertions — `web/api/v1/api_test.go:983`, `:999`.** `require.GreaterOrEqual(t, qs.Samples.SamplesRead, int64(0))` cannot fail for a counter built from non-negative increments.

---

### Low (4)

11. **Bounds-check asymmetry — `util/stats/query_stats.go:352` vs `:328`.** `IncrementSamplesReadAtStep` guards `i < len(...)` and silently drops the per-step write while still adding to the total; the pre-existing `IncrementSamplesAtStep` indexes unguarded and panics. Latent divergence of `SamplesRead` from `sum(SamplesReadPerStep)` with no signal. `IncrementSamplesReadAtStep` also omits the `i >= 0` check its `…AtTimestamp` sibling has.
12. **Silent truncation in `MergeSamplesReadFromSubquery` — `util/stats/query_stats.go:428`.** `min(len(parent), len(child))` drops child entries already counted in the total. Currently unreachable (the sole call site builds both from the same triple), but undocumented.
13. **Nil-guard inconsistency — `util/stats/query_stats.go:183`, `:207`.** The same commit adds `if qs == nil` to the mutators but not to the new `SamplesReadPerStepMap` / `samplesReadPerStepPoints` accessors.
14. **Three unreconciled per-step attribution rules — `engine.go:2436`, `:2440`, `:2472`, `:2164`** (ceiling division, clamp-to-last-step, all-to-step-0, window delta) described flatly in the docs as "delta semantics". Not safe to alert on as documented.

---

### Recommended actions

1. Fix the allocation at `engine.go:2397` — cap `numSteps`, or size the child by the outer layout as `evalSubquery` already does.
2. Hoist `fullWindowCount` out of the `if` at `engine.go:2149` so `TotalSamples` is bit-for-bit unchanged; only `samplesReadCount` should be 0 on reuse. Delete the "unchanged semantics" comment.
3. Resolve the subquery double-count before this ships — it defines what users will alert on.
4. Rewrite the docs invariant to the three real cases, and re-derive the test table independently rather than from the implementation's output.
5. Gate or eliminate `countSamplesAfter` to recover the 13%.

---

### Coverage caveats

- **Ran (8):** pr-summarizer, code-reviewer, architecture-reviewer, blind-hunter, edge-case-hunter, adversarial-general, pr-test-analyzer, silent-failure-hunter.
- **Not run (4):** `security-reviewer`, `comment-analyzer`, `type-design-analyzer` — I judged the change to have no trust-boundary surface and let adversarial-general carry the resource-exhaustion angle, but that is a real gap in the roster you should know about. `issue-linker` was correctly skipped (no remote).
- Findings 1, 2, 3, and 5 are **empirically confirmed** by running both commits, not inferred from reading.
- Two subagents created scratch test files in the repo despite the review-only instruction; both cleaned up after themselves, and I verified the tree is clean (`git status` empty, no stray worktrees).

**Token use:** ~798k across agents (Opus 181k, Sonnet 617k) ≈ $13.70, plus orchestrator — run `/cost` for exact figures.

