✅ Review complete: `.decaf/code-reviews/CODE_REVIEW_2026-08-12_21-00-54.md`

## ❌ NEEDS_CHANGES — 1 Critical, 2 High, 2 Minor

Two of the three primary findings are **regressions**, confirmed by running the same probe against `efbdc3f88` and `ec7157593` side by side.

**#1 🔴 Critical — unbounded allocation from the subquery step grid** · `promql/engine.go:2397` + `util/stats/query_stats.go:306`
The subquery's stats child is now built on the *subquery's* grid, and `InitStepTracking` allocates two `[]int64` of `(subqEnd-subqStart)/subqInterval + 1`. Subquery resolution is user-controlled and uncapped (the 11 000-point API limit bounds only the *outer* grid). Base used `NewChild()`, which disabled per-step tracking entirely — nothing was allocated.
Measured, metric matching **zero** series, `err=<nil>`: base flat at ~13 MB for both spans; HEAD 57.6 MB (`[1h:1ms]`) → 172.8 MB (`3h`) → 345.6 MB (`6h`) — exactly 16 B/step. Extrapolating the same `make`, `[30d:1ms]` ≈ 41 GB, allocated before any read, before `max-samples`, before the timeout. Requires `--enable-feature=promql-per-step-stats` + `stats=all` — the very flag this change extends.

**#2 🟠 High — `@` modifier reuse path reports zero `totalQueryableSamples` after step 0** · `promql/engine.go:2145`
`fullWindowCount` is declared inside the step loop and assigned only inside the `ts == ev.startTimestamp || selVS.Timestamp == nil` branch, so on the reuse path `IncrementSamplesAtStep(step, 0)` fires where the old code passed the retained window length. `predict_linear(m3[60s] @ end(), 3600)` over 4 steps: **72 → 18**. The `prometheus_engine_query_samples_total` counter drops with it. The in-line comment claims "unchanged semantics" and `docs/feature_flags.md` claims every step counts the full window — both false here. CI misses it because the only `@` test uses `max_over_time`, which *is* step-invariant and never reaches this loop; `predict_linear` is in `AtModifierUnsafeFunctions`.

**#3 🟠 High — `samplesRead` double-counted for subquery-as-range-vector-argument** · `promql/engine.go:1874`
`evalSubquery` merges the child's `SamplesRead`, then the caller walks the returned synthetic selector and counts the same in-memory points again — the deleted comment ("Avoid double counting samples when running a subquery") guarded exactly this. `max_over_time(m1[60s:5s])`: `TotalSamples=12`, `SamplesRead=24`; nested: 30. That contradicts both `docs/querying/api.md` ("for other queries this equals `totalQueryableSamples`") and the new field comment in `query_stats.go`. **The new tests pin the doubled value** (`engine_test.go:1175-1200`: `TotalSamples: 36, SamplesRead: 72`), so code, tests, and docs disagree inside one change.

Minor: `IncrementSamplesReadAtStep` omits the `i >= 0` guard its sibling has eight lines below (not reachable today); `NewChildWithStepTracking`'s doc says "outer query step layout" while one of its two callers passes the subquery's.

Notes on the run: all three verdict-driving findings came from `adversarial-reviewer` — the only agent on the session model under this preset's `models=low`; the three cheap-tier agents produced only the two Minor items, and `test-reviewer` explicitly cleared the very test rows that enshrine #3. Probes ran via an untracked scratch test in `promql/` and a nested base-commit worktree (the environment hook blocks `/tmp`); both removed, `git status` verified clean, no tracked file touched. Nothing was posted anywhere and no code was modified.
