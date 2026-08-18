I'll start by invoking the requested skill.
Pre-flight passed. Dispatching the review wave.

**Review team** (preset `review`, explicit · roster N=6 derived: ~120 executable lines · models=norm · evidence=norm · reach=norm):
- `quick-reviewer` (always) — mid tier
- `broad-reviewer` (always) — mid tier
- `adversarial-reviewer` — 119 executable lines; query-compiler semantics, rank-1 specialist — session model
- `test-reviewer` — hard gate: test files present — mid tier
- `dotnet-reviewer` — hard gate: C# + idiom surface (nullable annotations, `!` laundering, hash-set equality on expression trees) — mid tier
- `consistency-reviewer` — dense sibling optimizations in the same file to compare against — mid tier
- `design-reviewer`: skipped — no public API/contract change, change confined to a method body
- `security-reviewer`: skipped — no trust-boundary trigger
- `performance-reviewer`: dropped — roster N=6 (derived: ~120 executable lines): ranked below the 4 specialists kept
- `knowledge-reviewer`: dropped — roster N=6: ranked last
- `spec-compliance-reviewer` / `data-migration-reviewer` / `prior-feedback-reviewer`: skipped — hard gates unmet
Wave dispatched; `quick-reviewer` has returned. I verified two load-bearing facts myself while the rest run:

- `SearchConditionConvertingExpressionVisitor` runs **after** `ProcessSqlNullability` (`src/EFCore.SqlServer/Query/Internal/SqlServerParameterBasedSqlProcessor.cs:40-45`), so a raw `AndAlso`/`OrElse` `SqlBinaryExpression` can legitimately be a `CaseWhenClause.Result` when the new code inspects it.
- `COALESCE` is built as a `SqlFunctionExpression` with `argumentsPropagateNullability: [false, false]` (`src/EFCore.Relational/Query/SqlExpressionFactory.cs:503-509`), and relational `SqlBinaryExpression(Coalesce, …)` is never constructed — so the COALESCE half of `quick-reviewer`'s claim does not hold, while the `AndAlso`/`OrElse` half does.

Waiting on the remaining five reviewers.
Consistency reviewer returned and independently corroborates the `AndAlso`/`OrElse` gap, quoting the file's own carve-out at `SqlNullabilityProcessor.cs:2314-2321`. Still waiting on `broad-reviewer`, `adversarial-reviewer`, `test-reviewer`, and `dotnet-reviewer`.
Verified `ExpressionType.And`/`Or` render as bitwise `&`/`|` (`QuerySqlGenerator.cs:1090,1097`), which do propagate NULL — so the unsound set narrows to `AndAlso`/`OrElse` only. Awaiting `broad-reviewer`, `adversarial-reviewer`, and `test-reviewer`.
Confirmed by reading the file: `SqlNullabilityProcessor` never sees a `SqlBinaryExpression` with `ExpressionType.Coalesce` — all `??` goes through `SqlExpressionFactory.Coalesce`, which builds a `SqlFunctionExpression` with `argumentsPropagateNullability: [false, false]` and is therefore correctly skipped. The COALESCE sub-claim raised by three reviewers is refuted; the `AndAlso`/`OrElse` root cause stands. Awaiting `adversarial-reviewer` and `test-reviewer`.
Five reviewers in; `test-reviewer` adds the coverage-gap side of the same root cause plus two untested-branch gaps. Awaiting `adversarial-reviewer`, then I will run the nominated probes.
All six reviewers are in. Running the nominated probes now — I am the only actor on the tree.
Pre-existing SDK mismatch (repo pins .NET 9 preview; env has 10.0.400) breaks `EFCore.Specification.Tests` — unrelated to this PR. Routing the probe through a standalone app instead.
Empirically confirmed on SQLite. Now verifying these are **introduced** by the change, by building the base commit in an isolated copy (no touch to this working tree).
Regression confirmed: base commit matches on all five; the change diverges on `OrElse` and `AndAlso`. Capturing the generated SQL.
SQL evidence captured. The `COALESCE` case provably keeps its guard. Now checking the SQL Server–specific claim offline via `ToQueryString()`.
Both SQL Server and SQLite evidence is now definitive. Verifying the remaining non-probed finding.
All probes complete. Cleaning up and writing the report.
✅ Review complete: `.decaf/code-reviews/CODE_REVIEW_2026-08-18_14-23-39.md`

**Verdict: ❌ NEEDS_CHANGES** — two confirmed silent wrong-result regressions.

Six reviewers ran (`review` preset, roster 6). Rather than a validation wave, I confirmed the load-bearing claims empirically: executed the candidate queries on SQLite and generated SQL Server SQL via `ToQueryString()`, each against both this change and base commit `051c33a79`. The working tree was never modified — probes ran from scratch projects against built assemblies, with the base materialized by `git archive`.

**#1 🔴 Critical — `SqlNullabilityProcessor.cs:626-629`.** `NullPropagatedOperands` recurses into every `SqlBinaryExpression` regardless of operator, so `AndAlso`/`OrElse` are treated as null-propagating. They are not: `NULL AND FALSE = FALSE`, `NULL OR TRUE = TRUE`. The `IS NOT NULL` guard is deleted and the query returns a boolean where it must return `null`. Confirmed by execution — `NullableBoolA = NULL, BoolB = true` returns `True` instead of `null`; base commit returns `null`. This file already carries the exact carve-out the new code omits, at `:2314-2321` (`// for AndAlso, OrElse we can't do this optimization`). Found by all six reviewers.

**#2 🔴 Critical — `SqlNullabilityProcessor.cs:576-591`.** A second, independent defect that survives the fix for #1. On SQL Server a boolean is a search condition, not a value; `SearchConditionConvertingExpressionVisitor` runs after nullability processing and lifts a bare condition with a two-arm `CASE … ELSE CAST(0 AS bit)`, which has no NULL arm. So dropping the guard loses the NULL even for genuinely null-propagating operators — `x.NullableIntA != null ? (bool?)(x.NullableIntA > x.IntB) : null` yields `false` instead of `null`. Confirmed by SQL diff; SQLite is unaffected. Found only by `adversarial-reviewer`.

**#3 🟠 High** — the five new tests use only non-boolean, null-propagating results, so all pass; no added test exercises either broken shape. The fixture data would have caught both.

Plus three Low findings (`func.Instance!` missing the null guard its sibling at `:2394` performs; `Negate` and `SqlFunctionExpression` branches untested).

**Refuted:** four reviewers independently claimed `COALESCE` is mishandled. It is not — `??` becomes a `SqlFunctionExpression` with `argumentsPropagateNullability: [false, false]`, and the probe emits an identical, correctly guarded `CASE` on both providers, matching base exactly. `dotnet-reviewer`'s extension of the claim to bitwise `And`/`Or` is also wrong; those render as `&`/`|` and do propagate NULL.

One caveat worth flagging: the repo's test projects do not compile in this environment (`global.json` pins .NET 9 preview; installed SDK is 10.0.400), which is why probes ran out-of-tree. That is an environment mismatch, not a defect in this change.

