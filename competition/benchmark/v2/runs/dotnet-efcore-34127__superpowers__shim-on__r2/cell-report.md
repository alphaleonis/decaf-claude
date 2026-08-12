I'll run the superpowers code-review skill first.
Now dispatching the reviewer subagent.
Reviewer subagent's report, verbatim:

---

## Review: null-propagation optimization in `SqlNullabilityProcessor`

### Strengths

- **The core idea is right and the shape-matching is tight.** Gating on `testIsCondition && whenClauses is [var clause] && IsNull(elseResult)` (`SqlNullabilityProcessor.cs:578`) correctly restricts the rewrite to the exact `CASE WHEN <test> THEN <r> ELSE NULL END` form where dropping an implied `IS NOT NULL` is meaningful.
- **`DropNotNullChecks` (595-615) is correct.** It only descends through `AndAlso` — never `OrElse` — which is the right conservative choice, and the `left is null ? right : right is null ? left : Update(...)` fold correctly models "this conjunct is now `TRUE`". Returning `clause.Result` when the whole test collapses is type-safe: `CaseExpression`'s constructor derives `Type`/`TypeMapping` from `whenClauses[0].Result` (`CaseExpression.cs:33,48`), so no type mapping is lost.
- **The unary whitelist (621-622) is genuinely correct.** `Not`/`Negate`/`Convert` all propagate NULL, and critically `ExpressionType.Equal`/`NotEqual` (i.e. `IS NULL` / `IS NOT NULL`) are excluded, so `CASE WHEN a IS NOT NULL THEN a IS NULL ELSE NULL END` is left alone.
- **The `SqlFunctionExpression` handling (631-647) is exactly right**, including the `IsNiladic` guard before touching `ArgumentsPropagateNullability`. I verified this catches `COALESCE`, which `SqlExpressionFactory.Coalesce` emits with `argumentsPropagateNullability: [false, false]` — I ran `x.NullableIntA != null ? (int?)(x.NullableIntA ?? 7) : null` and the CASE is correctly *not* removed.
- **The baseline updates are all sound.** I read every changed baseline in GearsOfWar (SqlServer/TPC/TPT/Temporal) and Sqlite; each is `length(col)`, `col`, or `col || col` under an `IS NOT NULL` test — all genuinely null-propagating, all correct simplifications.

### Issues

#### Critical (Must Fix)

**1. `NullPropagatedOperands` treats *every* `SqlBinaryExpression` operator as null-propagating — including `AndAlso`, `OrElse`, and `Coalesce`. This produces wrong query results.**

`src/EFCore.Relational/Query/SqlNullabilityProcessor.cs:626-630`

```csharp
else if (expression is SqlBinaryExpression binary)
{
    NullPropagatedOperands(binary.Left, operands);
    NullPropagatedOperands(binary.Right, operands);
}
```

`SqlBinaryExpression.IsValidOperator` (`SqlBinaryExpression.cs:83-105`) admits `AndAlso`, `OrElse`, and `Coalesce`. None of those propagate NULL from an operand: `NULL AND FALSE` = `FALSE`, `NULL OR TRUE` = `TRUE`, `COALESCE(NULL, 0)` = `0`. So the set of "operands whose nullness forces the result to NULL" is over-approximated, and the `IS NOT NULL` guard that was protecting correctness gets dropped.

This is not theoretical. I built the head and base commits and ran both against SQLite (repro project outside this checkout; both worktrees removed afterward).

*Failure case A — projection returns `false` instead of `null`:*

```csharp
ss.Set<E>().Select(x => x.NullableBoolA != null ? (bool?)(x.NullableBoolA == x.NullableBoolB) : null)
```

The null-semantics rewrite turns the result into `A = B AND B IS NOT NULL` (an `AndAlso`), the traversal collects `A` from it, the test `A IS NOT NULL` is dropped, and the whole CASE disappears:

| | base `051c33a79` | head `afcfba2e9` |
|---|---|---|
| SQL | `CASE WHEN A IS NOT NULL THEN A = B AND B IS NOT NULL ELSE NULL END` | `A = B AND B IS NOT NULL` |
| row `A=NULL, B=NULL` | `NULL` (correct) | **`False`** |

*Failure case B — `OrElse`, and it changes row counts, not just projected values:*

```csharp
ss.Set<E>().Where(x => (x.NullableIntA != null ? (bool?)(x.NullableIntA > 1 || x.IntB > 1) : null) == true)
```

| | base | head |
|---|---|---|
| SQL predicate | `CASE WHEN NullableIntA IS NOT NULL THEN NullableIntA > 1 OR IntB > 1 ELSE NULL END = 1` | `NullableIntA > 1 OR IntB > 1` |
| ids returned (9-row table) | `1,2,3,4,5,6` (matches LINQ-to-Objects) | **`1,2,3,4,5,6,7,8,9`** |

The same failure reproduces with both operands nullable (`x.NullableIntA > 1 || x.NullableIntB > 1`). `Coalesce` as a `SqlBinaryExpression` is the third hole — currently unreachable in practice because `SqlExpressionFactory.Coalesce` returns a `SqlFunctionExpression`, but it is a valid operator any provider or future rewrite can produce, so it should be excluded explicitly rather than left as a latent trap.

