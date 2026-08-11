I'll start by invoking the requested skill.
I'll start by gathering context on the changeset.
Pre-flight gates are green. Dispatching the audit roster.

**Review team** (preset `audit`, explicit — `roster`=all gate-matched, `models`=high, `evidence`=any, `reach`=wide):

- `quick-reviewer` (always), `broad-reviewer` (always)
- `knowledge-reviewer` — substantive change embedding non-obvious accounting decisions
- `consistency-reviewer` — new stats API mirrors an existing `TotalSamples` surface to compare against
- `design-reviewer` — public JSON API contract + exported `util/stats` API + new metric
- `security-reviewer` — audit opens the judgment gate; HTTP API response surface + metric cardinality
- `test-reviewer` — hard gate: 1135 lines of new test code
- `adversarial-reviewer` — ≥50 executable lines; subtle cross-step accounting
- `performance-reviewer` — hot-path per-step loops in the query engine
- `go-reviewer` — hard gate: Go files; audit opens the idiom gate
- `spec-compliance-reviewer`: skipped — no spec found (hard gate)
- `data-migration-reviewer`: skipped — no migration artifacts (hard gate)
- `prior-feedback-reviewer`: skipped — local commit range, no PR threads (hard gate)
- `dotnet`/`typescript`/`cpp`/`rust`-reviewer: skipped — language absent (hard gate)
All 10 reviewers returned. Now running the nominated probes serially — I'm the only actor on the tree.
Probes confirmed the major claims. Now measuring the two remaining High-severity claims I can settle empirically.
Confirmed: the scan costs ~61% extra wall-clock, and the reverse-scan fix recovers it with identical results. One last claim to settle.
Tree verified byte-identical throughout. Writing the report.
✅ Review complete: `.decaf/code-reviews/CODE_REVIEW_2026-08-11_20-22-00.md`

**Verdict: ❌ NEEDS_CHANGES** — 2 Critical, 5 High, 12 Medium, 4 Low, 18 Minor. Ten reviewers ran; 22 of the findings I confirmed by direct execution rather than by static re-read.

## The two must-fixes

**#1 — the change silently breaks an existing public metric.** `fullWindowCount` is declared *inside* the per-step loop (`promql/engine.go:2145`) and only assigned inside the load guard, so when an `@`-pinned matrix selector reuses its window, `:2183` adds **0** for every step after the first. Measured on `predict_linear(m[60s] @ 30, 3600)` over 4 steps: `totalQueryableSamples` is **12** at HEAD vs **48** with the pre-change line restored — a 4× under-report of a long-standing counter, while the new comment on those very lines says "unchanged semantics". The full `./promql` suite passes with the old line restored, so nothing covers this and the fix is drop-in.

**#2 — the metric that is the whole point of the change is 2–14× too high.** `evalSubquery` merges the child's `SamplesRead` back (`:1874`) *and* the outer loop re-counts the same materialized points (`:2184`) — exactly the double-count the deleted comment existed to prevent. Removing only the merge makes instant-query values land precisely on `TotalSamples` (72→36, 2→1, 12→6). `samplesRead` therefore *exceeds* `totalQueryableSamples`, inverting the only reason to have both counters — and **48 of the 97 test cases pin the wrong values**, 38 of them instant queries that the docs added in this same commit say must be equal.

## Notable among the High findings

- `countSamplesAfter` forward-scans the full window per step per series, ungated by the `stats` parameter or the feature flag. Measured on the repo's own `absent_over_time(a_hundred[1d]) steps=1000` benchmark: **635 ms → 392 ms** with a reverse scan, full suite still green. The accounting is ~38% of query time.
- Subquery step-tracking allocates two `[]int64` sized by the *subquery* step count, which nothing validates. `count_over_time(m[1h:1ms])` allocates **55.4 MiB** (0.5 MiB pre-change) and the query is then rejected for too many samples anyway — the limiter never sees it. Linear, so `[1d:1ms]` is ~1.4 GB. Flag-gated.
- The test table ships a comment admitting its own numbers may be wrong ("Some sample count calculations may need refinement based on actual query execution"), plus `PHASE 2/3/4/5` banners and 4 exact-duplicate cases.

Two probes **refuted** nominated hypotheses worth stating: the `step == 0`/delta branch and `countSamplesAfter`'s `>` boundary *are* genuinely pinned (17 and 9 failures when broken). The core arithmetic is correct — it's the surrounding accounting that isn't.

Three deviations I want to flag rather than bury: I performed clustering inline and **waived the validator wave entirely**, because the probes had already answered by execution the question validators re-ask statically — both recorded in the report's anomalies with justification. And two reviewers ran mutating experiments via `go test -overlay` and a `/tmp` `go.work` instead of nominating them; they didn't touch the tree (md5-verified byte-identical at every checkpoint, `git status` clean), but I re-derived their results independently before relying on them.

