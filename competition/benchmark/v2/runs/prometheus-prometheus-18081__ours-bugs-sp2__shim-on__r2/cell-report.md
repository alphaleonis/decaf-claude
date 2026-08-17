I'll run the code review skill as requested.
I'll start by gathering context on the change under review.
Diff gathered. Now spec discovery and team announcement.
**Spec**: none found (no `--spec`, no linked work item, no repo plan doc matching this change).

```
Review team (preset `bugs-sp` — explicit · roster=1 fixed · seat on session model · evidence self-calibrated · reach=narrow):
- solo-reviewer (the preset's single seat) — session model
- wave agents: not evaluated — bugs-sp replaces the wave
```

Step 3.0 pre-flight skipped (the seat runs its own targeted gates). Dispatching the single seat.
The seat has returned. Now the format pass and report generation.
✅ Review complete: `.decaf/code-reviews/CODE_REVIEW_2026-08-17_11-24-03.md`

**Verdict: ❌ NEEDS_CHANGES** — 3 High, 1 Low. Mode `bugs-sp` (single seat, `reach=narrow`, no wave, no validation). Step 7 (review history) skipped — no prior reviews in this repo.

**Findings**

1. **🟠 `promql/engine.go:1874` — `SamplesRead` double-counts every subquery.** `evalSubquery` merges the child's `SamplesRead` into the parent, while the outer range-vector loop *also* counts the materialized subquery matrix at every step. The removed comment on that very line (`// Avoid double counting samples when running a subquery…`) described the guard that was deleted. Measured 2× on `max_over_time(m3[60s:5s])` (Total=36, Read=72) and 4× when nested. This makes "samples read" exceed "samples loaded" and falsifies the equality claim shipped in this same diff at `docs/feature_flags.md:48`, `docs/querying/api.md:247`, and `util/stats/query_stats.go:281`. The new tests pin the doubled values rather than catching it. Confirmed by mutation probe.

2. **🟠 `promql/engine.go:2164` — ~35% latency regression on long-window range queries.** `countSamplesAfter` linearly rescans the whole window at every step of every series, ungated by the `promql-per-step-stats` flag (it feeds the always-registered counter), so every query pays. `BenchmarkRangeQuery/rate(a_one[1d]),steps=1000`: 7.5–8.0 M ns/op at base → 10.1–10.7 M at head; replacing the call with `0` restores base timing. The slices are sorted, so `sort.Search` would make this O(log n).

3. **🟠 `promql/engine.go:2145` — `TotalSamples` silently drops ~4× for `@`-modified range selectors under non-step-invariant calls.** `fullWindowCount` is assigned inside the window-reuse guard, so it stays `0` for `step > 0` when `@` causes reuse. `predict_linear(m3[60s] @ 30, 3600)` reports Total=48 at base vs 12 at head. `predict_linear` is in `AtModifierUnsafeFunctions`, so it never gets `StepInvariantExpr` wrapping and always takes this path. Contradicts the in-diff comment "unchanged semantics" and the new HELP text. No test covers it, which is why the suite stays green.

4. **🟢 `web/api/v1/api_test.go:983` — tautological assertions.** `require.GreaterOrEqual(SamplesRead, int64(0))` on a monotonically-incremented counter passes even if the engine never populates the field.

Findings 1–3 were verified by execution (benchmarks, mutation probes in throwaway worktrees at base and head), not by reasoning alone. All eight dismissed items — including two the seat traced to unreachable — are recorded under Considered But Not Flagged.

Two process notes: the seat created and deleted two untracked `zz_probe*_test.go` files in the reviewed checkout during verification; I confirmed independently that `git status --porcelain` is empty, so no tracked source was touched and nothing was left behind. And a `bugs-sp` result carries a single agent's variance by construction — there is no corroboration signal in this report.

