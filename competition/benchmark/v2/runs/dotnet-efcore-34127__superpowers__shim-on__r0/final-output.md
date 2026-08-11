Reviewer subagent report, verbatim:

---

# Code Review: Null-propagation optimization of `IS NOT NULL` checks

## Verification performed

I could not run the repo's own test suites: `test/EFCore.Specification.Tests` does not compile under the only installed SDK (10.0.203; `global.json` pins 9.0.100-preview with `rollForward: latestMajor`), failing with pre-existing errors in `CustomConvertersTestBase.cs` and `TestUtilities/QueryTestGeneration/*` unrelated to this change. SQL Server functional tests additionally need a database that isn't available.

Instead I built `EFCore.Relational`, `EFCore.Sqlite.Core` and `EFCore.SqlServer` at **HEAD** and at **base (051c33a79, via a throwaway `git worktree`)** and ran a standalone probe app that (a) executes queries against in-memory SQLite and compares to LINQ-to-objects semantics, and (b) prints `ToQueryString()` for SQL Server. Everything marked "verified" below is from actual execution or actual generated SQL, diffed base-vs-HEAD. The worktree has been removed; `git status` is clean and HEAD is unchanged.

---

### Strengths

- **The core rewrite rule is sound and the guards around it are well chosen.** `CASE WHEN X IS NOT NULL AND rest THEN R ELSE NULL END` → `CASE WHEN rest THEN R ELSE NULL END` is correct whenever `X IS NULL ⟹ R IS NULL`: if `X` is NULL the original short-circuits `AndAlso` to FALSE (not UNKNOWN) and yields NULL, and the rewritten form yields either NULL (test not true) or `R` = NULL. The restriction to a **single** when-clause, to an **`ELSE NULL`** arm, and to descending only through **`AndAlso`** in `DropNotNullChecks` (`SqlNullabilityProcessor.cs:595-614`) are each load-bearing and each correct. Dropping a conjunct into `OrElse` would not have been.
- **`SqlFunctionExpression` handling is precise** (`:631-649`): it respects `IsNullable`, `InstancePropagatesNullability`, `ArgumentsPropagateNullability`, and guards `IsNiladic` before touching `Arguments`. This is exactly why `COALESCE` — built by `SqlExpressionFactory.Coalesce` as a function with `argumentsPropagateNullability: [false, false]` — is correctly *not* optimized. I verified the negative case: `x.NI_A != null ? (x.NI_A ?? 99) : null` still emits the full `CASE`.
- **Bottom-up composition falls out for free.** `Is_not_null_optimizes_binary_op_with_nested_checks` collapses a two-level nested `CASE` to a bare `A + B` because the inner `CASE` is simplified during `Visit(whenClause.Result, …)` before the outer test is examined. That's an elegant consequence of the placement, not an accident.
- **The reasoning is done on the post-simplification result tree**, which sidesteps a trap I went looking for: `Result` is visited while the tested columns are in `_nonNullableColumns`, so it may have been simplified under an assumption that no longer holds once the guard is dropped. Because null-propagation is re-derived from the *simplified* tree, this is safe.
- **All 25 changed baseline hunks are genuinely equivalent.** I checked each: `LEN(x)`/`length(x)` and `CAST(… AS int)` propagate NULL; `x || x` / `x + x` propagate NULL (under `CONCAT_NULL_YIELDS_NULL ON`, which EF already assumes everywhere); `CASE WHEN c.Name IS NOT NULL THEN c.Name ELSE NULL END → c.Name` is an identity. The two `WHERE … = 5` cases go UNKNOWN either way. No baseline was "just accepted".
- **The added spec tests use `AssertQuery`**, so they compare against in-memory expected results rather than only asserting SQL text. That's the right shape of test.

---

### Issues

#### Critical (Must Fix)

**C1 — `NullPropagatedOperands` treats `AndAlso`/`OrElse` as null-propagating; they are not. Verified wrong results.**
`src/EFCore.Relational/Query/SqlNullabilityProcessor.cs:626-630`

```csharp
else if (expression is SqlBinaryExpression binary)
{
    NullPropagatedOperands(binary.Left, operands);
    NullPropagatedOperands(binary.Right, operands);
}
```

This matches **every** `SqlBinaryExpression` operator. `AndAlso` and `OrElse` do not propagate NULL in SQL three-valued logic: `NULL AND FALSE = FALSE` and `NULL OR TRUE = TRUE`. So the precondition "`X IS NULL ⟹ Result IS NULL`" fails, and the guard is dropped anyway.

Failure scenario (executed against in-memory SQLite, base vs HEAD):

