I'll run the comprehensive review skill as requested.
I'll start with pre-flight: gathering the diff context.
Local mode confirmed (no remote). Let me capture the diff and read the core changes.
Substantive Go change to PromQL query stats. Let me read the key regions in full before dispatching agents.
Confirmed the key structures. Now dispatching the review roster in parallel while I continue verifying.
Six agents running. Now my own verification — checking whether pre-existing `TotalSamples` expectations changed.
No pre-existing expectations were changed. Let me verify the @-modifier path empirically.
Let me run the new tests to confirm the asserted numbers are real behavior.
The test comments themselves admit the issue. Let me confirm the @-modifier reuse path reachability.
`predict_linear` is a range-vector function *and* is at-modifier-unsafe — that makes the reuse path reachable. Let me verify empirically without touching the repo.
Let me verify against both revisions using scratch copies (leaving the repo untouched).
Confirmed: a 4× regression. Now probing the subquery double-count.
Both headline findings empirically confirmed. Let me check the API surface changes while agents run.
Let me quantify the per-step scan cost added to the hot path.
Three findings confirmed empirically (including a measured ~14% slowdown with stats disabled). Waiting on the agent roster.
An agent modified the repo despite the review-only instruction. Backing up then restoring.
Repo restored (agent scaffolding backed up to `/tmp/cr-agent-artifacts/`). Waiting for the remaining agents to report.
Architecture review confirms both headline findings independently. Quick check on one incidental item while the rest finish.
Waiting on the remaining five agents.
Five agents still working. I'll hold for their results rather than pre-empt them.

Interim status — three findings already **empirically confirmed** by differential testing against the base commit (using throwaway `git archive` copies in `/tmp`, leaving the repo under review untouched):

1. **`totalQueryableSamples` regression** for at-modifier-unsafe range-vector functions — `predict_linear(m[60s] @ 30, 60)` over a 4-step range query reports `16 → 4`.
2. **`samplesRead` double-counts subqueries** — `max_over_time(m[60s:10s])` reports `12` where the bare subquery `m[60s:10s]` reports `6` for the identical storage reads.
3. **~14% throughput regression** on `rate(m[1h])` range queries *with per-step stats disabled*.

