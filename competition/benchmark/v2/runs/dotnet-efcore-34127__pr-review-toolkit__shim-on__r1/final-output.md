Working tree is clean and back at `afcfba2e9`; all scratch artifacts removed.

# PR Review Summary — `051c33a79..afcfba2e9` ("Use null propagation to optimize away `IS NOT NULL` checks")

Six agents ran in parallel (code, tests, errors, comments, types, simplify). Three of them plus my own base-vs-head differential converged independently on the same root cause. **I confirmed the two critical findings by execution**, not inference: I built EF Core at both the base commit (`051c33a79`) and the head commit (`afcfba2e9`) and compared generated SQL for the same LINQ queries.

## Critical Issues (2) — these produce wrong query results

### C1. `NullPropagatedOperands` recurses into `AndAlso`/`OrElse` operands, which do not propagate NULL
**`src/EFCore.Relational/Query/SqlNullabilityProcessor.cs:626-630`** (enabling the drop at `:578-591`)

```csharp
else if (expression is SqlBinaryExpression binary)
{
    NullPropagatedOperands(binary.Left, operands);
    NullPropagatedOperands(binary.Right, operands);
}
```

The recursion is unconditional over every operator `SqlBinaryExpression.IsValidOperator` permits (`src/EFCore.Relational/Query/SqlExpressions/SqlBinaryExpression.cs:87-103`), which includes `AndAlso` and `OrElse`. Those emit SQL `AND`/`OR` (`src/EFCore.Relational/Query/QuerySqlGenerator.cs:1090-1091`) and are not strict: `NULL OR TRUE = TRUE`, `NULL AND FALSE = FALSE`. An operand nested under `||`/`&&` therefore enters `nullPropagatedOperands`, `DropNotNullChecks` (`:597-600`) deletes its `IS NOT NULL` test, and the `ELSE NULL` arm is lost.

**Verified.** `x.NullableBoolA != null ? x.NullableBoolA | x.NullableBoolB : null`:

| | SQL |
|---|---|
| base `051c33a79` | `CASE WHEN [e].[NullableBoolA] IS NOT NULL THEN CASE WHEN [e].[NullableBoolA] = CAST(1 AS bit) OR [e].[NullableBoolB] = CAST(1 AS bit) THEN CAST(1 AS bit) ELSE CAST(0 AS bit) END ELSE NULL END` |
| head `afcfba2e9` | `CASE WHEN [e].[NullableBoolA] = CAST(1 AS bit) OR [e].[NullableBoolB] = CAST(1 AS bit) THEN CAST(1 AS bit) ELSE CAST(0 AS bit) END` |

Row `NullableBoolA = NULL, NullableBoolB = true` → head returns `true`, the C# ternary yields `null`. The `&&` mirror returns `false` where `null` is expected. Two agents independently reproduced this end-to-end against a real SQLite database with row-level `Expected: null / Actual: False` assertion failures.

**Not confined to projections.** In predicate position it changes which rows come back:

```
WHERE (x.NullableIntA != null ? (bool?)(x.NullableIntA > 5 || x.BoolA) : null) == true
  base: WHERE CASE WHEN [NullableIntA] IS NOT NULL THEN CASE WHEN ... END ELSE NULL END = CAST(1 AS bit)
  head: WHERE [e].[NullableIntA] > 5 OR [e].[BoolA] = CAST(1 AS bit)
```
A row with `NullableIntA = NULL, BoolA = true` is now returned; previously it was excluded.

The decisive evidence that this is an oversight rather than a considered trade-off: **the same file already implements this exact rule correctly, with an explicit carve-out and a comment saying why** — `SqlNullabilityProcessor.cs:2314-2321`:

```csharp
case SqlBinaryExpression sqlBinaryOperand
    when sqlBinaryOperand.OperatorType != ExpressionType.AndAlso
    && sqlBinaryOperand.OperatorType != ExpressionType.OrElse:
    // binaryOp(a, b) == null -> a == null || b == null
    // for AndAlso, OrElse we can't do this optimization
```

**Fix:** replace the catch-all with a strict-operator allow-list (`Add, Subtract, Multiply, Divide, Modulo, And, Or, ExclusiveOr, Equal, NotEqual, LessThan(OrEqual), GreaterThan(OrEqual)`), excluding `AndAlso`, `OrElse`, `Coalesce` — mirroring `:2314`.

### C2. On SQL Server, the rewrite turns NULL into `false` for *any* boolean-valued THEN result — including strict ones
**`src/EFCore.Relational/Query/SqlNullabilityProcessor.cs:578-591`**

