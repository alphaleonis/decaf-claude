✅ Review complete: `.decaf/code-reviews/CODE_REVIEW_2026-08-12_21-45-09.md`

## Verdict: ❌ NEEDS_CHANGES

**3 Critical · 3 High · 9 Medium · 7 Low · 6 Minor** — from 10 parallel reviewers (67 raw findings → 22 consolidated), with the top findings confirmed by executable A/B probes I ran after the wave.

### The three Criticals

**#1 — `@`-modifier steps silently stop counting toward `TotalSamples`** (`promql/engine.go:2145`). `fullWindowCount` is declared inside the step loop but assigned only inside the `if ts == ev.startTimestamp || selVS.Timestamp == nil` block, so on window-reuse steps it stays 0. The pre-change code computed it *outside* the block. A/B probe with engine.go swapped:

```
predict_linear(m[60s] @ 30, 60), 4 steps
BASE: TotalSamples=16  perStep=[4 4 4 4]
HEAD: TotalSamples=4   perStep=[4 0 0 0]
```

This silently shrinks the existing `totalQueryableSamples` field and `prometheus_engine_query_samples_total` counter — reachable with no feature flag, and the inline comment claims "unchanged semantics".

**#2 — `SamplesRead` double-counted for range-vector-over-subquery** (`engine.go:1874` + `:2184`). `evalSubquery` now merges the child's reads *and* the outer loop re-counts the materialized subquery points. Removing only the merge line drops `max_over_time(m[60s:5s])` from `SamplesRead=72` to `36` against `TotalSamples=36`, leaving correct cases untouched. ~48 of the new test rows encode the doubled value, so the test suite ratifies the bug rather than catching it.

**#3 — Unbounded per-step allocation on the subquery path** (`util/stats/query_stats.go:306`). Measured exactly 16 B per subquery step, linear, **zero at base** — and with `-query.max-samples=100` every probe query *succeeded* in milliseconds, proving the allocation precedes any limit check. `[40m:1ms]` → 36.6 MiB; extrapolating, `[30d:1ms]` → ~41 GB per request. Gated behind `promql-per-step-stats` + `stats=all`.

### Also worth flagging
The docs, metric `Help`, and field comments all assert `samplesRead == totalQueryableSamples` for non-range-vector queries — false in **both** directions (#4). And `countSamplesAfter` adds an unconditional O(window) scan to the innermost loop where O(new points) suffices, an *asymptotic* regression for `last_over_time`/`count_over_time` (#5).

Two probes I ran also confirmed single-finder claims: subquery `offset` is dropped from the outer-step mapping, skewing per-step attribution (#8), and `SamplesRead` isn't an I/O count on the lookback axis (#13).

No tracked file was modified — all probes ran via `go test -overlay=` with sources in `/tmp`; tree verified byte-identical before and after.
