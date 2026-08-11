All five agents are in, and I independently verified the two critical findings by building and running the changed code. Repo working tree is unmodified.

---

# PR Review Summary — `SqlNullabilityProcessor` null-propagation optimization
`051c33a79 → afcfba2e9` · 8 files, +202/−100

## Verification method

I built `src/EFCore.Sqlite` and `src/EFCore.SqlServer` at **head** and at **base** (in throwaway git worktrees, since removed) and ran the same queries against both. The repo's own test projects **do not compile** under the installed SDK (10.0.203) for reasons unrelated to this diff (`test/EFCore.Specification.Tests/TestUtilities/QueryTestGeneration/InjectWhereExpressionMutator.cs`, pre-existing CS8604s), so no xunit run backs this — behavioral claims come from scratch harnesses against the built assemblies.

---

## Critical Issues (2)

### C1. `NullPropagatedOperands` recurses into `AndAlso`/`OrElse`, which do not propagate NULL — **wrong query results**
`src/EFCore.Relational/Query/SqlNullabilityProcessor.cs:626-630`

```csharp
else if (expression is SqlBinaryExpression binary)   // ← no operator filter
{
    NullPropagatedOperands(binary.Left, operands);
    NullPropagatedOperands(binary.Right, operands);
}
```

The optimization's precondition is `x IS NULL ⇒ result IS NULL`. `SqlBinaryExpression.IsValidOperator` (`src/EFCore.Relational/Query/SqlExpressions/SqlBinaryExpression.cs:93,95`) admits `AndAlso` and `OrElse`, which violate it under three-valued logic: `NULL AND FALSE = FALSE`, `NULL OR TRUE = TRUE`.

**This exact guard already exists 1,700 lines below, with a comment explaining why** — `ProcessNullNotNull` at `SqlNullabilityProcessor.cs:2314-2321`:

```csharp
case SqlBinaryExpression sqlBinaryOperand
    when sqlBinaryOperand.OperatorType != ExpressionType.AndAlso
    && sqlBinaryOperand.OperatorType != ExpressionType.OrElse:
    // ...
    // for AndAlso, OrElse we can't do this optimization
```

**Confirmed by execution** (SQLite, head vs. base, DB result vs. LINQ-to-Objects):

| Query | Row | base | head | correct |
|---|---|---|---|---|
| `x.NullableBoolA != null ? (bool?)(x.NullableBoolA.Value && x.BoolB) : null` | `A=NULL, B=false` | `NULL` | **`false`** | `NULL` |
| `x.NullableBoolA != null ? (bool?)(x.NullableBoolA.Value \|\| x.BoolB) : null` | `A=NULL, B=true` | `NULL` | **`true`** | `NULL` |
| `x.NullableIntA != null ? (bool?)(x.NullableIntA == x.NullableIntB) : null` | `A=NULL, B=NULL` | `NULL` | **`false`** | `NULL` |
| `x.NullableIntA != null ? (bool?)(x.NullableIntA != x.NullableIntB) : null` | `A=NULL, B=NULL` | `NULL` | **`true`** | `NULL` |

Rows 3–4 are the nastier variant: the user wrote a plain `==`, but EF's own null-semantics rewrite turned the result into `A = B AND B IS NOT NULL` — an `AndAlso` — *before* this code sees it. Emitted SQL at head: `SELECT "NullableIntA" = "NullableIntB" AND "NullableIntB" IS NOT NULL`. So you don't need an unusual query to hit this. `RelationalSqlTranslatingExpressionVisitor.cs:442-443` also normalizes boolean `&`/`|` into `AndAlso`/`OrElse`, widening the surface further.

### C2. Boolean-typed results lose NULL entirely on SQL Server
`src/EFCore.Relational/Query/SqlNullabilityProcessor.cs:578-588`, interacting with `src/EFCore.SqlServer/Query/Internal/SearchConditionConvertingExpressionVisitor.cs:41-51`

Even for operators that *do* propagate NULL in 3VL (the comparisons), the guarding CASE is not redundant on SQL Server. `ConvertToValue` — which runs *after* `SqlNullabilityProcessor` — materializes a search condition as a **two-valued** CASE with no NULL arm:

```csharp
? _sqlExpressionFactory.Case(
    [new CaseWhenClause(SimplifyNegatedBinary(sqlExpression), Constant(true))],
    _sqlExpressionFactory.Constant(false))   // UNKNOWN → false, never NULL
```

The outer `CASE ... ELSE NULL` was the only thing carrying UNKNOWN into the value domain. **Confirmed by generating SQL Server SQL at both commits** (`ToQueryString()`, no live server) for `g.LeaderNickname != null ? (bool?)(g.LeaderNickname.Length == 5) : null`:

```sql
-- base 051c33a79
SELECT CASE WHEN [g].[LeaderNickname] IS NOT NULL
            THEN CASE WHEN CAST(LEN([g].[LeaderNickname]) AS int) = 5
                      THEN CAST(1 AS bit) ELSE CAST(0 AS bit) END
            ELSE NULL END

-- head afcfba2e9
SELECT CASE WHEN CAST(LEN([g].[LeaderNickname]) AS int) = 5
            THEN CAST(1 AS bit) ELSE CAST(0 AS bit) END
```

