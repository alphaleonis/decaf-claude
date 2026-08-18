I'll invoke the requested skill.
I'll start by gathering context on the change under review.
No spec found. Proceeding.

```
Review team (preset `bugs` — single seat · roster=1 · seat on session model · evidence self-calibrated · reach=norm):
- solo-reviewer (the preset's single seat) — session model
- wave agents: not evaluated — bugs is a single-seat path (use `bugs roster=N` for the wave)
```
✅ Review complete: `.decaf/code-reviews/CODE_REVIEW_2026-08-18_22-44-29.md`

**Mode**: `bugs` (single seat, `solo-reviewer` on the session model) · `reach=norm` · no screen, no validation wave (inherent to this path). Step 7 skipped — no prior reviews in this repo.

**Verdict**: ❌ NEEDS_CHANGES — 2 High, 2 Medium, 1 Low, 6 Minor.

The two blocking findings, both settled by execution rather than reasoning:

1. **`promql/engine.go:1874` — subquery samples counted twice in `SamplesRead`.** `evalSubquery` now merges the child's `SamplesRead` into the parent, but the materialized points are then re-counted by the matrix-selector range-eval path at `engine.go:2184` — which is exactly what the removed `NewChild()` comment ("Avoid double counting… counted in later stage") existed to prevent. Measured: `count_over_time(m[1m:10s])` reports `read=12` against 6 real reads, and `sum_over_time(m[10s:10s])` over a range yields `read=41 > total=40`, inverting the relationship the whole change rests on. The direct `*parser.SubqueryExpr` case is *not* affected.

2. **`promql/engine.go:2397` — unbounded eager allocation per subquery step.** The new `NewChildWithStepTracking` allocates two `[]int64` of `(queryRange + subqueryRange) / subqueryStep` before the subquery runs, so `query.max-samples` cannot stop it; the subquery step is caller-controlled down to 1 ms. Measured with `MaxSamples=10`: `count_over_time(m[1h:1ms])` allocates 55 MiB versus 0.1 MiB at the base commit, linear at ~16 B/step. Gated behind `promql-per-step-stats` + `stats=all`, but any query author can trigger it once the flag is on.

The Medium findings are downstream of #1: the ~1100 new test lines encode the double-counted values (their own comments say `// subquery + outer`), so the subquery portion of the table passes *because* of the defect and would fail once fixed; and both docs pages assert two properties — `samplesRead == totalQueryableSamples` for non-range-vector queries, and "samples read (I/O)" — that the implementation does not have.

The seat also verified the parts that are right: the plain matrix-selector delta (`cutoff = maxt - ev.interval`) is correct against `matrixIterSlice`'s `(mint, maxt]` window, the `StepInvariantExpr` step-0 attribution is right, and the `SubqueryExpr` restructuring is behavior-preserving. It found no path where `sum(SamplesReadPerStep) != SamplesRead`. Working tree confirmed byte-identical after its probes.

