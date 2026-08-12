I'll start by invoking the requested skill.
I'll run this review locally. Let me start with pre-flight.
Local mode confirmed (no remote). Let me examine the diff.
Confirmed a key fact: `SqlBinaryExpression` permits `AndAlso`, `OrElse`, and `Coalesce`. Let me dispatch the review roster while I build a concrete repro.
Build succeeds. Let me verify my hypothesis with a standalone repro outside the repo (no repo modifications).
Confirmed a wrong-results bug. Let me broaden the repro to map the full blast radius.
My client-side baseline was silently running on the server (`AsEnumerable().AsQueryable()` is a no-op on an `IQueryable`). Fixing that — materializing to a real list first.
Now let me confirm these are regressions introduced by this change by building the base commit in an isolated export.
Base commit: all 8 cases match. Head: 5 mismatches. Confirmed regression. Let me pin down the exact mechanism.
Verification is solid. Let me check the seed-data/test-coverage angle while agents finish.
The blind reviewer independently found the same Critical bug and points to an existing guard in the same file. Let me verify that corroboration.
Two agents converged on what I proved empirically. Let me verify the secondary claims before including them.
Let me run the existing NullSemantics suite on HEAD to confirm the regression escapes the current tests.
The repo's test projects don't compile under the installed SDK (pre-existing, unrelated to this diff), so my standalone before/after harness is the authoritative evidence. Let me check remaining agents.
The edge-case hunter raises a distinct SQL-Server-specific mechanism. Let me verify it by generating SQL Server SQL (no server needed) on both commits.
This confirms a **second, distinct** mechanism — and it fires on a plain equality comparison. Let me scope which providers are affected.
All four agents in; both mechanisms empirically confirmed. Let me check whether any existing test already covers the second shape, then clean up.
Repo is untouched (0 tracked files modified). Here is the review.

---

# Comprehensive Review — `051c33a79..afcfba2e9`

**Mode:** local (no git remote — provider operations unavailable, nothing posted).
**Scope:** 8 files, +202/−100. 1 production file (`SqlNullabilityProcessor.cs`, +73), 1 spec-test file, 6 SQL-baseline files.
**Agents:** architecture-reviewer, edge-case-hunter, blind-hunter, pr-test-analyzer (all 4 completed).

## Summary

The change adds an optimization to `VisitCase` that elides `CASE WHEN expr IS NOT NULL THEN result ELSE NULL END` when `result` already propagates NULL from `expr`. The idea is sound and the baseline updates in the diff are all correct.

But `NullPropagatedOperands` decides "propagates NULL" for `SqlBinaryExpression` by recursing into **both operands of every operator, with no `OperatorType` filter**. That is wrong for two separate reasons, and both produce **silently incorrect query results**. I verified this by building `HEAD` and the base commit side by side and running the same queries against both.

**Overall risk: Critical.** All four agents independently flagged the binary recursion.

---

## Critical

### C1 — `AndAlso`/`OrElse` are not null-propagating; their operands are harvested anyway
`src/EFCore.Relational/Query/SqlNullabilityProcessor.cs:626-630`

```csharp
else if (expression is SqlBinaryExpression binary)   // no OperatorType filter
{
    NullPropagatedOperands(binary.Left, operands);
    NullPropagatedOperands(binary.Right, operands);
}
```

`SqlBinaryExpression.IsValidOperator` (`SqlBinaryExpression.cs:93,95,102`) admits `AndAlso`, `OrElse`, and `Coalesce`. Under SQL three-valued logic `NULL AND FALSE = FALSE` and `NULL OR TRUE = TRUE` — the optimization's invariant ("operand IS NULL ⟹ result IS NULL") does not hold, so a load-bearing `IS NOT NULL` check gets dropped.

**This file already documents the rule at line 2313-2321** and excludes exactly these two operators:
```csharp
case SqlBinaryExpression sqlBinaryOperand
    when sqlBinaryOperand.OperatorType != ExpressionType.AndAlso
    && sqlBinaryOperand.OperatorType != ExpressionType.OrElse:
    // for AndAlso, OrElse we can't do this optimization
```

