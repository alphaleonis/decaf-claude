I'll run the code review skill as requested.
I'll start by gathering context on the change under review.
**Review team** (preset `bugs-sp` — explicit · roster=1 fixed · seat on session model · evidence self-calibrated · reach=narrow):
- `solo-reviewer` (the preset's single seat) — session model
- wave agents: not evaluated — bugs-sp replaces the wave

**Spec**: none found. **Pre-flight**: skipped (the seat runs its own targeted gates).
✅ Review complete: `.decaf/code-reviews/CODE_REVIEW_2026-08-17_11-07-26.md`

**Mode**: `bugs-sp` (explicit) · roster=1 fixed · reach=narrow · no wave, no screen, no validation wave. Tracked source untouched (`git status --porcelain` shows only the untracked report directory).

**Verdict**: ❌ NEEDS_CHANGES — 3 High, 2 Low.

The three High findings, all empirically verified by the seat:

1. **`promql/engine.go:2145` — the `@`-modifier reuse path zeroes existing `TotalSamples` accounting.** `fullWindowCount` is declared inside the step loop but only assigned inside the re-evaluation branch, so when the `@` data-reuse path skips re-evaluation the increment at line 2183 adds 0. This regresses the *existing* `totalQueryableSamples` field and `prometheus_engine_query_samples_total` counter, and contradicts the doc line this same change adds. A/B against the base tree with `predict_linear(m[60s] @ 30, 60)` over 4 steps: base `TotalSamples=16`, new `TotalSamples=4`. No test covers the shape.

2. **`promql/engine.go:1874` — `SamplesRead` double-counts subqueries, compounding with nesting.** `evalSubquery` merges the subquery's reads into the parent, and then the range-vector loop counts the synthetic in-memory matrix again at line 2184 — counting derived points as I/O. Measured: `m[1m:20s]` → 3, `max_over_time(m[1m:20s])` → 6, and 76 at three nesting levels for 3 real reads. The added tests encode the doubling as expected (`engine_test.go:1168-1187`, commented `// subquery + outer`), while the added docs state the opposite.

3. **`promql/value.go:195` — `countSamplesAfter` is an O(window) scan per step in the hot loop**, replacing an O(1) `len()`, and runs whether or not stats were requested. Benchmarked `changes(a_one[1d]),steps=1000` at ~+10.5% with non-overlapping ranges across 6 runs; the slices are ascending in `T`, so a backwards scan gives the same answer in O(new points).

The two Low findings cover wasted per-step array allocation in subquery children (`TotalSamplesPerStep` is allocated but by design never merged out) and three exact duplicate cases plus a leftover "IMPLEMENTATION NOTES … may need refinement" block in the new `TestQueryStatistics` table — which is the mechanism by which finding #2 got asserted as correct rather than caught.

