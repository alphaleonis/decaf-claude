I'll run the comprehensive-review skill as requested.
I'll start by gathering the pre-flight context for this local review.
No git remote — provider operations are unavailable as noted; proceeding locally. Let me gather the diff and project context.
Confirmed the expression taxonomy. Now launching the review agents in parallel while I continue verifying independently.
Summarizer done. Continuing my own verification while the rest run.
Test project won't build against the installed SDK (pre-existing env mismatch). Let me try a standalone harness instead.
Source builds cleanly. Let me build a standalone harness in /tmp to empirically test my main hypothesis.
Three agents independently converged on the same core defect. Let me settle reachability empirically.
Empirically confirmed — real wrong rows. Now verifying this is a regression introduced by this change, not pre-existing.
Definitive regression. Let me pin down exactly which operator classes are affected.
Precise result: `AndAlso`/`OrElse` are broken; `Coalesce`, `Convert`, and comparisons are safe. Cleaning up.
Repo clean, worktree removed. Waiting on the remaining three agents.
CLR-type concern refuted. Checking remaining agents.
The canonical helper in the same file already excludes these operators explicitly — decisive evidence.
All predicted repros confirmed. Waiting on the final two agents.
Adversarial agent surfaced a pre-existing bug at line 539. Let me verify it and the `Coalesce` reachability claim.
Waiting on the last agent (code-reviewer) before consolidating.
I have enough convergence to report; I'll note the last agent is still running. Let me stop the monitor and clean up.
# Comprehensive Review — `051c33a79..afcfba2e9`

Provider operations unavailable (no git remote); ran fully local, posted nothing, modified nothing. Repo is clean, temporary worktree removed.

## Summary

Adds a peephole optimization to `VisitCase` in `SqlNullabilityProcessor` that rewrites `CASE WHEN <test> THEN <result> ELSE NULL END` by dropping `X IS NOT NULL` conjuncts from `<test>` when `X` is a sub-expression of `<result>` that propagates nullability. If the test collapses entirely, the CASE is replaced by `<result>`.

| File | Change |
|---|---|
| `src/EFCore.Relational/Query/SqlNullabilityProcessor.cs` | +73 — the optimization plus two static local helpers |
| `test/EFCore.Relational.Specification.Tests/Query/NullSemanticsQueryTestBase.cs` | 5 new `AssertQuery` tests |
| `test/EFCore.SqlServer.FunctionalTests/Query/NullSemanticsQuerySqlServerTest.cs` | 5 new SQL baselines |
| 5 × GearsOfWar baselines (SqlServer/TPC/TPT/Temporal/Sqlite) | baseline churn only |

**Overall risk: Critical.** One confirmed wrong-results regression, reproduced by execution.

---

## Critical

### 1. `NullPropagatedOperands` treats `AndAlso`/`OrElse` operands as null-propagating — silently wrong query results
`src/EFCore.Relational/Query/SqlNullabilityProcessor.cs:626-630`

```csharp
else if (expression is SqlBinaryExpression binary)
{
    NullPropagatedOperands(binary.Left, operands);
    NullPropagatedOperands(binary.Right, operands);
}
```

The unary arm at `:621-622` is carefully allow-listed to `Not`/`Negate`/`Convert`. The binary arm has no operator filter, but `SqlBinaryExpression.IsValidOperator` (`src/EFCore.Relational/Query/SqlExpressions/SqlBinaryExpression.cs:93,95`) admits `AndAlso` and `OrElse`, for which the optimization's premise (`X IS NULL ⇒ result IS NULL`) is false: `NULL AND FALSE = FALSE`, `NULL OR TRUE = TRUE`. `DropNotNullChecks` then deletes a load-bearing guard and the CASE collapses to an expression that can no longer yield NULL at all.

**Decisive in-repo evidence:** the file's own canonical helper `ProcessNullNotNull` performs the same reasoning at `:2312-2321` and explicitly excludes these operators:

```csharp
case SqlBinaryExpression sqlBinaryOperand
    when sqlBinaryOperand.OperatorType != ExpressionType.AndAlso
    && sqlBinaryOperand.OperatorType != ExpressionType.OrElse:
    // binaryOp(a, b) == null -> a == null || b == null
    // for AndAlso, OrElse we can't do this optimization
```

**Verified by execution.** I built the tree at both commits and ran identical queries against SQLite (`NullSemanticsQuerySqliteTest` inherits the same base class, so these shapes would run there):