**Verified by execution** (SQLite, real data, base vs. HEAD). Base: all 8 cases correct. HEAD: 5 wrong.

| Query | Row | Correct (LINQ) | HEAD returns |
|---|---|---|---|
| `A != null ? (bool?)(A.Value \|\| BoolA) : null` | `A=NULL, BoolA=true` | `null` | `true` |
| `A != null ? (bool?)(A.Value && BoolA) : null` | `A=NULL, BoolA=false` | `null` | `false` |
| `A != null ? (bool?)(A == B) : null` | `A=NULL, B=NULL` | `null` | `false` |
| `A != null ? (bool?)(A != B) : null` | `A=NULL, B=NULL` | `null` | `true` |

The equality/inequality rows matter most: EF's own null-semantics expansion turns `A == B` into `A = B AND B IS NOT NULL`, so **ordinary comparisons between two nullable columns hit this path**. It also corrupts filtering — `Where(x => (x.NullableBoolA != null ? (bool?)(x.NullableBoolA.Value || x.BoolA) : null) == true)` returned **2 rows on HEAD vs. 1 on base**, silently leaking a row that should have been excluded.

**Fix:** filter the recursion, mirroring line 2313:
```csharp
else if (expression is SqlBinaryExpression
         { OperatorType: not (ExpressionType.AndAlso or ExpressionType.OrElse or ExpressionType.Coalesce) } binary)
```
Better still, extract one shared operator predicate so this rule and the one at line 2313 cannot drift apart again.

*(`Coalesce` is defensive only: `SqlExpressionFactory.Coalesce` at line 502-508 emits a `SqlFunctionExpression` with `argumentsPropagateNullability: [false, false]`, which the function branch handles correctly. But binary `Coalesce` is a legal node a provider could construct.)*

---

### C2 — Comparison results are search conditions: `UNKNOWN` becomes `false`, not `NULL`
`src/EFCore.Relational/Query/SqlNullabilityProcessor.cs:626-630` (comparisons) and `:621-623` (boolean `Not`)

**This survives a fix for C1** and needs its own guard.

For `Equal`/`NotEqual`/`LessThan`/… a NULL operand yields `UNKNOWN`, not a NULL *value*. That distinction is invisible while the condition sits inside `CASE WHEN … THEN <cond> ELSE NULL END`. Once the guard is dropped, SQL Server's `SearchConditionConvertingExpressionVisitor` re-wraps the bare condition as a value with **no `ELSE NULL` arm**, so `UNKNOWN` collapses to `0`.

Generated SQL for `Select(x => x.NullableIntA != null ? (bool?)(x.NullableIntA == 1) : null)`:

```sql
-- BASE                                    -- HEAD
SELECT CASE                                SELECT CASE
    WHEN [e].[NullableIntA] IS NOT NULL        WHEN [e].[NullableIntA] = 1
    THEN CASE                                  THEN CAST(1 AS bit)
        WHEN [e].[NullableIntA] = 1            ELSE CAST(0 AS bit)
        THEN CAST(1 AS bit)                END
        ELSE CAST(0 AS bit)                FROM [Entities1] AS [e]
    END
    ELSE NULL
END
```

With `NullableIntA IS NULL`: base yields `NULL`; HEAD yields `0` (`false`). C# yields `null`. Same for the string variant (`== N'Marcus'`).

Note this needs **no logical connective at all** — a plain equality against a constant is enough.

**Provider scope, checked both ways:** SQLite is unaffected for this shape (it has no `bit` type; `SELECT A = 1` returns `NULL` directly — I ran it, it matches). SQL Server and any provider routing conditions through a search-condition converter are affected. I confirmed the SQL shape on both commits; I did not execute against a live SQL Server (none available here), but `CASE WHEN <unknown> THEN 1 ELSE 0 END = 0` is plain ANSI semantics, not an inference.

**Fix:** bail out when `clause.Result` is a search condition (`Type` is `bool`/`bool?`), or exclude comparison operators and boolean `Not` from `NullPropagatedOperands`. The value-typed cases this change targets (arithmetic, `~`, string concat, `LEN`) are untouched by that restriction.