`SqlNullabilityProcessor` runs before `SearchConditionConvertingExpressionVisitor` (`src/EFCore.SqlServer/Query/Internal/SqlServerParameterBasedSqlProcessor.cs:45`), which wraps a search condition used as a *value* in `CASE WHEN <cond> THEN CAST(1 AS bit) ELSE CAST(0 AS bit) END` (`SearchConditionConvertingExpressionVisitor.cs:41-51`) — a two-arm CASE with no NULL branch, so SQL's UNKNOWN collapses to `false`. While the condition sits inside the original `CASE … ELSE NULL END`, the outer CASE preserves NULL. Drop it and nothing does.

**Verified.** `x.NullableStringA != null ? (bool?)(x.NullableStringA != "x") : null`:

| | SQL |
|---|---|
| base | `CASE WHEN [e].[NullableStringA] IS NOT NULL THEN CASE WHEN [e].[NullableStringA] <> N'x' THEN CAST(1 AS bit) ELSE CAST(0 AS bit) END ELSE NULL END` |
| head | `CASE WHEN [e].[NullableStringA] <> N'x' THEN CAST(1 AS bit) ELSE CAST(0 AS bit) END` |

For `NullableStringA IS NULL` the head query returns `false`; the C# ternary yields `null`. `<>` **is** strict — so fixing C1 alone does not fix this. Same for `==`, `>`, `<`.

This one is provider-dependent: SQLite emits a bare comparison that yields NULL and is unaffected, so **a SQLite-only test run structurally cannot catch it.**

**Fix:** skip the rewrite when `clause.Result` is a search condition — in practice when the type is `bool`/`bool?`.

Not every boolean result is affected: `!x.NullableBoolA.Value` translates to the value expression `[NullableBoolA] ^ CAST(1 AS bit)`, which is strict and stays correct (I verified). String and numeric results are correct too — which is exactly why all five new tests and every updated baseline pass.

## Important Issues (2)

### I3. `Coalesce` as a `SqlBinaryExpression` would be mis-analyzed — defensive only
`src/EFCore.Relational/Query/SqlNullabilityProcessor.cs:626-630`. `ExpressionType.Coalesce` is a legal operator (`SqlBinaryExpression.cs:102`) and neither operand propagates NULL. **This is currently unreachable**: `SqlExpressionFactory.Coalesce` (`src/EFCore.Relational/Query/SqlExpressionFactory.cs:502-509`) emits a `COALESCE` *function* with `argumentsPropagateNullability: [false, false]`, which the function branch at `:642` handles correctly — I confirmed `x.NullableIntA != null ? (int?)(x.NullableIntA ?? 99) : null` correctly keeps its CASE at head. Today's safety is an accident of one factory method, not an enforced invariant; a provider constructing the binary form gets a silently wrong rewrite. The C1 allow-list closes this.

*(Two agents asserted the `COALESCE` in the `_with_partial_checks` baseline proves the binary-Coalesce path is reached. That inference is wrong — it is the function form. Correcting it here because it changes the severity, not the fix.)*

### I4. The rewrite deletes the assumption its own translation was built on
`src/EFCore.Relational/Query/SqlNullabilityProcessor.cs:512-514` and `:578-591`. `clause.Result` is visited with `preserveColumnNullabilityInformation: true` — translated *assuming the tested columns are non-null*. That is why `_with_partial_checks` yields `[A] + [B] + COALESCE([C], N'')` with no COALESCE on the checked columns. The new code then removes the test that justified the assumption. The surviving rewrites happen to be strict today, but nothing enforces it — e.g. `IsNull(non_nullable_column) -> false` at `:2282` becomes unsound the moment its guard is dropped. Worth an explicit stated invariant at minimum.

## Suggestions

- **`:635`** — `NullPropagatedOperands(func.Instance!, operands)`: the null-forgiving `!` asserts an invariant `SqlFunctionExpression`'s constructor never checks (`SqlFunctionExpression.cs:186-226` validates only argument-count parity). Use the form already established at `:2394`: `func is { InstancePropagatesNullability: true, Instance: not null }`. This branch has **zero** test coverage — its only producers are the NTS/HierarchyId translators, which pass `elseResult: null` and so never reach the guard at `:578`.
- **`:578`** — `IsNull(elseResult)` returns `false` for C# `null` (`:1633-1635`), so `CASE WHEN t THEN r END` (no ELSE) is never optimized despite being semantically identical to `ELSE NULL`, and being handled as such at `:562`. Missed optimization, not a bug — but say which it is.
- **`:576`** — `// optimize expressions such as expr != null ? expr : null` describes only the degenerate case; the code handles arbitrarily deep sub-expressions, conjunctions, and partial drops. Also written in C# binary-inequality syntax while the matched node at `:597` is a *unary* `NotEqual` (`IS NOT NULL`).
- **`:600`** — `return null; // true` is not true: the matched `IS NOT NULL` is false for many rows. What holds is the conditional claim that dropping it is value-preserving *inside a `CASE … ELSE NULL`*. A maintainer trusting the comment will reuse `DropNotNullChecks` where it is unsound.
- **`:617`** — `NullPropagatedOperands` is the only noun-phrase `void` method in the file (cf. `DropNotNullChecks`, `TryNegate`, `IsLogicalNot`); reads like a property at the call site `:582`. Suggest `CollectNullPropagatingOperands`.
- **`:602-615`, `:621-648`** — both local functions use `if/else if/else` type-pattern chains; the file's prevailing style for subtype dispatch is `switch` (`:409-448`, `:1974-2091`, `:2259-2433`).
- **`:590`** — `whenClauses = [new(test, clause.Result)]` uses a bare target-typed `new` where `:537` spells `new CaseWhenClause(...)`; also allocates a second list when `whenClauses[0] = …` would do.
- **`:577`** — the bare `// TODO: optimize expr == null ? null : expr` is within convention here (47 TODOs in `src/EFCore.Relational/Query/`, only 13 issue-linked), but unlike its siblings it doesn't say *why* the dual case is deferred.