| Query (projection) | Generated SQL at HEAD | Result |
|---|---|---|
| `A != null ? (A == C) : null` | `A = C AND C IS NOT NULL` | **2/18 rows wrong** (A=NULL,C=NULL → `False`, expected `NULL`) |
| `A != null ? (A.Value && BoolA) : null` | `A AND BoolA` | **3/18 wrong** (A=NULL,BoolA=false → `False`) |
| `A != null ? (A.Value \|\| BoolA) : null` | `A OR BoolA` | **3/18 wrong** (A=NULL,BoolA=true → `True`) |
| `A != null && C != null ? (A.Value \|\| C.Value) : null` | `A OR C` | **4/18 wrong** |
| `A != null ? (A \| C) : null` | `A OR C` | **2/18 wrong** |
| `A != null ? !(A.Value && BoolA) : null` | `NOT(A) OR NOT(BoolA)` | **3/18 wrong** |

All six produce correct results at base `051c33a79` (SQL retains the `CASE`), so this is a regression introduced by this change. The first row is the most alarming: `A == C` is rewritten by `RewriteNullSemantics` (`:1881-1890`) into an `AndAlso`/`OrElse` tree whose `nullable` is `false` — so an ordinary equality inside a null-guarded ternary silently loses its `NULL` result.

Verified **not** affected: arithmetic `+`, comparisons (`>`), `Convert`/cast, `??` (see below), and CLR-type preservation on the early `return clause.Result` path.

**Fix:** mirror the unary allow-list, e.g.
```csharp
else if (expression is SqlBinaryExpression binary
    && binary.OperatorType is not (ExpressionType.AndAlso or ExpressionType.OrElse or ExpressionType.Coalesce))
```
`Coalesce` belongs in the exclusion for defense in depth: `SqlExpressionFactory.Coalesce` emits a `SqlFunctionExpression` with `argumentsPropagateNullability: [false, false]` (`SqlExpressionFactory.cs:502-509`), so the `??` path is safe today — I confirmed the optimization correctly does not fire for `IntA != null ? (IntA ?? 0) : null`. But `MakeBinary` (`SqlExpressionFactory.cs:394-421`) accepts `ExpressionType.Coalesce` and constructs a raw `SqlBinaryExpression` without routing to that helper, so a provider or custom translator can reach the unsound path.

---

## High

### 2. No test covers any logical-operator result — the entire vulnerable class is untested
`test/EFCore.Relational.Specification.Tests/Query/NullSemanticsQueryTestBase.cs:2250-2293`

The five new tests use only `~` (Not) and `+` (Add/concat). No test has `clause.Result` be `&&`, `||`, `??`, or an equality that expands via null semantics. I grepped the existing suite: the nearest existing tests, `Select_null_propagation_negative6/7` (`test/EFCore.Specification.Tests/Query/GearsOfWarQueryTestBase.cs:990-1003`), collapse to constants and so do not exercise this path either. That is why only 6 baseline files needed updating and why nothing turned red.

### 3. No negative test — nothing asserts the guard is *retained* when it must be
All five new tests are "the optimization fires" tests. `Is_not_null_optimizes_binary_op_with_mixed_checks` (`:2288`) keeps a CASE only because of a leftover unrelated conjunct, not because a guard was correctly refused. Four of the five assert fully-collapsed SQL, so a future widening (invited by the `// TODO` at `:577`) would produce no baseline churn in these tests at all — removing the very signal that catches this class of bug.

### 4. `SqlFunctionExpression` propagation flags are promoted to a correctness contract, untested
`src/EFCore.Relational/Query/SqlNullabilityProcessor.cs:631-646`

A provider or `HasTranslation` that mis-declares `ArgumentsPropagateNullability` previously produced a suboptimal expansion; it now produces wrong rows. Dropping the guard also hoists the function call out of the CASE, so it is evaluated with NULL arguments on rows where it previously was not — relevant for scalar UDFs that throw on NULL. No new test uses a function result; coverage is incidental (`LEN`/`length` in the GearsOfWar baselines).

---

## Medium

### 5. Duplicated null-propagation logic that diverges from the canonical helper
`src/EFCore.Relational/Query/SqlNullabilityProcessor.cs:631-646` vs `:2393-2408`

The new function arm re-implements the traversal already in `ProcessNullNotNull`, with two divergences beyond the Critical one:
- `:634` uses `if (func.InstancePropagatesNullability == true)` then dereferences `func.Instance!`; the sibling at `:2394` guards with `is { Instance: not null, InstancePropagatesNullability: true }`. The `[EntityFrameworkInternal]` constructor (`SqlFunctionExpression.cs:192-211`) does not enforce the pairing.
- `:640` bounds the loop by `ArgumentsPropagateNullability.Count`; the sibling at `:2402` uses `Arguments.Count`. Equivalent in practice (the constructor throws `InconsistentNumberOfArguments` at `SqlFunctionExpression.cs:216-226`), but the convention divergence is gratuitous.

