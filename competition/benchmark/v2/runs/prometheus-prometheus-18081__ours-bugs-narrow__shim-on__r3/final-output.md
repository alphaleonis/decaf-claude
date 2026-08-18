✅ Review complete: `.decaf/code-reviews/CODE_REVIEW_2026-08-18_23-04-39.md`

**Mode**: `bugs` (single seat, roster=1) · `reach=narrow` · `--report` · no spec found · no validation wave (single-seat path). Working tree verified clean after the run; no code was modified and nothing was posted.

**Verdict: ❌ NEEDS_CHANGES** — 1 Critical, 3 High, 2 Medium, 3 Low.

The blocking findings:

- **#1 Critical — `promql/engine.go:2397`** (allocation at `util/stats/query_stats.go:306-308`): the new `NewChildWithStepTracking` for subqueries eagerly allocates two `[]int64` sized by the *subquery's own* step count, before `-query.max-samples`, the timeout, or cancellation can intervene. `count_over_time(metric[300d:1ms])` produced a `fatal error: runtime: out of memory` at `ec7157593` that `evaluator.recover` cannot catch; the same query at the base commit returns `ErrTooManySamples` with a 0.5 MiB allocation delta. Gated behind `--enable-feature=promql-per-step-stats` + `stats=all`, but reachable from any accepted query in that configuration.
- **#2 High — `promql/engine.go:1874`**: `MergeSamplesReadFromSubquery` reintroduces the double count the deleted comment ("Avoid double counting samples when running a subquery") existed to prevent. Measured ratio is exactly 2.0 for instant subqueries and up to 7× for nested ones, making `samplesRead` larger than `totalQueryableSamples` — the opposite of the documented contract. The new tests assert the doubled values as correct.
- **#3 High — `promql/engine.go:2156-2166`**: `fullWindowCount` stays 0 on `@`-modifier reuse steps, silently changing the pre-existing `totalQueryableSamples` statistic and the `prometheus_engine_query_samples_total` counter (52 → 16 on two measured queries), independent of the feature flag.
- **#4 High — `promql/value.go:195-208`**: `countSamplesAfter` front-scans the whole window per step per series, unconditionally. Benchmarked ~25% slowdown on `rate(m1[1h])` with non-overlapping distributions, confirmed by a mutation probe that restored base performance. Both slices are time-sorted, so a tail scan is O(new points).

Medium/Low cover the documentation-vs-behavior mismatch shipped into both OpenAPI golden schemas, a committed test banner stating its own expectations are unverified, a tautological `GreaterOrEqual(..., 0)` assertion, and duplicated test cases.
