I'll run the code review skill as requested.
Reviewing the change: a new `samplesRead` query statistic threaded through the PromQL engine, stats package, API schema, and docs.

**Review team** (preset `bugs-sp` — explicit · roster=1 fixed · seat on session model · evidence self-calibrated · reach=narrow):
- `solo-reviewer` (the preset's single seat) — session model
- wave agents: not evaluated — bugs-sp replaces the wave

**Spec**: none found (local commit-range review, no `--spec`, no linked work item).

Per the `bugs-sp` path, Step 3.0 pre-flight is skipped — the seat runs its own targeted gates.
✅ Review complete: `.decaf/code-reviews/CODE_REVIEW_2026-08-17_13-46-27.md`

**Verdict: ❌ NEEDS_CHANGES** — 2 High, 2 Medium, 1 Low. Preset `bugs-sp` (one whole-surface seat, `reach=narrow`, no validation wave). No prior reviews exist in this repo, so the Recurring Findings step was skipped.

The seat verified findings #1–#4 empirically by building the base commit `efbdc3f88` in a throwaway worktree and diffing stats output; the working tree was confirmed clean afterwards.

**#1 High — `promql/engine.go:2145`**: `fullWindowCount` is declared inside the per-step loop and only assigned when the window is re-sliced. Under an `@` modifier, steps > 0 leave it at 0, so `TotalSamples`, `totalQueryableSamplesPerStep` and the pre-existing `prometheus_engine_query_samples_total` counter silently lose those steps — the old code read the retained slices at the increment site and counted the full window. Measured: `predict_linear(m1[60s] @ 300, 60)` over 7 steps went from `total=42, perStep=[6×7]` to `total=6, perStep=[6,0,0,0,0,0,0]`. The change's own comment claims `TotalSamples` semantics are unchanged.

**#2 High — `promql/engine.go:2164` / `promql/value.go:195`**: `countSamplesAfter` scans the whole retained window per step per series, ungated on whether stats were requested, turning O(1) per-step accounting into O(window). Benchmarked `rate(a_one[1d]),steps=1000` at 7.10 ms → 9.51 ms median (+34%, distributions non-overlapping, allocations unchanged). Fixable by walking the sorted slices backwards.

**#3 Medium — `promql/engine.go:1874`**: subquery reads are merged into the parent *and* re-counted when the outer function walks the synthesized matrix, so `samplesRead` exceeds `totalQueryableSamples` (measured 50 vs 42) — contradicting both new doc paragraphs. The PR's own test expectations bake the doubling in (`// subquery + outer`), so it's deliberate; either the double count or the docs needs to change.

**#4 Medium — `promql/engine.go:2434-2438`**: the subquery→outer step attribution compares a subquery-time timestamp against the outer start without adding `offsetMillis` back, so with a non-zero offset every subquery step lands too early and the clamps absorb the overflow. At `offset 300s`, 64% of reads pile onto step 0. Totals stay right; only `samplesReadPerStep` is wrong. Existing offset+subquery tests are all single-step, so the suite doesn't catch it.

**#5 Low — `promql/engine_test.go:1777`**: shipped `IMPLEMENTATION NOTES` scratch block stating "sample count calculations may need refinement", `PHASE 2/3/4/5` banners, and five duplicate cases. The "actual behavior"/"corrected values" comments suggest expectations were recorded from observed output rather than derived — which is consistent with #1, #3 and #4 going unnoticed.