Extracting one shared helper would have prevented finding #1 entirely.

### 6. The soundness precondition is nowhere documented
`src/EFCore.Relational/Query/SqlNullabilityProcessor.cs:576`

`// optimize expressions such as expr != null ? expr : null` understates the transform — it handles multi-conjunct tests, partial conjunct removal, and transitive descent through unary/binary/function trees. The load-bearing invariant ("every node kind descended into must return NULL when the descended-into operand is NULL") is unstated, which is precisely why the binary arm's missing filter reads as an oversight rather than a decision.

### 7. `null`-means-`true` sentinel is under-documented
`src/EFCore.Relational/Query/SqlNullabilityProcessor.cs:600` (`return null; // true`), consumed at `:585` and `:607-609`. A `SqlExpression?` returning `null` reads as "could not process". If anyone later adds a bail-out returning `null`, the whole `WHEN` test is silently deleted and every row takes the THEN branch — a wrong-results bug with no compiler signal. A one-line contract comment on `DropNotNullChecks` covers both consumers.

### 8. No opt-out and no diagnostic
The helpers are `static` **local** functions inside `VisitCase`, outside the `protected virtual` surface that `SqlNullabilityProcessor` otherwise exposes (34 members, subclassed by `SqlServerSqlNullabilityProcessor`). A provider hitting finding #1 can only override the whole ~90-line `VisitCase` or set `UseRelationalNulls` (far broader). Nothing signals that the rewrite fired — the CASE is simply absent.

---

## Low

### 9. Missed optimization for the no-`ELSE` form
`src/EFCore.Relational/Query/SqlNullabilityProcessor.cs:578`. `IsNull` (`:1633`) returns `false` for a C# `null` `elseResult`, so `CASE WHEN t THEN r END` is skipped while the identical `... ELSE NULL END` is folded — even though `:571` (`elseResult ?? Constant(null, …)`) and `:561` already encode the equivalence. Fix: `(elseResult is null || IsNull(elseResult))`. Missed optimization only, not a correctness issue.

### 10. Pre-existing wrong restore-count argument in the modified method
`src/EFCore.Relational/Query/SqlNullabilityProcessor.cs:539`: `RestoreNullValueColumnsList(currentNonNullableColumnsCount);` passes the non-nullable count to the null-value restore. `:529` and `:566` both correctly pass `currentNullValueColumnsCount`. **Confirmed present at base `051c33a79` — not introduced here**, but it corrupts the `_nullValueColumns` state feeding the result-visiting this change now depends on. Worth a separate fix.

### 11. O(n²) hashing when building `nullPropagatedOperands`
`src/EFCore.Relational/Query/SqlNullabilityProcessor.cs:580`. Every node of the result subtree is inserted into a `HashSet<SqlExpression>`, and `GetHashCode` is recursive and uncached (`SqlBinaryExpression.cs:172-173`). Per-translation cost only (translations are cached), gated behind a cheap `IsNull` check. Track, don't block.

---

## Claims I checked and refuted

These were raised by review agents; I verified each against the code or by execution and they do not hold:

- **`??` / `Coalesce` is broken in practice** — no. `IntA != null ? (IntA ?? 0) : null` correctly keeps its `CASE`, because the factory emits a `SqlFunctionExpression` with `[false, false]`. Only reachable via `MakeBinary`.
- **Index mismatch between `ArgumentsPropagateNullability` and `Arguments`** — the constructor throws `InconsistentNumberOfArguments` (`SqlFunctionExpression.cs:216-226`).
- **`IsNull(elseResult)` throws on a null `elseResult`** — signature is `IsNull(SqlExpression?)`; it returns `false`.
- **Shaping SQL on a runtime parameter value breaks caching** — parameter nullability is part of the 2nd-level cache key; `:1631` documents this and `DoNotCache()` is correctly not required.
- **`nullable` out-param wrong on the early-return path** — `IsNull(elseResult)` implies `elseResultNullable`, so `nullable` is already `true`.
- **CLR `Type`/`TypeMapping` drift on `return clause.Result`** — tested `StrA != null ? (int?)StrA.Length : null`; correct.
- **`operand` discarded on the early return** — guarded by `testIsCondition`, which is `caseExpression.Operand == null`.
- **`HashSet` structural equality could over-match** — `ColumnExpression` equality includes `IsNullable`, making it stricter; miss-only.
- **`TODO` without an issue link violates convention** — `SqlNullabilityProcessor.cs` has three other unlinked TODOs (`:2173`, `:2181`, `:2208`); ~75% of TODOs under `src/EFCore.Relational/` are unlinked.
- **Row sets returned by `WHERE` change** — I could not reproduce this; the one filter case I built kept its guard. Verified impact is on **projected values**.

