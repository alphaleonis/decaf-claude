Review complete. Nothing was posted; output is terminal-only.

---

### Code review

Reviewed `git diff 051c33a79..afcfba2e9` (3 commits: new `VisitCase` null-propagation optimization + tests + baseline updates).

Found 1 issue:

**1. `NullPropagatedOperands` treats `AndAlso`/`OrElse` as null-propagating, which they are not in SQL's three-valued logic — this returns wrong data.**

`src/EFCore.Relational/Query/SqlNullabilityProcessor.cs:626-630`

```csharp
else if (expression is SqlBinaryExpression binary)
{
    NullPropagatedOperands(binary.Left, operands);
    NullPropagatedOperands(binary.Right, operands);
}
```

The set built here is consumed by `DropNotNullChecks` (line 595) to delete an `X IS NOT NULL` conjunct from the `WHEN` test. That is only sound if the result is guaranteed `NULL` whenever `X` is `NULL`. The branch above asserts that for *every* `SqlBinaryExpression` operator, but `AndAlso` and `OrElse` render as SQL `AND`/`OR` (`QuerySqlGenerator.cs:1097-1098` shows `And`/`Or` are the bitwise `&`/`|` variants — those *are* null-propagating; `AndAlso`/`OrElse` are not), where `NULL AND FALSE = FALSE` and `NULL OR TRUE = TRUE`.

Verified by execution. Built the SQLite provider at this commit and at the parent (`051c33a79`, in a separate worktree) and ran:

```csharp
ctx.Es.OrderBy(x => x.Id).Select(x => x.NB != null ? (bool?)(x.NB.Value && x.BoolB) : null)
```

over rows `(NB=null,BoolB=false), (NB=null,BoolB=true), (NB=true,BoolB=false), (NB=false,BoolB=true)`:

| | SQL | Results |
|---|---|---|
| parent `051c33a79` | `CASE WHEN "e"."NB" IS NOT NULL THEN "e"."NB" AND "e"."BoolB" ELSE NULL END` | `NULL, NULL, False, False` (correct) |
| this change | `"e"."NB" AND "e"."BoolB"` | **`False`**, `NULL`, `False`, `False` |

Row 1 changes from `NULL` to `False`. The `OrElse` form (`x.NB.Value \|\| x.BoolB`) is symmetric: row 2 changes from `NULL` to `True`. LINQ-to-Objects gives `NULL` for both, so `AssertQuery` would fail on these — no existing or new test covers a boolean/search-condition `WHEN` result, which is why CI is green. The five new tests in `NullSemanticsQueryTestBase.cs:2250-2295` all use `int?`/`string` results, where every operator involved genuinely propagates nulls.

Fix direction: restrict the binary recursion to operators that actually propagate nullability (arithmetic, bitwise `And`/`Or`/`ExclusiveOr`, comparisons) and exclude `AndAlso`, `OrElse`, and `Coalesce`. `Coalesce` is a legal `SqlBinaryExpression` operator (`src/EFCore.Relational/Query/SqlExpressions/SqlBinaryExpression.cs:102`) and is also not null-propagating; relational's factory currently emits `COALESCE` as a `SqlFunctionExpression` with `argumentsPropagateNullability: [false, false]` (`SqlExpressionFactory.cs:502-509`), so it is not reachable today, but the allow-list should exclude it rather than relying on that.

---

Minor, below the reporting bar (noted, not posted):

- `src/EFCore.Relational/Query/SqlNullabilityProcessor.cs:578` — `IsNull(elseResult)` is `false` when `elseResult` is C# `null`, i.e. a `CASE WHEN t THEN r END` with no `ELSE`. That is semantically identical to `ELSE NULL`, so the optimization is silently skipped for that shape. Missed optimization, not a correctness problem.
- Baseline updates in the GearsOfWar/Temporal/TPC/TPT files are all consistent with the new optimization and correct for the shapes involved (`LEN(x)`, string `+`, bare column).
