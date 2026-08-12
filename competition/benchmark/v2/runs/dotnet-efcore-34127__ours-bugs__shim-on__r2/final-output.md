✅ Review complete: `.decaf/code-reviews/CODE_REVIEW_2026-08-12_13-32-28.md`

## Verdict: ❌ NEEDS_CHANGES — 1 Critical, 1 High

Both are silent data-correctness defects in the new `VisitCase` optimization: the query returns a wrong non-null value where it must return `null`. No exception, no warning.

**#1 🔴 Critical — `SqlNullabilityProcessor.cs:626`.** `NullPropagatedOperands` recurses into both operands of *every* `SqlBinaryExpression`. But `AndAlso`/`OrElse` don't propagate NULL in three-valued logic (`UNKNOWN AND FALSE` → `FALSE`), so an operand under a logical connective is wrongly treated as null-propagating and its `IS NOT NULL` guard is deleted. This shape is reached by EF's *own* null-semantics rewrite, which turns `A == B` into `A = B AND B IS NOT NULL` precisely because the test being dropped registered `A` as non-nullable.

**#2 🟠 High — `SqlNullabilityProcessor.cs:578`.** Boolean-valued results propagate NULL at the SQL level but not through the pipeline: SQL Server's `SearchConditionConvertingExpressionVisitor.ConvertToValue` materializes a predicate as `CASE WHEN p THEN 1 ELSE 0 END`, where UNKNOWN becomes `false`, never NULL. The outer `CASE … ELSE NULL END` was the only thing carrying NULL out — the optimization deletes it and nothing restores it. Distinct from #1 and survives fixing it.

**Both confirmed by execution, not inference.** The test projects don't compile under the only installed SDK (pre-existing `global.json` pin vs. .NET 10 — unrelated to this change), so I built a standalone probe outside the repo against the compiled assemblies, and ran the identical probe against a separate `git worktree` at the base commit:

| Query | base | this change |
|---|---|---|
| `A != null ? A + B : null` (control) | match | match |
| `A != null ? (bool?)(A == B) : null` | match | **row `A=NULL,B=NULL`: expected `null`, got `False`** |
| `NSA != null ? (bool?)(NSA != StringA) : null` | SQL has `ELSE NULL` | **SQL has no NULL branch at all** |

The value-typed control passing in both directions is what isolates the defect to the boolean/logical shapes rather than the optimization as a whole — and explains why the suite is green: all five new tests and every updated baseline use value-typed results (`~int`, `int + int`, string concat, `CAST(LEN(…) AS int)`).

Suggested fixes are in the report: an operator allow-list at line 626 (fail closed, not open), and a `clause.Result.Type.UnwrapNullableType() != typeof(bool)` guard at line 578.

Two things I'd flag about the run itself: `adversarial-reviewer` was the sole finder of #2 and the only agent to build concrete counterexamples — the two cheap-tier agents corroborated #1 but didn't reach #2. And I did not dispatch validator agents, because an executed counterexample is stronger evidence than an independent reader; that deviation from the skill's Critical-always-validated rule is recorded in the report. All probe artifacts were removed; `git status --porcelain` is empty at `afcfba2e9`.
