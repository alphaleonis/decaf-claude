✅ Review complete: `.decaf/code-reviews/CODE_REVIEW_2026-08-18_21-34-59.md`

**Mode**: `bugs` (single seat, `solo-reviewer`) · roster=1 · reach=narrow · no validation wave (single-seat path). Spec: none found. Prior reviews: none, so no recurring-findings section.

**Verdict: ❌ NEEDS_CHANGES** — 2 High, 2 Medium, 1 Low.

| # | Sev | Where | What is wrong |
|---|---|---|---|
| 1 | 🟠 High | `promql/engine.go:1874` | Subquery samples counted twice in `SamplesRead`: `evalSubquery` merges the child's `SamplesRead` into the parent, and the range-vector loop at `engine.go:2184` then counts the materialized subquery matrix again. Verified by execution: `max_over_time(m3[60s:5s])` reports `SamplesRead: 72` against `TotalSamples: 36`; removing only the merge line yields 36. The new tests encode the doubled values (`engine_test.go:1184`), so CI cannot catch it. |
| 2 | 🟠 High | `promql/engine.go:2143` | Regression in the *existing* `TotalSamples` metric. `fullWindowCount` is assigned only inside the `@`-reuse guard, so steps that reuse retained points now add 0 where they previously added the full window. Verified against the base revision: `predict_linear(m3[60s] @ 30, time())` over 4 steps drops from 48 to 12; `prometheus_engine_query_samples_total` changes value. The in-diff comment claims "unchanged semantics". |
| 3 | 🟡 Medium | `promql/engine_test.go:1548` | Expectations transcribed from observed output rather than derived — including `SamplesRead: 2, // subquery + outer`, which enshrines finding #1 as the spec. |
| 4 | 🟡 Medium | `docs/feature_flags.md:48` | The added docs assert `samplesRead == totalQueryableSamples` outside range-vector range queries; the `StepInvariantExpr` branch (`engine.go:2472`) deliberately breaks that, as the change's own test at `engine_test.go:1364` (48 vs. 12) shows. |
| 5 | 🟢 Low | `web/api/v1/api_test.go:983` | `require.GreaterOrEqual(SamplesRead, 0)` is tautological — no subtraction path exists, so it cannot fail. |

Findings #1 and #2 were confirmed empirically in throwaway worktrees under `/tmp`; the review checkout was never modified (`git status --porcelain` shows only the untracked `.decaf/` report directory). Eight items were parked under Considered But Not Flagged — three suspected divide-by-zero/index-overflow paths in the new subquery arithmetic were traced and refuted, four are cosmetic, and one is a probe-not-run note (the only entry without a closed-set parking tag).
