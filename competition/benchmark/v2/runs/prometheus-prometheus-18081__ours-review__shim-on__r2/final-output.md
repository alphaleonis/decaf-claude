✅ Review complete: `.decaf/code-reviews/CODE_REVIEW_2026-08-12_21-24-24.md`

**Verdict: ❌ NEEDS_CHANGES** — 2 Critical, 2 High, 4 Medium, 3 Low, 9 Minor.

Nine reviewers ran in parallel. Two returned contradictory benchmark measurements and three top claims were about runtime behavior a re-read couldn't settle, so I replaced the screening/validation waves with differential probes — building and running both commits side by side in throwaway worktrees. The review tree was never modified (verified clean before, during, and after; worktrees removed).

**The four verified defects:**

1. 🔴 `promql/engine.go:2397` — the subquery child's per-step arrays are sized by the **subquery's** step count, which is unbounded (unlike a range query's 11 000-point cap) and allocated *before* any sample is read, so `query.max-samples` never engages. Measured on a storage holding 11 samples: `count_over_time(metric[100d:1s])` allocates **132 MiB** (base: 0), `[1d:1ms]` allocates **1341 MiB**, both returning no error. At `[100d:1ms]` the `make` becomes `fatal error: runtime: out of memory` via `runtime.throw` — I confirmed `recover()` does not catch it, so the engine's error handling can't either.

2. 🔴 `promql/engine.go:1874` — `samplesRead` double-counts every subquery: `evalSubquery` merges the child's reads, then the same `Call` loop counts the materialized matrix again. Measured `TotalSamples=12` against `SamplesRead` of 12 / **24** / **58** at nesting depths 0/1/2. Reads now exceed samples loaded, inverting the exact relationship the feature exists to express. The deleted comment at that site warned about this hazard for the sibling field.

3. 🟠 `promql/engine.go:2145` — `fullWindowCount` is only assigned inside the recompute branch, so `@`-pinned reuse steps contribute 0 to the **pre-existing** `totalQueryableSamples`. Measured `predict_linear(metric[60s] @ 200, 60)`: 24 → **6**; the no-`@` control is unchanged at 24, isolating the cause. The comment on that line claims "unchanged semantics".

4. 🟠 `promql/value.go:192` — `countSamplesAfter` rescans the full window per step, unconditionally, even with stats disabled. Repository's own benchmark, 4 runs each: **685 ms → 929 ms (+35.6%)** with identical allocation counts.

Findings #2 and #3 are both **baked into the new test expectations** (`engine_test.go:1176-1188` asserts `TotalSamples: 36` / `SamplesRead: 72`), which is why 1135 lines of new tests pass. The table also carries a banner admitting *"Some sample count calculations may need refinement based on actual query execution"* — that caveat turned out to be describing real defects, not hypothetical ones.

`go-reviewer` returned zero findings; its lane was genuinely quiet, and two other agents independently confirmed the hazards it dismissed as unreachable.