The projection is `bool?`, but the head SQL has no path that yields NULL — a NULL `LeaderNickname` returns `false`. This is provider-specific (SQLite still yields NULL, which is why my SQLite harness didn't catch this one), and I confirmed it at the SQL level rather than by executing against SQL Server.

**Note on the fix:** guarding on `clause.Result.Type.UnwrapNullableType() == typeof(bool)` fixes **both** C1 and C2, since `AndAlso`/`OrElse` are always bool-typed. Excluding `AndAlso`/`OrElse` alone fixes only C1.

---

## Important Issues (4)

### I1. No test covers either unsound shape
`test/EFCore.Relational.Specification.Tests/Query/NullSemanticsQueryTestBase.cs:2250-2295`

All five new tests use `int` or `string` results (`~a`, `a+b`, string concat ×3) — every one genuinely null-propagating. Uncovered: boolean-typed results (C2), `AndAlso`/`OrElse` results (C1), the no-`ELSE` form, `Negate` (one of three whitelisted unary operators), `UseRelationalNulls: true`, and **any negative test asserting the CASE survives where it must**. Four of the five are pure-win cases where the whole CASE vanishes, so their result assertions can't distinguish a sound drop from an unsound one — the discriminating power sits in the SQL baselines, which only run on SQL Server.

The seed data itself is fine — `NullSemanticsData.cs:41-92` builds the full 3×3×3 cross product with `null` in every nullable column, so the assertions are not vacuous.

### I2. Reimplements `ProcessNullNotNull`'s propagation table, and has already drifted from it
`SqlNullabilityProcessor.cs:617-649` vs. `:2242-2430` (same class, `private`)

Lines 631-648 are near-verbatim `:2393-2408`. Three divergences already exist: the missing `AndAlso`/`OrElse` guard (C1), the missing `Instance: not null` check (I3), and the loop bound (L6). One shared helper — "given an expression, yield the children through which null propagates" — would collapse both copies.

### I3. `func.Instance!` asserts an invariant nothing enforces
`SqlNullabilityProcessor.cs:633-635`

```csharp
if (func.InstancePropagatesNullability == true)
{
    NullPropagatedOperands(func.Instance!, operands);
}
```

Verified: `SqlFunctionExpression` declares `Instance` as `SqlExpression?` (`SqlFunctionExpression.cs:258`) with no `MemberNotNullWhen` tying it to `InstancePropagatesNullability`, and the public `[EntityFrameworkInternal]` constructor (`SqlFunctionExpression.cs:191-226`) accepts `instance: null` with `instancePropagatesNullability: true` — it validates only argument counts. The sibling doing the identical check uses the safe form: `if (sqlFunctionExpression is { Instance: not null, InstancePropagatesNullability: true })` (`SqlNullabilityProcessor.cs:2394`). This is the only `InstancePropagatesNullability == true` in `src/`.

### I4. Latent: binary `Coalesce` would be mis-optimized
`SqlNullabilityProcessor.cs:626`

`SqlExpressionFactory.Coalesce` (`SqlExpressionFactory.cs:502-509`) emits a `SqlFunctionExpression` with `argumentsPropagateNullability: [false, false]`, which the function arm correctly skips — so this is safe today, and the retained `COALESCE([NullableStringC], N'')` in the `..._with_partial_checks` baseline proves it. But `ExpressionType.Coalesce` is a legal `SqlBinaryExpression` operator (`SqlBinaryExpression.cs:102`) and `MakeBinary` will construct one, so a provider or future translator silently gets `CASE WHEN x IS NOT NULL THEN COALESCE(x, 5) ELSE NULL END → COALESCE(x, 5)` → `5` where `NULL` is required. An allow-list (rather than the current blanket `else if`) also fails safe when a new operator is added to `IsValidOperator`.

---

## Suggestions (9)

- **S1** `SqlNullabilityProcessor.cs:578` — `IsNull(elseResult)` returns `false` for a C# `null` `elseResult`, i.e. a CASE with no `ELSE`. `IsNull` (`:1633`) only matches `SqlConstantExpression`/`SqlParameterExpression`. In SQL those forms are identical, and `:571-573` already treats a missing else as NULL. Missed optimization; `elseResult is null || IsNull(elseResult)`.
- **S2** `SqlNullabilityProcessor.cs:576` — the comment `// optimize expressions such as expr != null ? expr : null` describes the smallest possible instance. It omits that the result can be any null-propagating expression, and omits the *partial-pruning* outcome at `:590` entirely (a CASE that survives with a reduced test) — which is exactly what `..._with_mixed_checks` exercises. It also doesn't state the `testIsCondition` / single-when-clause preconditions.
- **S3** `SqlNullabilityProcessor.cs:595,600` — `DropNotNullChecks` returns `SqlExpression?` where `null` means "test is unconditionally true", the inverse of the usual reading. `// true` is the entire documentation and sits at one of three sites where the sentinel matters. A one-line header comment on the method would fix it. Likewise the deliberate exclusions deserve a word: only `AndAlso` is decomposed (`:602`) because `true AND x == x` but `true OR x == true`; and the unary whitelist (`:621-622`) deliberately excludes `Equal`/`NotEqual`, which are `IS [NOT] NULL`.
- **S4** `SqlNullabilityProcessor.cs:595-615` — prior art for this exact function already exists: `SelectExpression.RemoveRedundantNullChecks` + `CombineNonNullExpressions` (`src/EFCore.Relational/Query/SqlExpressions/SelectExpression.cs:3282-3310`), same `null`-means-true contract and same `AndAlso` recursion, but with the recombination extracted instead of the nested ternary at `:607-609` (the only nested ternary in this file), and with sequential guards instead of `else`-after-`return`.
- **S5** `SqlNullabilityProcessor.cs:580-583` — the `HashSet<SqlExpression>` is built unconditionally, before the test is even inspected, and `GetHashCode` is structural and recursive (`SqlBinaryExpression.cs:173`), so insertion is O(nodes × depth) on exactly the left-leaning concat chains these tests exercise. Walking the *test* (1–3 conjuncts) and asking a `PropagatesNullFrom(result, operand)` predicate is simpler and costs nothing when the test has no null checks.
- **S6** `SqlNullabilityProcessor.cs:640` — iterates `func.ArgumentsPropagateNullability.Count` while indexing `func.Arguments[i]` at `:644`. Safe (the constructor throws on mismatch at `SqlFunctionExpression.cs:217-224`) but gratuitously different from the sibling at `:2401`, which iterates `Arguments.Count`.
- **S7** `SqlNullabilityProcessor.cs:617` — `NullPropagatedOperands` is a noun phrase naming a `void` mutator; every other member in the file and every comparable collector in `src/EFCore.Relational/Query/` is verb-first (`PopulateGroupByTerms`, `PopulateInnerKeyColumns`, `ProcessNullNotNull`, and its own sibling `DropNotNullChecks`). Both helpers are also recursive ~25-line local statics where the file uses private methods for everything of that size.
- **S8** `NullSemanticsQueryTestBase.cs:2290` — `Is_not_null_optimizes_binary_op_with_mixed_checks` is the only *negative* case (its baseline at `NullSemanticsQuerySqlServerTest.cs:4548-4559` keeps the CASE), but is named as a positive. The file already has a convention for this: `..._nullability_negative` (`:2172`), `..._conditional_negative` (`:2219`). Relatedly, `..._with_nested_checks` (`:2280`) has nested *conditionals*, not nested checks, and `..._with_partial_checks` (`:2270`) has complete checks over a *partially covered result* — the names read backwards.
- **S9** `test/EFCore.Sqlite.FunctionalTests/Query/GearsOfWarQuerySqliteTest.cs:1559` — a `WHEN "g"."LeaderNickname" IS NOT NULL THEN "g"."LeaderNickname" LIKE '%us'` baseline survives. `LIKE` does propagate null, so this is a leftover opportunity (`LikeExpression` isn't in the walker); not a bug.

**Checked and clean** (so these don't get re-litigated): `Type`/`TypeMapping` are preserved by `return clause.Result`, since `CaseExpression` derives both from `whenClauses[0].Result` (`CaseExpression.cs:33`). The `nullable` out-param stays correct on every path. The `null`-means-true sentinel is threaded correctly through `:607-609`. `DropNotNullChecks`'s default arm is conservative for every node kind. Recursion is bounded. The unary whitelist is sound. Bare `TODO`s match repo convention — 161 of 226 TODOs in `src/` are unlinked, including three already in this file. GearsOfWar baseline updates are complete across all six provider files.

---

## Strengths

- `NullSemanticsQueryTestBase` is the right home — the 27-row full cross product gives null/non-null coverage for every column for free.
- The `SqlFunctionExpression` arm correctly honors `IsNullable` and per-argument `ArgumentsPropagateNullability` rather than assuming functions propagate; the retained `COALESCE([NullableStringC], N'')` in the baseline is the visible proof.
- Splitting into `cde80722d` (tests with pre-optimization baselines) then `afcfba2e9` (baseline update) makes the SQL delta reviewable as a diff instead of a wall of new strings.
- `..._with_nested_checks` is a genuinely good pick — it proves the optimization composes across nesting levels.

---

## Recommended action

1. **Block on C1 and C2** — both produce silently wrong query results, both confirmed against the base commit. A single `clause.Result` bool-type guard at `SqlNullabilityProcessor.cs:578` addresses both; an operator allow-list at `:626` addresses only C1.
2. Add the tests in I1 first — the `&&`/`||` and `bool?`-result cases fail today via plain `AssertQuery` result comparison, no SQL baseline needed.
3. Then I2 (share the table with `ProcessNullNotNull`, which is what would have prevented C1) and I3.

One housekeeping note: a `/tmp/review-base` worktree is registered against this repo that I didn't create and haven't touched. The repo working tree itself is clean and at `afcfba2e9`.
