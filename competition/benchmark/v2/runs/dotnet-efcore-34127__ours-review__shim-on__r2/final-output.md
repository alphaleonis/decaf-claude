No prior reviews exist, so the Recurring Findings step is skipped. Tracked source is untouched — the only working-tree change is the untracked `.decaf/` report directory.

✅ Review complete: `.decaf/code-reviews/CODE_REVIEW_2026-08-12_14-12-39.md`

## Verdict: ❌ NEEDS_CHANGES

**1 Critical, 1 High, 1 Medium, 3 Low, 5 Minor** — 7 reviewers, 3 validators, all 3 validated findings confirmed, 0 refuted.

### The blocking finding

`src/EFCore.Relational/Query/SqlNullabilityProcessor.cs:626` — `NullPropagatedOperands` recurses into both operands of **every** `SqlBinaryExpression` with no `OperatorType` filter. That's only sound for operators where SQL guarantees NULL if either operand is NULL. `AndAlso`/`OrElse` have absorbing values (`NULL AND FALSE = FALSE`, `NULL OR TRUE = TRUE`), so the `IS NOT NULL` guard gets dropped from a CASE where it was load-bearing, and queries silently return `True`/`False` where they must return `NULL`.

Three things make this conclusive rather than theoretical:

- **The same file already implements this exact inference with the guard.** `ProcessNullNotNull` at `:2313-2320` reads `when sqlBinaryOperand.OperatorType != ExpressionType.AndAlso && ... != ExpressionType.OrElse`, with the comment *"for AndAlso, OrElse we can't do this optimization"*. The new code re-derives the rule and drops the exclusion.
- **Two reviewers independently measured row-level divergence** against SQLite with consistent results. The worst case needs no hand-written boolean logic: `A != null ? (bool?)(A == B) : null` emits `"A" = "B" AND "B" IS NOT NULL` — the `AndAlso` is manufactured by EF's *own* null-semantics expansion — and returns `False` where `null` is correct.
- **The strongest refutation was checked and failed.** The plausible defense is that booleans are wrapped in a nested `CASE ... CAST(1 AS bit)` before this runs. `SearchConditionConvertingExpressionVisitor` does that — but from `SqlServerParameterBasedSqlProcessor.Optimize:45`, *after* `base.Optimize` at `:41`, which is what runs `VisitCase`. The nesting exists only in the final SQL. Every relational provider is affected.

In a `WHERE` or `ORDER BY` this changes the row set and row order, not just a projected value.

### Also worth acting on

- **High** — no new test puts a boolean/logical expression in the CASE *result*. `..._with_mixed_checks` uses `&&` only in the *test* position, which is the safe case. The assertion machinery is sound (`AssertQuery` is a real LINQ-to-Objects oracle, seed data covers both branches) — the gap is a missing operator category, and it's exactly what let the Critical through six baseline-file updates.
- **Medium** — the soundness invariant is written down nowhere, while the two recursion arms give opposite signals: the unary arm is deliberately narrow, the binary arm entirely undiscriminated.
- Three Lows: the undocumented `null`-means-true sentinel in `DropNotNullChecks`, `func.Instance!` where the sibling at `:2394` pattern-matches defensively, and `IsNull(elseResult)` missing the reachable no-`ELSE` shape.

Two caveats on coverage: **no SQL Server instance was available**, so the SQL Server baselines this change updates were never executed — the empirical evidence is SQLite-only. And `broad-reviewer` briefly created then deleted an untracked probe file inside the repo tree, violating the read-only rule; I verified afterward that `git status` is clean and `HEAD` is unchanged, so no finding rests on a mutated tree. Both are recorded in the report's anomalies section.