---

## High

### H3 — No test covers a boolean or comparison result, which is exactly the unsound path
`test/EFCore.Relational.Specification.Tests/Query/NullSemanticsQueryTestBase.cs:2250-2294`

All five new tests use `~A` (bitwise `Not`), int `Add`, or string concat. Every one is a shape where dropping the check is *correct*. Nothing places a logical connective or a comparison in the **result** — `Is_not_null_optimizes_binary_op_with_mixed_checks` (2290) puts `x.BoolA` in the *test*, never the result. **The suite passes identically with or without a fix for C1/C2.**

The infrastructure is otherwise good: `AssertQuery` compares against in-memory LINQ, and `NullSemanticsData` seeds the full 3×3×3 `{false,true,null}` cross-product, so the discriminating rows already exist. Add:
```csharp
x => x.NullableIntA != null ? (bool?)(x.NullableIntA > 5 || x.BoolA) : null   // C1
x => x.NullableIntA != null ? (bool?)(x.NullableIntA == x.NullableIntB) : null // C1
x => x.NullableIntA != null ? (bool?)(x.NullableIntA == 1) : null              // C2
```

Also uncovered: `Negate`; `Subtract`/`Multiply`/`Divide`/`Modulo`/`And`/`Or`/`ExclusiveOr`; the `ArgumentsPropagateNullability[i] == false` guard (line 642); `InstancePropagatesNullability` (633-636); `DropNotNullChecks`' right-dropped arm (608) and `binary.Update` arm (609); and an `OrElse` test-position case. Notably, the only existing guard that the optimization *doesn't* over-fire lives in an unrelated suite (`GearsOfWarQuerySqlServerTest.cs:3654`) — worth mirroring into `NullSemanticsQueryTestBase`.

---

## Medium

### M4 — The result was simplified under the very assumption being dropped
`src/EFCore.Relational/Query/SqlNullabilityProcessor.cs:576-590`

`clause.Result` is visited with `preserveColumnNullabilityInformation: true` (line 511-518), so the test's columns are in `_nonNullableColumns` while the result is being rewritten. Directly observable: on base, `A == B` inside the guard emits `A = B AND B IS NOT NULL` — the `A IS NOT NULL` conjunct is *missing because it was assumed*. Hoisting that expression out of the guard is what makes C1 unsound rather than merely over-eager.

Fixing C1/C2 makes this latent rather than live (value-typed results survive the hoist — the elided `COALESCE` in string concat is benign because `+` propagates NULL anyway). But it is the invariant a fix must preserve, and it is written down nowhere. Document on the helper that the set is a **must**-propagate set ("the expression is NULL whenever any member is NULL"), not a may-propagate set, and that search conditions never belong in it.

### M5 — No provider extension point for the new null-propagation model
`src/EFCore.Relational/Query/SqlNullabilityProcessor.cs:595,617`

Both helpers are `static` local functions inside `VisitCase`. Every other nullability decision in this class is `protected virtual`, and providers already use that seam — `SqlServerSqlNullabilityProcessor.VisitCustomSqlExpression:37` and `SqliteSqlNullabilityProcessor:36` both handle custom node types that propagate NULL from their operands and are invisible to this model. A provider wanting to participate must fork all of `VisitCase`. Base-class types the class already visits are missing too (`VisitAtTimeZone:479`, `VisitCollate:659`, `VisitDistinct:689`, `VisitJsonScalar:1615`) — missed optimizations only, but the drift is structural. Promote to `protected virtual void CollectNullPropagatedOperands(...)` with a `base` fall-through.

### M6 — Operand set is built before it can possibly be useful
`src/EFCore.Relational/Query/SqlNullabilityProcessor.cs:579-582`

The full result subtree is walked into a `HashSet<SqlExpression>` (structural `Equals`/`GetHashCode` per node) *before* `DropNotNullChecks` establishes that `clause.Test` contains even one `IS NOT NULL`. `VisitCase` recurses across the whole SQL tree, so this repeats per nested `CASE` and is pure waste whenever the test is an unrelated predicate. Scan the test first and bail early.

