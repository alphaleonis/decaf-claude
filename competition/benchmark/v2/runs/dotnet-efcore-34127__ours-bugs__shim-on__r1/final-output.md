✅ Review complete: `.decaf/code-reviews/CODE_REVIEW_2026-08-17_14-18-38.md`

**Mode**: `bugs-sp` (explicit) · roster=1 fixed · reach=narrow · no validation wave (single-seat path)
**Verdict**: ❌ NEEDS_CHANGES — 1 Critical, 0 other primary findings, 8 parked

## The finding

**🔴 Critical — `src/EFCore.Relational/Query/SqlNullabilityProcessor.cs:626`**

`NullPropagatedOperands` recurses into `SqlBinaryExpression.Left`/`.Right` for *every* operator type, but `SqlBinaryExpression.IsValidOperator` admits `AndAlso`, `OrElse` and `Coalesce` — and under SQL three-valued logic those don't propagate null (`NULL AND FALSE` is `FALSE`, `NULL OR TRUE` is `TRUE`). An operand reached through an `AND`/`OR` node is therefore wrongly recorded as null-propagating, and `DropNotNullChecks` deletes the `IS NOT NULL` guard that was protecting it.

This is reachable through the common path, not a corner case: `SqlNullabilityProcessor`'s own null-semantics rewrite (`RewriteNullSemantics`) *produces* `AndAlso`/`OrElse` results, so any `x.Nullable != null ? (bool?)(<comparison over another nullable>) : null` hits it. The `ELSE NULL` arm disappears and the expression returns `TRUE`/`FALSE` where it used to return `NULL` — silently wrong projected values and silently wrong rows, on every relational provider.

The reviewer verified this by execution rather than by argument, building `EFCore.Sqlite.Core` at both `afcfba2e9` and the parent commit in throwaway worktrees and running a standalone probe:

- Projection `x.A != null ? (bool?)(x.A == x.B) : null` over a row with `A = null, B = null`: parent returns `null` (matching LINQ-to-objects), this change returns `False`.
- `Where((x.A != null ? (bool?)(x.A != x.B) : null) == true)`: parent returns ids `3,5`; this change returns `1,3,5` — an extra row.

SQL Server is affected identically. None of the five new tests has a boolean-typed WHEN result, which is why the suite doesn't catch it.

Proposed fix is a guard on the recursion excluding `AndAlso`/`OrElse`/`Coalesce`; the reviewer confirmed in a scratch worktree that it restores correct behavior while every optimization the new tests assert still fires.

## Caveats worth your attention

- The repo's own `EFCore.Specification.Tests` **does not compile** here (9 errors under installed SDK 10.0.203 vs. the `global.json`-pinned 9.0.100-preview) — pre-existing and unrelated, but it meant verification ran through an out-of-tree probe rather than the project suite.
- `bugs-sp` is a single-agent path: this result carries one agent's variance, with no validation wave behind it.
- The working tree was verified byte-identical after the review; nothing was modified and nothing was posted.
