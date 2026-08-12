Repository is clean again (temporary worktree removed; `artifacts/` is gitignored). Nothing was posted anywhere and no repository code was modified — the reproduction was built in `/tmp`.

---

### Code review

Found 1 issue:

**1. `NullPropagatedOperands` recurses into *every* `SqlBinaryExpression` operator, but `AndAlso`/`OrElse` do not propagate nullability in SQL's three-valued logic — the optimization drops a required `IS NOT NULL` guard and changes query results.**

`src/EFCore.Relational/Query/SqlNullabilityProcessor.cs:626-630`

```csharp
else if (expression is SqlBinaryExpression binary)
{
    NullPropagatedOperands(binary.Left, operands);
    NullPropagatedOperands(binary.Right, operands);
}
```

`SqlBinaryExpression.IsValidOperator` (`src/EFCore.Relational/Query/SqlExpressions/SqlBinaryExpression.cs:84-105`) admits `AndAlso`, `OrElse` and `Coalesce` alongside the arithmetic/comparison operators. Arithmetic and comparison genuinely propagate null, so collecting their operands is sound. `AndAlso`/`OrElse` do not: `NULL OR TRUE` is `TRUE` and `NULL AND FALSE` is `FALSE`. So `x` appearing under an `OR`/`AND` in the `THEN` branch does **not** mean the branch is `NULL` when `x` is `NULL`, yet `DropNotNullChecks` (`:595`) still deletes the `x IS NOT NULL` test at `:578-592`.

Note the operator type is the only thing that matters here — `bool` `|`/`&` are normalized to `OrElse`/`AndAlso` by `RelationalSqlTranslatingExpressionVisitor` (`src/EFCore.Relational/Query/RelationalSqlTranslatingExpressionVisitor.cs:442-443`), so they are affected too.

**Verified by execution.** I built the SQLite provider at both `051c33a` (baseline) and `afcfba2` (this change) and ran the same queries against a real database with rows `{A=null,B=true}`, `{A=null,B=false}`, `{A=true,B=false}`:

| query | LINQ-to-Objects (expected) | baseline `051c33a` | this change `afcfba2` |
|---|---|---|---|
| `x.NullableBoolA != null ? x.NullableBoolA.Value \|\| x.BoolB : (bool?)null` | `NULL, NULL, True` | `NULL, NULL, True` | **`True`, NULL, True** |
| `x.NullableBoolA != null ? x.NullableBoolA.Value && x.BoolB : (bool?)null` | `NULL, NULL, False` | `NULL, NULL, False` | `NULL`, **`False`**, `False` |

SQL emitted after the change:

```sql
SELECT "e"."NullableBoolA" OR "e"."BoolB" FROM "Entities" AS "e"      -- guard gone
```

versus baseline:

```sql
SELECT CASE WHEN "e"."NullableBoolA" IS NOT NULL
            THEN "e"."NullableBoolA" OR "e"."BoolB" ELSE NULL END
FROM "Entities" AS "e"
```

This is not confined to projections — it changes which rows are returned. `Where(x => (x.NullableBoolA != null ? x.NullableBoolA.Value || x.BoolB : (bool?)null) == true)` returns row `3` at baseline and rows `1, 3` after the change, because the predicate becomes `WHERE "NullableBoolA" OR "BoolB"`.

The new tests (`test/EFCore.Relational.Specification.Tests/Query/NullSemanticsQueryTestBase.cs:2250-2295`) only cover `~`, `+` on ints, and string concatenation — all genuinely null-propagating — so nothing in the suite catches this. `Coalesce` happens to be safe today only by accident: `SqlExpressionFactory.Coalesce` (`src/EFCore.Relational/Query/SqlExpressionFactory.cs:484-510`) emits a `SqlFunctionExpression` with `argumentsPropagateNullability: [false, false]` rather than a `SqlBinaryExpression`, which I also confirmed at runtime (the `COALESCE` case keeps its `CASE` guard). But since the `Coalesce` operator is legal on `SqlBinaryExpression`, a provider constructing one directly would hit the same hole.

Suggested fix: restrict the `SqlBinaryExpression` recursion to operators that actually propagate null, e.g.

```csharp
else if (expression is SqlBinaryExpression binary
    && binary.OperatorType is not (ExpressionType.AndAlso or ExpressionType.OrElse or ExpressionType.Coalesce))
```

and add coverage for a `bool?` result built with `&&`/`||`.

---

Secondary observations, below the bar I'd post as findings:

- `src/EFCore.Relational/Query/SqlNullabilityProcessor.cs:580-581` — `NullPropagatedOperands` walks the entire `THEN` tree for *every* single-when-clause `CASE` with a `NULL` else, even when the test contains no `IS NOT NULL` at all. Gating on the test shape first would avoid the allocation and traversal. Minor.
- `src/EFCore.Relational/Query/SqlNullabilityProcessor.cs:577` — the `// TODO: optimize expr == null ? null : expr` carries no issue link; most TODOs in this area reference a tracking issue.