## Test Coverage Gaps

All five new tests (`test/EFCore.Relational.Specification.Tests/Query/NullSemanticsQueryTestBase.cs:2250-2295`) are **positive** — every one asserts the optimization fires. There is no test asserting it must *not* fire, and **none has a boolean-typed THEN result**. C1 and C2 live precisely in that untested quadrant.

Minimum additions, as `AssertQuery` (data-comparing, not baseline-only — a baseline-only test would happily record the wrong SQL as expected):

```csharp
x => x.NullableBoolA != null ? (bool?)(x.NullableBoolA.Value || x.BoolB) : null   // C1: OrElse result
x => x.NullableBoolA != null ? (bool?)(x.NullableBoolA.Value && x.BoolB) : null   // C1: AndAlso result
x => x.NullableStringA != null ? (bool?)(x.NullableStringA != x.StringA) : null   // C2: strict comparison result
x => x.NullableIntA != null ? (int?)(x.NullableIntA ?? 0) : null                  // I3: pin the COALESCE non-firing
```

Also uncovered: `DropNotNullChecks`'s `binary.Update(left, right)` arm at `:609` (no test has ≥2 surviving conjuncts), the `right is null ? left` arm at `:608`, `InstancePropagatesNullability` (`:633`), the `IsNiladic` guard (`:638`), and `Negate`. `~` **is** covered (via `Is_not_null_optimizes_unary_op`).

Naming nits: `_with_partial_checks` (`:2270`) is the test where the CASE is eliminated *completely*, while `_with_mixed_checks` (`:2290`) is the only genuinely partial one — the names are effectively swapped relative to what they assert.

## Strengths

- The unary (`:621-622`) and function (`:631-647`) branches are correct by construction — an explicit three-operator allow-list, and deference to `IsNullable`/`InstancePropagatesNullability`/`ArgumentsPropagateNullability` rather than assumption. The missing binary carve-out reads as a genuine omission against that standard.
- `DropNotNullChecks` fails in the safe direction: unrecognized shapes fall to `:613` and are *kept*, and it only descends through `AndAlso`, so returning `null` ("TRUE") is always in conjunctive position.
- The GearsOfWar baseline churn is all semantically sound — I traced each distinct change. `WHERE CAST(LEN(x) AS int) = 5` is safe because UNKNOWN and FALSE are indistinguishable in a `WHERE`, and the `SELECT [c].[Name]` cases are the trivial identity. No stale baselines were found across the 41 candidate `WHEN <col> IS NOT NULL THEN <…col…>` patterns in `test/`.
- `Is_not_null_optimizes_binary_op_with_nested_checks` (`:2280`) is the strongest of the five — it pins recursive application (the inner CASE must collapse before the outer test becomes droppable).

## Recommended Action

1. **Block on C1 and C2.** Both change query results; C2 is silent and SQL-Server-specific.
2. Fix C1 with the operator allow-list mirroring `:2314-2321`; fix C2 by excluding boolean-typed results.
3. Add the four negative/boolean-result tests above, plus SQLite overrides — C2 showed the two providers diverge materially, and `NullSemanticsQuerySqliteTest` currently inherits all five new tests with no SQL baseline.
4. Then address I4's invariant comment and the smaller items.

**Adjacent, out of scope:** `:539` passes `currentNonNullableColumnsCount` to `RestoreNullValueColumnsList` where `:529` and `:566` both pass `currentNullValueColumnsCount`. Confirmed pre-existing via `git log -L` (introduced in `17a9035ad`, Oct 2023) — not part of this change, but it sits inside the method under review and corrupts the `_nullValueColumns` bookkeeping this optimization now depends on.