## Positive observations

- All six changed baselines are semantically equivalent under three-valued logic — I checked each by hand (`LEN(NULL)`→NULL, `NULL + NULL`→NULL, identity cases). No baseline is a disguised regression.
- The new tests use `AssertQuery`, so they compare real rows against LINQ-to-Objects, not just SQL strings — the right shape for a null-semantics change. Seed data (`NullSemanticsData.cs:44-89`) genuinely contains NULLs, so the 3VL path is exercised, not vacuously passed.
- The unary arm is correctly allow-listed, and `SqlUnaryExpression` `Equal`/`NotEqual` (`IS [NOT] NULL`) are correctly excluded — a subtle case handled right.
- `DropNotNullChecks` descends only `AndAlso`, never `OrElse` — the conservative, correct choice.

## Recommended actions

1. **Blocking:** add the operator filter at `:626` excluding `AndAlso`/`OrElse`/`Coalesce`.
2. **Blocking:** add regression tests for boolean `&&`/`||`/`|` results and for `A != null ? (A == C) : null` — the last one is the cheapest reproduction of the whole class.
3. Add a negative test asserting the `CASE` is retained when the guard is not implied.
4. Extract the helpers into instance methods sharing logic with `ProcessNullNotNull`, and document the soundness invariant.
5. File the `:539` restore-count bug separately.

---

**Agents:** pr-summarizer, blind-hunter, architecture-reviewer, edge-case-hunter, adversarial-general, pr-test-analyzer, comment-analyzer completed. `code-reviewer` was still running when I consolidated; four independent agents already converged on finding #1, which I then confirmed by execution, so its result would not change the conclusion. Skipped: issue-linker (`--local`), security-reviewer (no trust-boundary surface in a query-compiler optimization), type-design-analyzer (no type definitions), silent-failure-hunter (no error-handling constructs), CVE check (no dependency manifests), static analyzers (none installed for C#).
The final agent (code-reviewer) has now returned. Let me clean up its scratch artifacts and verify repo state.
## Addendum — final agent result

`code-reviewer` completed after I consolidated. It **confirms finding #1 independently** and adds two things worth folding in. No conclusion changes; the review above stands.

**1. Cross-provider confirmation.** It built `EFCore.SqlServer` and used `ToQueryString()`, so the defect is now verified on **both** providers — my execution repro was SQLite, its SQL-generation repro is SQL Server:

```sql
-- x.NullableBoolA != null ? (x.NullableBoolA == true || x.BoolB) : (bool?)null
SELECT CASE
    WHEN [e].[NullableBoolA] = CAST(1 AS bit) OR [e].[BoolB] = CAST(1 AS bit) THEN CAST(1 AS bit)
    ELSE CAST(0 AS bit)
END
FROM [E] AS [e]
```
With `NullableBoolA = NULL, BoolB = 1`: `NULL OR TRUE` → `TRUE` → `1`, where the C# ternary yields `null`. Same divergence I measured on SQLite.

**2. A sharper root-cause statement, worth adding to finding #1.** The failure is not merely "the guard was redundant and got dropped" — the two halves actively compound:

> `NullableBoolA == true` is emitted as a raw, **uncompensated** `A = 1` comparison *because* the enclosing `A IS NOT NULL` guard put the column into `_nonNullableColumns` for that scope (`SqlNullabilityProcessor.cs:1286-1335`, `1368-1378`). The new optimization then removes that very guard. The uncompensated comparison is left exposed to a genuinely-NULL column at runtime.

That makes the fix direction firmer: the guard is load-bearing for simplifications already applied to the result under its scope, so excluding `AndAlso`/`OrElse` from the recursion at `:626` is the safe fix rather than any attempt to reason about the other operand — whether it can take the operator's absorbing value (`FALSE` for `AND`, `TRUE` for `OR`) is not statically knowable here. This also corroborates the coupling that `adversarial-general` flagged as undocumented (finding #6).

**3. It independently reached the same refutations** I listed — `Coalesce` unreachable through `SqlExpressionFactory.Coalesce` (confidence 35, "latent trap for provider code" only), the `nullable` out-parameter being sound (`nullable |= elseResult == null` forces `true` whenever this path is reachable), and `HashSet`/`ColumnExpression` equality being correct for cross-instance operand matching.

All eight dispatched agents have now reported. Five converged independently on finding #1; it is confirmed by execution on SQLite and by SQL generation on SQL Server, and is a regression against base `051c33a79`. Repo is clean, worktree removed, all scratch harnesses deleted; nothing was posted or modified.