| Query | Row | Correct (`base`, and LINQ-to-objects) | HEAD |
|---|---|---|---|
| `x.NB_A != null ? (bool?)(x.NB_A.Value && x.B_B) : null` | `NB_A = null, B_B = false` | `null` | **`false`** |
| `x.NB_A != null ? (bool?)(x.NB_A.Value \|\| x.B_B) : null` | `NB_A = null, B_B = true` | `null` | **`true`** |
| `x.NB_A != null ? (x.NB_A & x.NB_B) : null` | `NB_A = null, NB_B = false` | `null` | **`false`** |
| `x.NI_A != null ? (bool?)(x.NI_A == x.NI_B) : null` | `NI_A = null, NI_B = null` | `null` | **`false`** |

Base SQL: `SELECT CASE WHEN "e"."NB_A" IS NOT NULL THEN "e"."NB_A" AND "e"."B_B" ELSE NULL END`.
HEAD SQL: `SELECT "e"."NB_A" AND "e"."B_B"`.

Note the last row: EF's own null-semantics expansion of `a == b` produces an `AndAlso`/`OrElse` tree (`"NI_A" = "NI_B" AND "NI_B" IS NOT NULL`), so this defect is reachable from ordinary equality comparisons, not only from explicit boolean operators. Note also `RelationalSqlTranslatingExpressionVisitor.cs:442-443` normalizes bitwise `&`/`|` on booleans into `AndAlso`/`OrElse`, so excluding those two operator types covers the boolean `And`/`Or` case as well.

**Fix:** replace the blanket `is SqlBinaryExpression` with an explicit allow-list of genuinely null-propagating operators — `Add, Subtract, Multiply, Divide, Modulo, ExclusiveOr`, and `And`/`Or` only for non-boolean (bitwise) operands — and exclude `AndAlso`, `OrElse`, and `Coalesce` (see I1).

---

**C2 — Boolean-typed results are unsound even when 3VL-correct, because EF materializes search conditions with no NULL arm. Verified via generated SQL Server SQL.**
`src/EFCore.Relational/Query/SqlNullabilityProcessor.cs:626-630` (comparison operators)

Comparison operators (`Equal`, `GreaterThan`, …) do yield UNKNOWN on a NULL operand, so treating them as null-propagating is defensible in pure 3VL. It is **not** defensible in EF, because `SearchConditionConvertingExpressionVisitor.ConvertToValue` (`src/EFCore.SqlServer/Query/Internal/SearchConditionConvertingExpressionVisitor.cs`) materializes a search condition in value position as:

```csharp
_sqlExpressionFactory.Case(
    new[] { new CaseWhenClause(SimplifyNegatedBinary(sqlExpression), Constant(true)) },
    _sqlExpressionFactory.Constant(false))   // <- no NULL arm
```

Previously the outer `CASE … ELSE NULL` preserved the NULL; once the guard is dropped, UNKNOWN collapses to `false`. Generated SQL Server SQL, base vs HEAD:

```
-- x.NS_A != null ? (bool?)(x.NS_A.Length == 5) : null
-- base:
SELECT CASE WHEN [e].[NS_A] IS NOT NULL
            THEN CASE WHEN CAST(LEN([e].[NS_A]) AS int) = 5 THEN CAST(1 AS bit) ELSE CAST(0 AS bit) END
            ELSE NULL END
-- HEAD:
SELECT CASE WHEN CAST(LEN([e].[NS_A]) AS int) = 5 THEN CAST(1 AS bit) ELSE CAST(0 AS bit) END
```

Every gear with a NULL `NS_A` now projects `false` instead of `null`. Same collapse verified for `NI_A > 5` and for the C1 shapes. This is precisely the existing `Select_null_propagation_negative1` test with the tested column and the result column made the same — it escapes today only because that test happens to use two different columns.

**Fix:** in addition to C1, gate the whole optimization on `clause.Result.Type != typeof(bool)`, or make the boolean case conditional on the provider preserving NULL for search conditions. (`Not`-via-XOR is fine — `[NB_A] ^ CAST(1 AS bit)` is a bit-wise XOR that does propagate NULL; I checked.)

---

#### Important (Should Fix)

**I1 — `ExpressionType.Coalesce` is a legal `SqlBinaryExpression` operator and would be miscompiled.**
`SqlNullabilityProcessor.cs:626-630` vs `SqlExpressions/SqlBinaryExpression.cs:102`

`IsValidOperator` accepts `Coalesce`, so `new SqlBinaryExpression(ExpressionType.Coalesce, …)` is constructible by any provider or by future EF code. `COALESCE(a, b)` propagates null from *neither* operand. EF's own `SqlExpressionFactory.Coalesce` currently routes to a `SqlFunctionExpression` with `argumentsPropagateNullability: [false, false]`, so this is latent today — but it is exactly the kind of thing an allow-list makes safe by construction and a blanket type test makes fragile. Fold it into the C1 allow-list.

**I2 — The added tests cover only the subset of shapes where the rewrite is sound.**
`test/EFCore.Relational.Specification.Tests/Query/NullSemanticsQueryTestBase.cs:2252-2296`