**Fix:** replace the blanket `SqlBinaryExpression` arm with an operator whitelist. A whitelist (not a blacklist) is the safer shape here since `IsValidOperator` can grow:

```csharp
else if (expression is SqlBinaryExpression
    {
        OperatorType: ExpressionType.Add or ExpressionType.Subtract or ExpressionType.Multiply
            or ExpressionType.Divide or ExpressionType.Modulo
            or ExpressionType.And or ExpressionType.Or or ExpressionType.ExclusiveOr
            or ExpressionType.Equal or ExpressionType.NotEqual
            or ExpressionType.LessThan or ExpressionType.LessThanOrEqual
            or ExpressionType.GreaterThan or ExpressionType.GreaterThanOrEqual
    } binary)
```

Note that gating the whole optimization on `resultNullable` instead would *not* be a sufficient fix: failure case B's result is still reported nullable, and the drop is still unsound. The operator set is the actual defect.

#### Important (Should Fix)

**2. The new tests never exercise a boolean/logical result expression — precisely the gap the bug lives in.**

`test/EFCore.Relational.Specification.Tests/Query/NullSemanticsQueryTestBase.cs:2250-2291`

The five added tests cover a unary op (`~`), integer `+`, string `+` chains, nesting, and a mixed test with a non-droppable conjunct. Every one has a *scalar* result. There is no case where the CASE result is a boolean expression, which is the only shape where `AndAlso`/`OrElse` can appear in the result — so the suite is structurally blind to issue #1. This matters because CI passing here was the main evidence the change is safe.

Add coverage alongside the existing five, e.g.:

```csharp
public virtual Task Is_not_null_does_not_optimize_orelse_result(bool async)
    => AssertQuery(async, ss => ss.Set<NullSemanticsEntity1>().Select(
        x => x.NullableBoolA != null ? (bool?)(x.NullableBoolA == x.NullableBoolB) : null));
```

and a `Where`-context variant, since the filtering case is the one that silently changes result-set cardinality. `AssertQuery` compares against LINQ-to-Objects, so both fail today.

**3. There is no negative test asserting the optimization *doesn't* fire.**

Related to #2 but distinct: `Is_not_null_optimizes_binary_op_with_mixed_checks` is the only test that asserts a CASE survives, and it survives because of an unrelated conjunct (`BoolA = 1`), not because the null-propagation analysis declined. Nothing pins the boundary of what `NullPropagatedOperands` considers propagating. A `COALESCE`-result test (`x.NullableIntA != null ? (int?)(x.NullableIntA ?? 7) : null`) would lock in the correct behavior I verified by hand and is a one-liner.

#### Minor (Nice to Have)

**4. `CASE WHEN … THEN … END` with no `ELSE` is missed.** `IsNull(elseResult)` at line 578 returns `false` when `elseResult` is C# `null` (`IsNull` at 1633-1635 only matches a null constant or null-valued parameter). A CASE with no ELSE is semantically identical to `ELSE NULL`, so this shape is silently skipped. Cheap to widen to `(elseResult is null || IsNull(elseResult))`.

**5. Missed propagating node types.** `LikeExpression`, `CollateExpression`, `AtTimeZoneExpression`, and `JsonScalarExpression` all propagate NULL but aren't traversed. Conservative and safe — just noting the analysis is narrower than the doc comment's framing implies. Not worth expanding until there's a query that wants it.

**6. `// TODO: optimize expr == null ? null : expr` at line 577** — the mirror case is left unimplemented with no issue link. Fine as a marker, but the asymmetry means `x.Foo == null ? null : x.Foo + x.Bar` gets no benefit while `x.Foo != null ? x.Foo + x.Bar : null` does, which will read as a puzzling inconsistency to users comparing generated SQL.

**7. `[Unverified] String `+` and `CONCAT_NULL_YIELDS_NULL`.** `Is_not_null_optimizes_binary_op_with_partial_checks` depends on `A + B` yielding NULL when `A` is NULL. Under the deprecated `SET CONCAT_NULL_YIELDS_NULL OFF` on SQL Server that is false. EF appears to assume the default (ON) elsewhere, so this is consistent with existing behavior rather than a new problem — flagging only so it's a conscious assumption.

### Recommendations

- Add a short comment above `NullPropagatedOperands` stating the invariant it must maintain ("membership means: if this operand is NULL, the whole expression is NULL"). The bug is precisely an unstated invariant being violated by a wildcard pattern match; naming it makes future operator additions self-checking.
- Consider asserting the invariant in debug builds, or at minimum keep the operator lists as explicit whitelists in both the unary and binary arms so the two read symmetrically. Today the unary arm is a whitelist and the binary arm is a wildcard — that asymmetry is exactly where the defect landed.
- Worth a targeted run of the full `NullSemanticsQuery*` and `GearsOfWarQuery*` suites after the fix, since the baselines were regenerated wholesale; some of the removed CASEs may need to come back.

### Assessment

**Ready to merge?** No.

**Reasoning:** The optimization silently drops `IS NOT NULL` guards whose result expression contains `AndAlso`/`OrElse`, producing wrong values in projections and wrong row sets in `Where` clauses — I reproduced both against SQLite and confirmed the base commit is correct on the same data, so this is a regression introduced by this change, not a pre-existing issue. The fix is small (an operator whitelist at line 626), but it must land with tests covering a boolean result expression, since the current suite cannot detect the failure.

