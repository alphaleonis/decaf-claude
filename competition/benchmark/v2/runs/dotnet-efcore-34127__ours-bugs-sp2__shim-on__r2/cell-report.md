I'll start by invoking the requested skill.
**Spec discovery**: no `--spec`, no PR link, no repo plan/spec document → `none found`.

```
Review team (preset `bugs-sp` — explicit · roster=1 fixed · seat on session model · evidence self-calibrated · reach=narrow):
- solo-reviewer (the preset's single seat) — session model
- wave agents: not evaluated — bugs-sp replaces the wave
```

Pre-flight gates: skipped (the seat runs its own targeted gates under `bugs-sp`).
✅ Review complete: `.decaf/code-reviews/CODE_REVIEW_2026-08-17_11-54-23.md`

**Verdict: ❌ NEEDS_CHANGES** — 1 Critical, nothing else.

## #1 🔴 Critical — `src/EFCore.Relational/Query/SqlNullabilityProcessor.cs:626`

`NullPropagatedOperands` recurses into both sides of *every* `SqlBinaryExpression` without checking the operator. Arithmetic, bitwise and comparison operators do propagate NULL — but SQL's logical `AND`/`OR` do not (`NULL AND FALSE` = `FALSE`, `NULL OR TRUE` = `TRUE`). So an operand reachable only under an `AndAlso`/`OrElse` gets registered as null-propagating, `DropNotNullChecks` (line 598) deletes its `IS NOT NULL` test, and line 587 returns the bare result — which now yields `TRUE`/`FALSE` on exactly the rows where the original `CASE` returned `NULL`.

This isn't a corner case: EF's own `RewriteNullSemantics` (lines 1882-1897) is what *creates* the `AndAlso`/`OrElse`. Given the test asserts the left operand is non-null, `a == b` becomes `a = b AND b IS NOT NULL` and `a != b` becomes `a <> b OR b IS NULL`. So every `nullableA != null ? (nullableA <op> nullableB) : null` regresses — the most idiomatic use of the shape this optimization targets. In a `Where`, it returns **extra rows**, not just wrong projected values.

**Verified by execution.** The reviewer built `EFCore.Sqlite.Core` from three trees (pre-change `051c33a79`, post-change `afcfba2e9`, and post-change + fix) and probed the 27-row `NullSemanticsData` model against in-memory LINQ. Seven shapes pass pre-change and fail post-change, including `Where((A != null ? (bool?)(A != B) : null) == true)` returning 3 extra rows. The five tests this change adds all use genuinely propagating results (`~A`, `A + B`, string concat), so none of them can catch it.

The proposed fix — excluding `AndAlso`/`OrElse`/`Coalesce` from that recursion — was applied in a throwaway worktree: all seven failures resolve and all five intended optimizations are retained. (`Coalesce` is legal per `IsValidOperator` and also non-propagating; no relational construction site reaches it today, but excluding it is free.)

Working tree confirmed clean afterward: `git status --porcelain` empty, no leftover worktrees, `HEAD` still at `afcfba2e9`.

Six items are recorded under Considered But Not Flagged, including one worth knowing: the repo's own `test/EFCore.Specification.Tests` **does not compile** in this environment (pre-existing SDK 10.0.203 vs `global.json`-pinned 9.0.100-preview.5), so this change was verified against purpose-built probes rather than the project's suites. Full detail plus `--report` session metrics are in the report file.