All five tests use arithmetic (`~`, `+`), string concat, or `COALESCE` results. None uses a **boolean-typed** result, which is where the optimization breaks (C1/C2). Also missing:
- `useRelationalNulls: true` (the fixture supports both; only the default mode is exercised).
- Negative tests asserting the optimization does *not* fire: `COALESCE(A, k)` result, result independent of the tested column. I verified both behave correctly today, but nothing locks that in — a future widening of `NullPropagatedOperands` would break them silently.
- No `useRelationalNulls`/non-projection variant of `Is_not_null_optimizes_binary_op_with_mixed_checks`.

Add at minimum the four boolean shapes from the C1 table as spec tests; they fail today.

**I3 — Requirement 2 as written is too weak, and the task description doesn't match the code.**

The stated bar is "semantics-preserving under SQL three-valued logic". C2 shows that is not sufficient in EF: `ConvertToValue` maps UNKNOWN → `false`, so a rewrite can be 3VL-faithful and still change observable results for a `bool?` projection. The real invariant is "the CASE and its replacement must produce the same *materialized value*". Worth stating explicitly, because it's the assumption that failed.

Separately, the task description says the optimization fires "when visiting a binary expression"; the code is entirely in `VisitCase` (`:576-650`) and rewrites `CaseExpression`s. Worth confirming the description, not the code, is what's stale.

**I4 — The null-propagation knowledge is closed to providers.**
`SqlNullabilityProcessor.cs:595-650`

`SqlNullabilityProcessor` is explicitly an extension point (`protected virtual Visit*`, `VisitCustomSqlExpression`), but both helpers are `static` local functions inside `VisitCase`. A provider with a custom nullable-propagating expression type gets the conservative default (node added, no descent) — safe, but not extensible. More concerning: `is SqlBinaryExpression` / `is SqlFunctionExpression` also match *provider subclasses*, whose null semantics may differ from the base type's. Consider a `protected virtual void CollectNullPropagatingOperands(SqlExpression, HashSet<SqlExpression>)`.

---

#### Minor (Nice to Have)

- **`SqlNullabilityProcessor.cs:617`** — `NullPropagatedOperands` is a noun phrase naming a `void` mutator. `CollectNullPropagatingOperands` reads better and states the direction ("operands *whose* nullness propagates to the result", which is what it computes).
- **`SqlNullabilityProcessor.cs:578`** — `IsNull(elseResult)` returns `false` when `elseResult` is C# `null` (i.e. a `CASE` with no `ELSE`), which is semantically identical to `ELSE NULL`. Missed optimization and an inconsistency in the guard. `elseResult is null || IsNull(elseResult)` covers it.
- **`SqlNullabilityProcessor.cs:580-582`** — the `HashSet` is allocated and the whole result tree walked before checking whether `clause.Test` contains any `IS NOT NULL` at all. Compile-time only and cached, so low impact, but a cheap `Test`-side pre-check would avoid the common no-op case.
- **`SqlNullabilityProcessor.cs:577`** — bare `// TODO: optimize expr == null ? null : expr` with no issue link. Repo convention is generally to reference an issue.
- **Adjacent, pre-existing (not introduced here)** — `SqlNullabilityProcessor.cs:539` calls `RestoreNullValueColumnsList(currentNonNullableColumnsCount)` where it almost certainly means `currentNullValueColumnsCount`. Present unchanged at the base commit, so out of scope, but it's 40 lines above the new code and governs the same nullability bookkeeping the new logic depends on. Worth a separate issue.

---

### Recommendations

1. Replace both blanket type tests in `NullPropagatedOperands` with explicit allow-lists (operator kinds for binaries, and keep the existing careful function handling). "Deny-list by omission" is the wrong default for a soundness predicate — the failure mode is silent wrong data.
2. Add the failing boolean shapes as spec tests *before* fixing, so the fix is demonstrably driven by them.
3. Add a short comment above `NullPropagatedOperands` stating the invariant it must maintain ("membership means: if this sub-expression is NULL, the whole result is NULL") — that one sentence makes the `AndAlso` and `Coalesce` exclusions self-evident to the next reader.
4. Consider running the full `GearsOfWarQuery`/`NullSemanticsQuery`/`NorthwindQuery` suites for **all** providers before merge; only SqlServer GoW variants and Sqlite GoW baselines were updated, and I couldn't run the suites to confirm nothing else drifted.

---

### Assessment

**Ready to merge?** No.

**Reasoning:** The core rewrite and its guards are well designed, and the baseline updates are all genuinely equivalent — but `NullPropagatedOperands` descends into `AndAlso`/`OrElse` and comparison operators, which are not null-propagating, producing verified wrong results (`false`/`true` where `null` is correct) on both SQLite and SQL Server for boolean-typed `CASE` results. The added tests miss this entire class because they only exercise arithmetic and string results.