Note: one subagent wrote debug instrumentation into `promql/engine.go` plus two scratch test files despite the review-only instruction. I restored the tree to pristine (`git status` clean); the artifacts are backed up under `/tmp/cr-agent-artifacts/` if you want to inspect what it was probing.
Let me independently verify the delta logic is actually correct in the common cases (so I don't over-report).
Test analysis independently confirms both. Let me verify the shipped test-file comment block it flagged.
Confirmed verbatim. Waiting on the last four agents.
Four agents still working. Holding for their findings before consolidating.
Still running. I'll wait for the notifications rather than continue polling.
Repo still clean. Waiting for the four remaining agents to report.
I'll stop polling and wait for the completion notifications.
Waiting on `code-reviewer`, `edge-case-hunter`, `blind-hunter`, and `adversarial`. I'll consolidate everything into the final report once they land.
Adversarial review confirms the core findings and adds API-stability angle. Verifying two of its supporting claims.
Both verified: `docs/stability.md:16` lists the v1 HTTP API as stable for 3.x, and `docs/querying/api.md` uses the `*New in vX.Y*` marker 16 times.

Waiting on the final three agents (`code-reviewer`, `edge-case-hunter`, `blind-hunter`) before I consolidate.
Blind review independently reproduced the regression with zero context. Let me verify its duplicate-test-case claim.
Confirmed — three byte-identical cases at `engine_test.go:1541`, `:1590`, `:1639`. Waiting on the final two agents.
I'll wait for the last two rather than keep polling.
Holding for `code-reviewer` and `edge-case-hunter`.
Two agents still running. Continuing to wait.
Waiting.
Edge-case analysis found a **broader trigger** for the same regression and cleared several suspected issues. Only `code-reviewer` remains.
Let me verify that wider trigger myself — it materially expands the finding's blast radius.
Wider trigger confirmed: `quantile_over_time(scalar(bar), m[60s] @ 30)` goes **20 → 8**. The regression is not limited to `predict_linear`.

Waiting briefly for the last agent before finalizing.
Still running. Waiting for the monitor checkpoint.
Waiting on the last agent.
All six agents reported. Stopping the monitor and doing a final integrity check.
Repo clean at `ec7157593`; scratch trees removed. Consolidating.

---

# Comprehensive Review — `samples-read` (`efbdc3f88..ec7157593`)

Local mode (no git remote; nothing posted anywhere). 6 review agents + differential testing against the base commit. All A/B measurements were run in throwaway `git archive` copies under `/tmp`; **the repo under review is unmodified** (`git status` clean).

## Summary

Adds a `SamplesRead` / `SamplesReadPerStep` query statistic (delta-per-step for range vectors) alongside the existing `TotalSamples`, plus counter `prometheus_engine_query_samples_read_total` and new `/api/v1/query{,_range}` `stats.samples` fields.

**Overall risk: High.** The core delta logic for raw matrix selectors is correct and well-tested. But the change (a) silently regresses an existing, stable API field and server counter, (b) makes the new "I/O" statistic *less* accurate than the one it improves on for subqueries, and (c) adds an unconditional O(window) scan to the hottest PromQL loop. Findings 1–3 were each independently reproduced by multiple agents and by my own A/B runs.

---

## Critical

### 1. `totalQueryableSamples` / `prometheus_engine_query_samples_total` silently regress for `@`-modified range vectors
`promql/engine.go:2145` (declaration) → `promql/engine.go:2183` (use)

`fullWindowCount` is declared per-iteration at zero but assigned **only inside** `if ts == ev.startTimestamp || selVS.Timestamp == nil`. The pre-existing call it replaced read the *retained* `floats`/`histograms`, which still hold the reused window:

```go
// before — unconditional, measures the reused slices
ev.samplesStats.IncrementSamplesAtStep(step, int64(len(floats)+totalHPointSize(histograms)))
// after — 0 on every reuse step
ev.samplesStats.IncrementSamplesAtStep(step, fullWindowCount)
```

The path is reachable whenever an `@`-modified matrix selector is *not* hoisted into a `StepInvariantExpr` — `preprocessExprHelper`'s `*parser.MatrixSelector` case returns `shouldWrap=false` (`promql/engine.go:4368`). Two distinct triggers, both measured (range 201→220, step 5s):

| Query | base | head |
|---|---|---|
| `predict_linear(m[60s] @ 30, 60)` | `16` `{4,4,4,4}` | **`4`** `{4,0,0,0}` |
| `quantile_over_time(scalar(bar), m[60s] @ 30)` | `20` `{5,5,5,5}` | **`8`** `{5,1,1,1}` |

`predict_linear` is the only range-vector function in `AtModifierUnsafeFunctions` (`promql/functions.go:2244`); the second form generalizes to any multi-arg range-vector function with a step-varying sibling argument.

This changes a **documented, stable** API field, `totalQueryableSamplesPerStep`, and a long-standing counter — in a PR that adds a statistic rather than changing one. The inline comment at `engine.go:2143` claims "Full window count for TotalSamples (unchanged semantics)", and `util/stats/query_stats.go:270-276` documents the invariant this breaks. No test covers it; no existing expectation changed.

**Fix:** compute the `IncrementSamplesAtStep` argument unconditionally from the live slices; gate only `samplesReadCount` on the branch (its zero-on-reuse behavior is correct).

### 2. `samplesRead` double-counts subqueries — the metric exceeds `totalQueryableSamples`
`promql/engine.go:1874` (`MergeSamplesReadFromSubquery`) + `promql/engine.go:2184` (`IncrementSamplesReadAtStep`)

`evalSubquery` merges the child's `SamplesRead` into the parent; the range-vector loop then walks the **materialized in-memory** subquery matrix and counts the same points again as "read". The deleted comment stated the hazard exactly: *"Avoid double counting samples when running a subquery, those samples will be counted in later stage."* `TotalSamples` still avoids it; only `SamplesRead` does not.

Measured on head (instant query, identical storage reads in each pair):

| Query | `TotalSamples` | `SamplesRead` | actual points read |
|---|---|---|---|
| `m[60s:10s]` (bare subquery) | 6 | 6 | 6 |
| `max_over_time(m[60s:10s])` | 6 | **12** | 6 |
| `max_over_time(m[60s])` (no subquery) | 6 | 6 | 6 |
| `max_over_time(max_over_time(m[60s:5s])[120s:10s])` | 36 | **240** | ~39 |

So a counter whose stated purpose is I/O accounting over-reports by 2× (6.7× when nested) and **exceeds** `TotalSamples` — the full-window-per-step upper bound. `prometheus_engine_query_samples_read_total` will sit above `prometheus_engine_query_samples_total` in production, making the pair unusable as a ratio.

The tests enshrine it: adding `require.LessOrEqual(t, stats.Samples.SamplesRead, stats.Samples.TotalSamples)` to the harness fails **48 of 97** subtests, and one expectation is annotated `SamplesRead: 2, // subquery + outer` (`promql/engine_test.go:1550`).

**Fix:** attribute at exactly one point — drop the merge in `evalSubquery`, or suppress the loop's increment for a synthesized subquery selector. Add the `SamplesRead <= TotalSamples` invariant to the harness.

### 3. Unconditional O(window) rescan added to the innermost range-vector loop
`promql/value.go:195` (`countSamplesAfter`), called from `promql/engine.go:2164`

`countSamplesAfter` linearly scans every point in every window, per series, per step. The previous code used `len(floats)` — O(1). It runs **regardless of whether stats were requested or the feature flag is on**.

| Benchmark | base | head | delta |
|---|---|---|---|
| `rate(m[1h])`, 1000 steps, 20 series, **per-step stats disabled** (my run) | ~14.8 ms/op | ~17.0 ms/op | **+14%** |
| `BenchmarkRangeQuery expr=rate(a_hundred[1d]),steps=1000` | 722–732 ms/op | 982–987 ms/op | **+35%** |
| `BenchmarkRangeQuery expr=rate(a_hundred[1m]),steps=1000` | 8.23–8.41 ms/op | 8.65–8.74 ms/op | +4% |

Ranges do not overlap; cost scales with window size exactly as an O(window × steps) scan predicts. `rate(...[5m])` over many series is Prometheus's most common query shape. `promql/bench_test.go` is untouched and no numbers are reported in the commit.

**Fix:** the delta is derivable in O(1) — `matrixIterSlice` already knows where the previous `mint` fell, and `floats` is time-sorted (a `sort.Search` is O(log n)). At minimum, gate on `StepTrackingEnabled()`.

---

## Medium

### 4. The documented invariant is false, stated in four places
`docs/feature_flags.md:48`, `docs/querying/api.md:246`, `util/stats/query_stats.go:279-281`, `web/api/v1/openapi_schemas.go:593`

*"For other query types, this equals totalQueryableSamples."* Measured counterexamples on head:

| Query | `TotalSamples` | `SamplesRead` |
|---|---|---|
| `max_over_time(m[60s:10s])` | 6 | 12 |
| `m @ 30` (range query, **bare vector selector**) | 4 | 1 |
| `timestamp(m @ 30)` (range query) | 4 | 1 |

The last two are plainly "other query types". The real rule is *attributed once per evaluation, not per step* — step-invariant subtrees land on step 0 (`engine.go:2472`).

Also: `docs/feature_flags.md` documents `samplesRead` and `prometheus_engine_query_samples_read_total` inside the `promql-per-step-stats` section, implying flag-gating. Neither is gated — `samplesRead` has no `omitempty` (`util/stats/query_stats.go:108`) and the counter registers unconditionally (`engine.go:464`). Only the `*PerStep` arrays are gated.

### 5. `samplesReadPerStep` out-of-window attribution is fabricated and undocumented
`promql/engine.go:2434-2443`

Subquery steps before the outer start are folded onto step 0; steps after the last are clamped onto the last step (`if outerStep >= numOuterSteps { outerStep = numOuterSteps - 1 }`). The test comments say so (`engine_test.go:1424`: `216000: 9, // steps after last outer → last step`). The first and last buckets are therefore systematically inflated, so the series is not comparable step-to-step — the exact use case per-step stats exist for. Neither doc mentions it.

### 6. Test expectations fitted to observed output, with an in-file admission
`promql/engine_test.go:1776-1784` — shipping in the diff:

```go
// IMPLEMENTATION NOTES:
// - Some sample count calculations may need refinement based on actual query execution
// - Framework demonstrates key patterns: ...
```

Corroborated at `engine_test.go:1539` (`// ... - corrected values`) and `:1544` (`TotalSamples: 1, // Actual behavior: single step shows 1 effective sample`). This is why `SamplesRead: 72` beside `TotalSamples: 36` passed authoring review.

Plus verbatim duplication: `sum_over_time(metricWith1SampleEvery10Seconds[30s:30s])` @ `Unix(90,0)` appears **three times** identically (`engine_test.go:1541`, `:1590`, `:1639` — Go emits `#01`/`#02` subtest suffixes), and `sum(max_over_time(metricWith3SampleEvery10Seconds[20s:10s]))` twice. ~1135 added test lines with no coverage of the one path this PR regresses.

### 7. The headline deliverable — the counter — has zero test coverage
`promql/engine.go:424-431`, `:464`, `:686`

No test references `querySamplesRead`, `query_samples_read`, or `query_samples_total`. Registration sits inside `if opts.Reg != nil`; a missing `MustRegister` entry produces no error and no metric — the feature would pass every unit test and expose nothing on `/metrics`.

### 8. Two divergent merge implementations; the inline one bypasses the package's nil discipline
`promql/engine.go:2426-2447` vs `util/stats/query_stats.go:423-433`

`MergeSamplesReadFromSubquery` merges index-by-index (correct only because `evalSubquery` happens to build the child with the parent's exact layout — unchecked and undocumented). The `*parser.SubqueryExpr` case does **not** use it: it reaches into `.SamplesRead`, `.SamplesReadPerStep`, `.Interval`, `.StartTimestamp` directly and reimplements the merge with timestamp realignment. Every other `QuerySamples` accessor opens with `if qs == nil { return }` — and this diff *adds* that guard to `InitStepTracking` (`:298`) and `StepTrackingEnabled` (`:312`), so nil is considered reachable — yet the inline block has none.

### 9. Non-`omitempty` field freezes contested semantics into a stable API
`util/stats/query_stats.go:108`

`docs/stability.md:16` lists the v1 HTTP API as stable for 3.x. `samplesRead` appears in every `stats`-bearing response immediately, so the double-counted semantics of finding 2 cannot be corrected within 3.x without a stable-API behavior change. Settle finding 2 before merge, or gate the field until then.

### 10. `IncrementSamplesReadAtStep` silently drops out-of-range writes
`util/stats/query_stats.go:352`

`qs.SamplesRead` is incremented unconditionally, but the per-step write is skipped when `i >= len(...)` — producing `SamplesRead != sum(SamplesReadPerStep)` with no signal. The sibling `IncrementSamplesAtStep` (`:321`) has no bound check and would panic, so the same bug is loud for `TotalSamples` and silent for `SamplesRead`. Asymmetric too: `IncrementSamplesReadAtTimestamp` (`:365`) checks `i >= 0`, this one does not.

### 11. Vacuous API-layer assertions
`web/api/v1/api_test.go:983`, `:999` — `require.GreaterOrEqual(t, qs.Samples.SamplesRead, int64(0))`. `SamplesRead` is an `int64` counter that is never negative, and the query under test yields 0; the assertion passes if the field is hard-wired to 0, i.e. it cannot detect the feature being entirely unplumbed.

### 12. Per-step slices allocated per subquery where none were before
`promql/engine.go:1869`, `:2396` → `util/stats/query_stats.go:298`

`NewChildWithStepTracking` allocates **two** `[]int64` of `numSteps` (including `TotalSamplesPerStep`, which is then discarded unmerged); the old `NewChild()` allocated nothing. For `sum_over_time(x[5m:15s])` over a 30-day range that is ~172k steps ≈ 2.8 MB per subquery node, allocated before any sample is read — so `query.max-samples` cannot bound it and `PeakSamples` does not reflect it. Correctly gated behind the flag, but unbounded once enabled.

### 13. API asymmetry: package-level constructor forces a new exported accessor
`util/stats/query_stats.go:406` vs the sibling method `NewChild` at `:402`

Because `NewChildWithStepTracking` takes `enablePerStepStats` as a parameter rather than reading a receiver, both call sites must write `stats.NewChildWithStepTracking(parent.StepTrackingEnabled(), ...)` — which is the sole reason the exported `StepTrackingEnabled()` (`:311`) exists. Two new exported symbols where one method would do.

---

## Low

- **`docs/querying/api.md:239`** — the new `### Query statistics` section carries no `*New in vX.Y*` marker, breaking a convention used 16 times in that file. Client authors can't tell which version first returns the field.
- **`docs/querying/api.md:239`** — the section is `###` under the range-query `##`, so it doesn't appear in the instant-query TOC even though line 105 links to it.
- **`promql/engine_test.go:51`** — `defaultEpsilon` removed (live copy is `promql/promqltest/test.go:59`). Harmless dead-code cleanup, but unrelated churn in a 1135-line test addition.

---

## Explicitly ruled out (checked, not defects)

- **`countSamplesAfter`'s `maxt-ev.interval` cutoff is correct.** Verified across constant `offset`, `Anchored`/`Smoothed` (both shift `maxt` by a step-independent `lookbackDelta`, preserving the inter-step delta), non-overlapping windows (range < step), heavily overlapping windows, native histograms (`h.size()`), and the strict `>` matching `matrixIterSlice`'s `(mint, maxt]`. Measured: `rate(m[60s])` over 201→220/5s reports `read=7`, exactly the distinct points touched. 100% statement coverage from the new tests.
- **No reachable panic** in the subquery attribution loop — `outerStep` is only assigned under a `tk > ev.startTimestamp` guard with a positive-numerator ceil, and Go's truncating division prevents a negative `make([]int64, n)`.
- **No missed counting site** — every `TotalSamples` mutation (`engine.go:1817`, `1840`, `2183`, `2424`, `2469`, `2577`, `2746`) has a paired `SamplesRead` increment.
- The query log picks up the new field for free (`engine.go:710`); both OpenAPI golden files were regenerated consistently; the counter follows Prometheus naming conventions with no cardinality concern.
- **Best thing in the PR:** `engine_test.go:2434-2441` re-runs every case with per-step stats disabled and asserts both aggregates match — a real invariant covering the nil-slice guards and the `else` fallback for free.

---

## Recommended actions

1. Fix finding 1 — it is an unannounced regression to a stable API field and a server counter, invisible to the test suite.
2. Resolve finding 2 before merge (finding 9 makes it expensive to fix later); add `SamplesRead <= TotalSamples` to the harness — it catches all 48 cases.
3. Benchmark and address finding 3, or gate the scan on stats being enabled.
4. Correct the four copies of the false invariant, and document the per-step clamping.
5. Remove the `IMPLEMENTATION NOTES` block and the duplicate cases; re-derive subquery expectations from first principles.
6. Add a registry test for the new counter.

## Agent roster

| Agent | Model | Tokens | Tools |
|---|---|---:|---:|
| architecture-reviewer | Opus | 81,196 | 20 |
| pr-test-analyzer | Sonnet | 102,596 | 42 |
| adversarial-general | Opus | 103,276 | 32 |
| blind-hunter | Sonnet | 158,976 | 41 ⚠ |
| edge-case-hunter | Sonnet | 127,760 | 59 ⚠ |
| code-reviewer | Sonnet | 132,909 | 35 ⚠ |

`pr-summarizer` and `issue-linker` skipped (local mode, no remote). Findings 1–3 were reproduced independently by 3+ agents *and* by my own A/B runs, which is why I'm stating them as confirmed rather than probable.

**One process note:** a subagent wrote debug instrumentation into `promql/engine.go` plus two scratch test files despite the review-only instruction. I backed the artifacts up to `/tmp/cr-agent-artifacts/` and restored the tree; `git status` is clean and `HEAD` is `ec7157593`. Two other agents independently noticed the contamination and reviewed against `git show` instead of the working tree, so their findings are unaffected.
Stale checkpoint from an earlier wait — both agents it was watching already reported and the review is complete. Cleaning up the leftover monitors.
Both leftover monitors have expired on their own. Nothing remains running.
The review is complete and delivered above. Final state:

- **Repo untouched** — working tree clean, `HEAD` still at `ec7157593`. All differential testing ran in throwaway `git archive` copies under `/tmp`, since removed.
- **Nothing posted anywhere** — local mode throughout; no provider operations attempted.
- **All 6 agents reported**; no failures.

The three findings I'd treat as blocking are #1 (the `totalQueryableSamples` / `prometheus_engine_query_samples_total` regression for `@`-modified range vectors), #2 (the subquery double count that makes `samplesRead` exceed `totalQueryableSamples`), and #3 (the ~14–35% slowdown from the unconditional per-step window rescan, paid even with stats disabled). Each was reproduced by A/B measurement against the base commit rather than inferred from reading the diff.

One caveat worth restating plainly: finding #9 means #2 is time-sensitive. `samplesRead` ships non-`omitempty` into a surface `docs/stability.md:16` declares stable for 3.x, so whatever number lands there is what clients will code against — the double count is much cheaper to settle before merge than after.