---

## Low

- **`src/EFCore.Relational/Query/SqlNullabilityProcessor.cs:633-636`** — `NullPropagatedOperands(func.Instance!, operands)` guards only on `InstancePropagatesNullability == true`. The sibling at line 2393 guards both: `is { Instance: not null, InstancePropagatesNullability: true }`. The `[EntityFrameworkInternal]` constructor (`SqlFunctionExpression.cs:191-224`) accepts `instance: null` with `instancePropagatesNullability: true` and validates only argument counts, so the `!` asserts an invariant nothing enforces. Defensive — I could not reach it from EF's own translations. *(The adjacent `Arguments`/`ArgumentsPropagateNullability` index pairing is fine: the constructor throws `InconsistentNumberOfArguments` at line 217.)*
- **`:595-615`** — `DropNotNullChecks` returns `null` to mean the boolean constant **true**, signalled only by a trailing `// true` on line 600. Three lines above, `SqlExpression? elseResult` uses `null` to mean *absent*. Both the call site (`if (test is null) return clause.Result;`) and the conjunction folding at 607-609 depend on the true-reading. Consider `TryDropNotNullChecks(... out SqlExpression? remainingTest)`.
- **`:578`** — `IsNull(elseResult)` is `false` when there is no `ELSE` at all (`IsNull` at 1633 returns `false` for `null`), so `CASE WHEN t THEN r END` is never optimized even though SQL treats a missing `ELSE` as `NULL`. Missed optimization, not a defect.
- **`:617`** — `NullPropagatedOperands` is a noun phrase on a `void` method that accumulates into its second argument; its sibling `DropNotNullChecks` is a verb phrase. `CollectNullPropagatedOperands` would read correctly at the call site.
- **`:577`** — `// TODO: optimize expr == null ? null : expr` carries no issue reference, so a reader can't tell whether the symmetric (and arguably more common) form is deferred or deliberately out of scope.

---

## What's correct

- Every one of the 22 updated SQL baselines is semantically sound — `LEN`/`CAST`, string concat, and bare column projections all genuinely propagate NULL. The bug lives entirely in untested territory.
- Baselines were regenerated across all five affected suites (SqlServer TPH/TPT/TPC/temporal + SQLite) — the right blast-radius check.
- The `SqlFunctionExpression` arm is the well-built part: gating on `IsNullable: true`, honoring `IsNiladic`, and respecting per-argument `ArgumentsPropagateNullability` is what correctly stops the walk at `COALESCE(x, '')`.
- `DropNotNullChecks` fails safe: unrecognized test shapes (`OrElse`, `IS NULL`, non-conjunctive) fall to the `else` and are returned unchanged. Partial conjunction collapse is handled correctly rather than all-or-nothing.
- Unrecognized node types contribute nothing — the default for *unknown* nodes is safe. The problem is `SqlBinaryExpression`, which is recognized and fails **open**.

## Recommended actions

1. Gate the binary recursion on `OperatorType`, excluding `AndAlso`/`OrElse`/`Coalesce` (**C1**).
2. Skip the optimization when the result is a search condition (**C2**) — this is not fixed by (1).
3. Add regression tests for both shapes before merging (**H3**); the fixture data already discriminates.
4. Document the must-propagate invariant, and consider promoting the model to `protected virtual` (**M4/M5**).

## Verification notes

- Both mismatch sets were produced by building `HEAD` and `051c33a79` into separate output trees and running identical queries through each — base clean, HEAD wrong. C1 was confirmed end-to-end against SQLite with real rows; C2 was confirmed by diffing generated SQL Server SQL between the two commits.
- The repository's test projects **do not compile** under the installed SDK (10.0.203) — pre-existing errors in `test/EFCore.Specification.Tests/CustomConvertersTestBase.cs:1202` and `TestUtilities/QueryTestGeneration/`, unrelated to this diff — so I could not run the repo's own suite and used a standalone harness instead.
- Nothing in the repository was modified (`git status`: 0 tracked files changed); all scratch artifacts were built outside the repo and removed.

