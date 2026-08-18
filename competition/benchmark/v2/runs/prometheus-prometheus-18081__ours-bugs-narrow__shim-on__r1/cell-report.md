I'll start by invoking the requested skill.
Review team (preset `bugs` — single seat · roster=1 · seat on session model · evidence self-calibrated · reach=narrow):
- solo-reviewer (the preset's single seat) — session model
- wave agents: not evaluated — `bugs` is a single-seat path (use `bugs roster=N` for the wave)

Spec: none found. Pre-flight: skipped (single-seat path — the seat runs its own targeted gates).
✅ Review complete: `.decaf/code-reviews/CODE_REVIEW_2026-08-18_21-52-10.md`

**Verdict: ❌ NEEDS_CHANGES** — preset `bugs` (single seat, `reach=narrow`), 11 files, +1409/-34.

Two High, two Medium. The two High findings were both verified by execution against the `TestQueryStatistics` fixture:

**#1 — `promql/engine.go:1874`: `SamplesRead` double-counts subqueries under range-vector functions.** `evalSubquery` now merges the child's `SamplesRead` into the parent, but the enclosing `*parser.Call` loop *also* counts the materialized subquery matrix at `engine.go:2184`. `TotalSamples` only gets the second contribution (the child's total is deliberately discarded), so the two axes diverge. Measured: `max_over_time(m3[60s:5s])` → `TotalSamples=36`, `SamplesRead=72` — exactly 2×, against a true read count of 36. `samplesRead` can therefore exceed `totalQueryableSamples`, inverting the change's own framing (loaded ≥ read). Hits `rate(sum(x)[5m:1m])`-shaped queries, which are everywhere.

**#2 — `promql/engine.go:2160`: existing `TotalSamples` semantics silently change.** `fullWindowCount` is declared per-step but only assigned inside the `if ts == ev.startTimestamp || selVS.Timestamp == nil` block, so with an `@` modifier it stays 0 from step 1 on, where the old code passed the retained window unconditionally. Measured against the base commit: `predict_linear(m3[60s] @ 30, scalar(m1))` went from `perStep=[13 13 13 13]` to `[13 1 1 1]`. This moves `totalQueryableSamples` and `prometheus_engine_query_samples_total` — externally consumed for per-query cost accounting — and contradicts the doc comment left in place at `util/stats/query_stats.go:271`. Uncovered by tests; the nearest case is fully step-invariant and takes the other arm.

Medium: the new docs assert `samplesRead == totalQueryableSamples` outside range-vector range queries, false in both directions (`engine.go:2470` vs `:2472` for step-invariant subtrees, plus #1); and the new test table asserts the inflated values from #1, so it ratifies the defect — a `require.LessOrEqual(SamplesRead, TotalSamples)` invariant would fail on at least six cases today.

Ten items parked under Considered But Not Flagged (three unverified panic/consistency paths that could not be reached, one pre-existing nil deref, five minor, one process note without a closed-set reason). Nothing was posted anywhere and no code was modified; the working tree is clean.

