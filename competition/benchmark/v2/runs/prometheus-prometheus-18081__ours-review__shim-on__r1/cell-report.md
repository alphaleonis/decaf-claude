I'll start by invoking the requested skill.
I'll start by gathering context on the changeset.
Pre-flight gates pass. Now dispatching the review wave.

**Review team** — preset `review` (explicit) · `roster` N=6 (derived: 249 executable lines) · `models=norm` · `evidence=norm` · `reach=norm`:

- `quick-reviewer` (always, mid-tier)
- `broad-reviewer` (always, mid-tier)
- `adversarial-reviewer` — 249 executable lines ≥ 50; stats accounting has composition surface (session model)
- `design-reviewer` — new exported `util/stats` API, new JSON response contract, new metric (session model)
- `test-reviewer` — hard gate: 1131 added test lines (mid-tier)
- `go-reviewer` — hard gate: Go files; idiom surface = slice aliasing across steps, nil-receiver methods, shared `samplesStats` pointers (mid-tier)
- `performance-reviewer`: **dropped** — roster N=6 (derived): ranked below the 4 specialists kept. Trade noted: the new per-step `countSamplesAfter` scan sits in the eval hot path; I'll check that myself during consolidation.
- `knowledge-reviewer`, `consistency-reviewer`: **dropped** — roster N=6 (derived): ranked last (lowest measured drop cost)
- `security-reviewer`: skipped — no trust-boundary trigger in the diff (no handler, no parsing of boundary-crossing data, no identity check, no crypto/secrets)
- `spec-compliance-reviewer`: skipped — no spec available (hard gate)
- `data-migration-reviewer`: skipped — no migration artifacts (hard gate)
- `prior-feedback-reviewer`: skipped — local commit-range review, no PR threads (hard gate)
- `dotnet`/`typescript`/`cpp`/`rust`-reviewer: skipped — languages absent (hard gate)
All six reviewers returned, with strong convergence. Let me independently verify the two load-bearing claims empirically.
Head confirmed. Now comparing against the base commit via an isolated worktree.
Both findings confirmed by direct base-vs-head measurement. Cleaning up my probes.
Tree clean at head. Now verifying the secondary claims.
Verified independently. Now running the validation wave on the three borderline Medium findings (the two High findings are waived — I confirmed both by direct base-vs-head measurement).
All three validators confirmed. Verifying exact line numbers for the report.
✅ Review complete: `.decaf/code-reviews/CODE_REVIEW_2026-08-11_22-58-57.md`

No tracked file was modified; the only untracked addition is the review report itself. Nothing was posted anywhere.

## Verdict: ❌ NEEDS_CHANGES — 2 High, 5 Medium, 4 Minor

Six reviewers ran (roster N=6, derived from 249 executable lines), plus three validators. I confirmed both High findings myself by running the same queries against the base and head commits and comparing reported statistics — neither is inference.

**#1 — `TotalSamples` regression on the `@`-modifier reuse path** (`promql/engine.go:2145`)

This is the more serious of the two, because it breaks *pre-existing* behavior. `fullWindowCount` is declared inside the per-step loop but assigned only inside the `if ts == ev.startTimestamp || selVS.Timestamp == nil` recompute gate. On the `@`-reuse path the buffers are deliberately reused, so from step 1 onward the variable is still 0 and `IncrementSamplesAtStep` adds nothing. The old code recomputed `len(floats)+totalHPointSize(histograms)` unconditionally.

| query (range, step 5s) | base | head |
|---|---|---|
| `predict_linear(m3[60s] @ 30, 3600)` | 48 `[12 12 12 12]` | **12** `[12 0 0 0]` |
| `quantile_over_time(scalar(m1), m3[60s] @ 30)` | 52 `[13 13 13 13]` | **16** `[13 1 1 1]` |
| same without `@` (control) | 72 | 72 ✅ |

The comment added at line 2144 says "unchanged semantics". It isn't. `totalQueryableSamples` and `prometheus_engine_query_samples_total` are affected.

**#2 — `SamplesRead` double-counts subquery I/O** (`promql/engine.go:1874`)

`evalSubquery` merges the subquery's real reads into the parent, then the outer loop counts the materialized output points again. Measured: `max_over_time(m[10m:1m])` gives Total=10, Read=**20**; nested gives 10 vs **32**. The comment this change removed said exactly why not to do this: *"Avoid double counting samples when running a subquery."*

It contradicts the docs shipped in the same commit (`docs/feature_flags.md:48`: "For other query types, this equals totalQueryableSamples") and makes `query_samples_read_total` exceed `query_samples_total`, which the help strings present as impossible. It is **not** gated by the feature flag — the scalar feeds the always-on counter.

**48 of the 97 new test cases assert `SamplesRead > TotalSamples`**, so CI cannot catch it. Line 1550 annotates it plainly: `SamplesRead: 2, // subquery + outer`.

Two things worth flagging about the process rather than the code: I skipped the clustering and screening sub-agents and did that inline, and the roster cap dropped `performance-reviewer` on a diff that adds a hot-path scan — I checked `countSamplesAfter` statically but took no throughput measurement. Both are recorded in the report's anomalies section.

