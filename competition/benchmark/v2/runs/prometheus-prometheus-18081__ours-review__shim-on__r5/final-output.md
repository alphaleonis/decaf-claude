✅ Review complete: `.decaf/code-reviews/CODE_REVIEW_2026-08-18_13-36-23.md`

**Verdict: NEEDS_CHANGES** — 5 High, 2 Medium, 9 Low, 6 Minor. Working tree unmodified (only the untracked `.decaf/` report added); all probes ran against out-of-tree `git archive` copies of both commits.

Four findings are confirmed by direct base-versus-head measurement, not inspection:

1. **`SamplesRead` double-counts subquery samples** (`promql/engine.go:1874`) — `evalSubquery` merges the subquery's reads into the parent, then the enclosing range-vector loop counts the materialized result again. Measured `max_over_time(m[60s:5s])`: Total 36, Read 72; nested 6 → 22. 48 of the change's own 97 expected-value cases have `SamplesRead > TotalSamples`, worst 14×. The counter is documented as I/O and is incremented unconditionally, so it ships wrong. The deleted comment — *"Avoid double counting samples when running a subquery"* — was the invariant this breaks.

2. **`TotalSamples` regresses silently** (`promql/engine.go:2145`) — `fullWindowCount` is now assigned only inside the `@`-reuse guard. For `quantile_over_time(scalar(other), foo[60s] @ 30)` over 4 steps: base 52 → head 16. That is pre-existing public surface (`prometheus_engine_query_samples_total`), and the comment two lines above asserts "unchanged semantics". No test covers the shape, so the full suite passes.

3. **Unbounded client-triggerable allocation** (`promql/engine.go:2397`) — per-step arrays sized by the *subquery's* step count, allocated before any sample is read, so `query.max-samples` cannot bound it. `count_over_time(m[1d:1ms])` with `MaxSamples=1`: 1382 MB head vs 0.1 MB base, exactly linear. Gated on the experimental `promql-per-step-stats` flag plus `stats=all` — which is why I set High rather than the reporting agent's Critical.

4. **Unconditional hot-path cost** (`promql/value.go:195`) — `countSamplesAfter` rescans the whole window every step, discarding `matrixIterSlice`'s incremental maintenance. `absent_over_time(a_hundred[1d]), steps=1000`: **+80%**; `changes(...)`: +16%. Not gated on any flag.

Also High: the documented relationship between the two counters is false in **both** directions (subqueries make Read larger; step-invariant expressions make it smaller).

Two candidate findings were **refuted** by validators and moved to Considered But Not Flagged — a claimed ceiling-vs-floor rounding disagreement (vacuous: the floor index is never computed in the branch that would use it) and a claimed `MergeSamplesReadFromSubquery` layout hazard (parent and child are identical by construction at the sole call site). Three severities were corrected downward on validator evidence.

One caveat on the report's own process: I clustered findings in-orchestrator rather than dispatching the clustering agent, and waived validation on findings #1, #2 and #6 because I had already settled them by measurement. Both deviations are recorded in the report.
