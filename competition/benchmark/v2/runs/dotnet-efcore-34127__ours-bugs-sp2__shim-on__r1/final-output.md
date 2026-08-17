✅ Review complete: `.decaf/code-reviews/CODE_REVIEW_2026-08-17_11-38-34.md`

**Verdict: ❌ NEEDS_CHANGES** — 1 Critical, 1 Medium (preset `bugs-sp`, single seat, `reach=narrow`).

**#1 🔴 Critical — `src/EFCore.Relational/Query/SqlNullabilityProcessor.cs:626`**
The new `NullPropagatedOperands` helper recurses into *every* `SqlBinaryExpression` operator type, but `IsValidOperator` admits `AndAlso`/`OrElse`, which do **not** propagate NULL under SQL's three-valued logic (`NULL OR TRUE = TRUE`, `NULL AND FALSE = FALSE`). Any operand appearing anywhere inside a boolean result gets marked null-propagated, `DropNotNullChecks` deletes its `IS NOT NULL` test, and the `CASE` collapses — returning `true`/`false` on exactly the rows the guard existed to map to `NULL`.

The reviewer verified this by executing: a scratch app against `src/EFCore.Sqlite.Core` at `afcfba2e9` versus a worktree at the pre-change commit `051c33a79`, comparing DB results to LINQ-to-Objects. Six shapes regress, e.g. `x.NullableIntA != null ? (bool?)(x.NullableIntA == x.NullableIntB) : null` emits `"NullableIntA" = "NullableIntB" AND "NullableIntB" IS NOT NULL` and yields `False` where it must yield `null`. This is a common shape — EF's own null-semantics expansion of `==`/`!=` between nullable operands *produces* the `AndAlso`/`OrElse` nodes that trigger it.

Compounding detail: the WHEN-result is visited (`:534`) while `_nonNullableColumns` still holds knowledge established by the test, so `A == B` is emitted in the already-simplified form `A = B AND B IS NOT NULL`. Dropping the guard invalidates simplifications baked into the result, not just the guard.

Suggested fix is an operator **allow-list** (arithmetic, bitwise, comparisons) excluding `AndAlso`, `OrElse`, `Coalesce`, so future operators fail closed — plus spec tests with `bool?`-typed results. All five new tests project `int?`/`string`, which is why the suite is green on this.

**#2 🟡 Medium — same line:** `Coalesce` is likewise traversed. Not reachable through the stock pipeline today (`??` routes to a `SqlFunctionExpression` with `argumentsPropagateNullability: [false, false]`, handled correctly; and `QuerySqlGenerator.GetOperator` throws `UnreachableException` for binary `Coalesce`), but the operator is legal per `IsValidOperator` and buildable via the public `MakeBinary`. Covered free by the same allow-list.

The report also records what held up well (the `SqlFunctionExpression` arm's nullability-metadata handling, the tight entry guard, the deliberate stop at `IS NULL`/`IS NOT NULL` unaries) and five items considered but not flagged — including two pre-existing defects out of reach under `narrow`, and a note that `test/EFCore.Specification.Tests` does not compile under the installed SDK for reasons pre-dating this change. Nothing was posted or modified; the reviewer confirmed the tree byte-identical afterwards.
