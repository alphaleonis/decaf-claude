✅ Review complete: `.decaf/code-reviews/CODE_REVIEW_2026-08-11_17-07-31.md`

(No prior reviews exist in this repo, so the Recurring Findings step was skipped. `git status` confirms no tracked file was modified.)

## Verdict: ❌ NEEDS_CHANGES — 2 Critical, 1 Medium, 3 Minor

The optimization is unsound. I reproduced wrong results by execution, not inference — building this branch's `EFCore.Sqlite`/`EFCore.SqlServer` and running queries from a scratch console app under `/tmp`.

**#1 🔴 `SqlNullabilityProcessor.cs:626` — `NullPropagatedOperands` recurses through `AndAlso`/`OrElse`**, which don't propagate NULL in SQL three-valued logic (`NULL OR TRUE = TRUE`). That lets `DropNotNullChecks` delete a load-bearing `IS NOT NULL` guard. Confirmed against in-memory SQLite:

| Query | SQL returns | Correct |
|---|---|---|
| `a != null ? (bool?)(a > 5 \|\| BoolB) : null` | `True` | `null` |
| `a != null ? (bool?)(a > 5 && BoolB) : null` | `False` | `null` |
| `a != null ? (bool?)(a == b) : null` | `False` | `null` |

In a `WHERE` clause it **returns extra rows**: the third row of that table is the severe one — it contains no user-written `&&`/`||`. EF *generates* the `AndAlso` itself, because the guard is in `_nonNullableColumns` while the result is visited, collapsing the equality to `a = b AND b IS NOT NULL`; the optimization then deletes the guard that licensed that collapse. All six reviewers found this independently, and the same file's canonical routine `ProcessNullNotNull` (line 2313) already carries the exclusion with the comment *"for AndAlso, OrElse we can't do this optimization"*.

**#2 🔴 `SqlNullabilityProcessor.cs:587` — boolean-typed results become `false` instead of `null` on SQL Server.** `SearchConditionConvertingExpressionVisitor` runs *after* this pass and emits `CASE WHEN cond THEN CAST(1 AS bit) ELSE CAST(0 AS bit) END` — no NULL arm. I generated the SQL to confirm; `a != null ? (bool?)(a > 5) : null` becomes a bare two-valued CASE. This is independent of #1 (no logical operator; `GreaterThan` genuinely propagates NULL) and #1's fix won't address it. SQLite is unaffected, which my run confirms. *(Not executed against a live SQL Server — none available — but the ELSE-arm semantics are ANSI-standard.)*

**#3 🟡 `:617` — the null-propagation rule is now encoded twice** and has already diverged from `ProcessNullNotNull` in three ways (the AndAlso/OrElse exclusion, the COALESCE case, the defensive `Instance` check). #3 is the structural cause of #1.

Two reviewer findings were **refuted** by validators and are recorded with reasons: binary-`Coalesce` (unreachable in-box, and `QuerySqlGenerator` throws on it anyway) and "no provider seam" (hard-coded optimizations are this file's norm, not a deviation).
