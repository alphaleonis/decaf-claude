I'll start by invoking the requested skill.
**Review team** (preset `bugs` — single seat · roster=1 · seat on session model · evidence self-calibrated · reach=norm):
- `solo-reviewer` (the preset's single seat) — session model
- wave agents: not evaluated — `bugs` is a single-seat path (use `bugs roster=N` for the wave)

Spec discovery: none found. Pre-flight: skipped (single-seat path runs its own targeted gates).
✅ Review complete: `.decaf/code-reviews/CODE_REVIEW_2026-08-18_23-21-47.md`

**Mode**: `bugs` (single seat, `solo-reviewer`) · `reach=norm` · no validation wave (single-seat path).
**Verdict**: ❌ NEEDS_CHANGES — 2 High, 1 Medium, 2 Low, 3 Minor.

Findings, all empirically verified by the seat (targeted tests, benchmarks against a worktree at the base commit, and two byte-identically-restored mutation probes):

1. **High — `samplesRead` double-counts every subquery** (`promql/engine.go:1874`, `:2184`). `evalSubquery` merges the subquery's real read count into the parent, and the outer range-vector loop then counts the materialized subquery matrix again. Measured ~2× inflation: `sum_over_time(m[1m:10s])` reports 12 for 6 actual reads. The change's own tests enshrine it (`engine_test.go:1548`: `SamplesRead: 2, // subquery + outer`), and it contradicts the contract stated in all three doc sites ("for other queries this equals `totalQueryableSamples`").

2. **High — `countSamplesAfter` re-scans the full window every step** (`promql/value.go:195`, called from `engine.go:2164`), an O(window) scan where O(new points) suffices on ascending-sorted slices. It is **not** gated by the per-step-stats feature flag, so every range query pays it: measured +33% on `last_over_time(m[1h])`, +61% on `last_over_time(m[6h])`; a `return 0` mutation restored base timings exactly. Fix is a backwards walk from the tail.

3. **Medium — `totalQueryableSamples` regresses for `predict_linear(x[r] @ t, s)`** (`engine.go:2143-2184`). `fullWindowCount` is now assigned only inside the `@`-reuse guard, so reused steps contribute 0. Measured 66 → 6 on the one function (`AtModifierUnsafeFunctions`) whose matrix selector is not wrapped in `StepInvariantExpr`. This is an existing public API field and engine counter, changed under a comment claiming "unchanged semantics", and untested.

4. **Low** — `web/api/v1/api_test.go:983`/`:999`: `GreaterOrEqual(..., int64(0))` on a non-negative counter passes with the field permanently zeroed (verified by mutation).
5. **Low** — subquery children allocate a `TotalSamplesPerStep` slice that is never read (`query_stats.go:411`); ~322 KB dead per subquery at `[7d:15s]`, flag-gated.

Minor findings cover naming/guard asymmetry in `query_stats.go` and three testing gaps. The seat parked 7 items as considered-but-not-flagged (division-by-zero on `ev.interval`, the subquery clamp arithmetic, the `exec` counter race — all refuted by inspection); 1 of the 7 lacks a closed-set parking tag, recorded in the report header per the path's contract. Nothing was posted anywhere and no code was modified; `git status` shows only the new `.decaf/` artifact directory.

