I'll run the code review skill as requested.
I'll start by gathering context on the change under review.
**Review team** (preset `bugs-sp` — explicit · roster=1 fixed · seat on session model · evidence self-calibrated · reach=narrow):
- `solo-reviewer` (the preset's single seat) — session model
- wave agents: not evaluated — bugs-sp replaces the wave

**Spec**: none found. **Pre-flight**: skipped (bugs-sp — the seat runs its own targeted gates).
Working tree is clean apart from the untracked `.decaf/` report directory — the change under review is intact, and no code was modified.

✅ Review complete: `.decaf/code-reviews/CODE_REVIEW_2026-08-17_08-43-40.md`

**Verdict: ❌ NEEDS_CHANGES** — 3 High, 1 Medium, 2 Low, 3 Minor. Step 7 (review history) found no prior reviews, so no Recurring Findings section was added.

The three blocking findings, all verified by execution:

**#1 — `promql/engine.go:2145`: the change regresses the *existing* `TotalSamples` accounting.** `fullWindowCount` is assigned only inside the `if ts == ev.startTimestamp || selVS.Timestamp == nil` guard, so on `@`-modifier reuse steps it stays 0 and `IncrementSamplesAtStep` adds nothing — where the pre-change line counted the retained full window unconditionally. Measured at base vs. head with `predict_linear(metricWith1SampleEvery10Seconds[60s] @ 30, 3600)` over a 4-step range: `TotalSamples` 16 → 4, per-step `[4,4,4,4]` → `[4,0,0,0]`. That moves `prometheus_engine_query_samples_total` and `totalQueryableSamples`, which the change's own comment and doc-comment claim are unchanged.

**#2 — `promql/engine.go:1874`: `SamplesRead` double counts `f(subquery)`.** `evalSubquery` now merges the child's `SamplesRead` into the parent, but the subquery's output is then re-counted by the `matrixIterSlice` step loop at line 2184. Measured: `max_over_time(metricWith3SampleEvery10Seconds[60s:5s])` gives `TotalSamples=36, SamplesRead=72` — exactly 2×, while a bare subquery is not doubled. This falsifies the "equals totalQueryableSamples for other query types" claim written in both docs files and the struct comment, and inflates the new counter. The new tests encode the doubling as expected rather than catching it.

**#3 — `promql/value.go:195`: ~38% throughput regression on wide-window range queries.** `countSamplesAfter` linearly scans the whole retained window per step per series, replacing an O(1) `len(floats)`, and runs unconditionally because the engine counters are always accumulated. `BenchmarkRangeQuery` `rate(a_one[1d]),steps=1000`: ~7.17 ms/op at base → ~9.8–11.0 ms/op at head, 3 runs each. The buffer is sorted ascending, so a backward scan or binary search would make it O(new points).

Two caveats on this result: `bugs-sp` is the single-seat experimental path, so these findings carry one agent's variance with no corroboration or validation wave; and the seat's severities and confidence anchors are final by design — I applied only a format pass, no re-tiering.

