✅ Review complete: `.decaf/code-reviews/CODE_REVIEW_2026-08-17_14-50-24.md`

**Verdict: ❌ NEEDS_CHANGES** — 1 Critical, 1 Medium. No prior reviews exist, so no recurring-findings section.

### #1 🔴 Critical — `src/EFCore.Relational/Query/SqlNullabilityProcessor.cs:626`

`NullPropagatedOperands` recurses into both operands of **every** `SqlBinaryExpression`, but `AndAlso` and `OrElse` are legal operators (`SqlBinaryExpression.cs:88-91`) and are **not** NULL-strict in SQL's three-valued logic (`NULL AND FALSE = FALSE`, `NULL OR TRUE = TRUE`). The helper therefore records operands the result does *not* propagate NULL from, `DropNotNullChecks` deletes the corresponding `IS NOT NULL` test, and the `CASE` collapses to an expression returning `TRUE`/`FALSE` where the original returned `NULL`.

This is reached by ordinary queries, not a corner case — the null-semantics expansion of a comparison *is* an `AndAlso`/`OrElse`, and because the WHEN result is visited with the test's columns already in `_nonNullableColumns` (lines 512-514), dropping the test invalidates the very assumption the result was simplified under.

Verified by execution, not inference: the reviewer built `src/EFCore.Sqlite.Core` at both the head and (via a temporary worktree) the base commit and ran the same probe against a real SQLite database, comparing DB results against the same lambda in memory. **All 10 probes pass at base; 7 of 10 return wrong results at head.** In predicate position, `Where(x => (x.NullableBoolA != null ? (bool?)(x.NullableBoolA.Value || x.BoolA) : null) == true)` emits `WHERE "e"."NullableBoolA" OR "e"."BoolA"` and returns **36 rows instead of 27**.

The five new theories all use arithmetic/string/unary results, so none exercises a logical-connective result — **the suite goes green on this defect.**

Fix: replace the catch-all binary arm with an explicit allow-list of NULL-strict operators (excluding `AndAlso`, `OrElse`, `Coalesce`), and add boolean/comparison-result theories in both projection and `Where` position.

### #2 🟡 Medium — same line

`ExpressionType.Coalesce` is also admitted by `IsValidOperator` (`SqlBinaryExpression.cs:102`) and constructible via the public `MakeBinary`, and it is the archetypal non-strict operator. No in-tree translator produces the binary form today (`Coalesce` routes to a `SqlFunctionExpression` with `argumentsPropagateNullability: [false, false]`, handled correctly by the function arm) — so this is a provider-facing hazard, traced rather than executed, hence anchor 50. The allow-list in #1 closes it.

Working tree verified clean afterward (`git status --porcelain` empty, HEAD unchanged, no leftover worktrees). One caveat carried from the seat: the repo's own functional suites were not run — `test/EFCore.Sqlite.FunctionalTests` doesn't compile under the installed SDK (10.0.203 vs. `global.json`'s 9.0.100-preview, 9 pre-existing errors unrelated to this change), so verification went through a standalone probe instead.
