✅ Review complete: `.decaf/code-reviews/CODE_REVIEW_2026-08-18_22-28-08.md`

**Mode**: `bugs` (single seat, roster=1) · `reach=norm` · `--report`. No source file was modified; the only working-tree addition is the review report itself.

**Verdict: ❌ NEEDS_CHANGES** — 1 Critical, 1 High, 1 Medium, plus 1 pre-existing and 4 minor.

The two correctness findings both attack the same soundness argument behind the new `VisitCase` optimization ("if the null-checked operand is NULL, the result is NULL, so the `CASE` is redundant"):

1. **Critical — `SqlNullabilityProcessor.cs:626`**: `NullPropagatedOperands` recurses into both operands of *every* `SqlBinaryExpression`, including `AndAlso` and `OrElse`, which do not propagate NULL (`TRUE OR NULL = TRUE`). This file already encodes that exact exclusion 1700 lines later, in `ProcessNullNotNull` at line 2313. Consequence: `g.LeaderNickname != null ? g.LeaderNickname.Length > 3 || g.HasSoulPatch : null` drops the `IS NOT NULL` guard and starts matching rows where `LeaderNickname IS NULL`. Provider-independent. A second route needs no `||` in the user query at all — EF's own null-semantics rewrite manufactures the `OrElse` using the very non-nullability knowledge being dropped.

2. **High — `SqlNullabilityProcessor.cs:578`**: the guard does not distinguish a scalar result from a *search condition* result. `SqlNullabilityProcessor` runs before SQL Server's `SearchConditionConvertingExpressionVisitor`, whose `ConvertToValue` emits `CASE WHEN c THEN 1 ELSE 0 END` — so once the enclosing `ELSE NULL` is gone, a NULL condition becomes `false`. `x.NullableIntA != null ? (bool?)(x.NullableIntA > 5) : null` returns `false` instead of `null`. Silent; SQL Server only.

3. **Medium — new tests**: all five added tests project scalars through genuinely-propagating operators, so neither defect class is covered — which is why the baseline sweep came back clean. Several added branches (`Negate`, the right-side drop, the two-surviving-conjuncts `Update`, `InstancePropagatesNullability`) are also unexercised.

Both correctness findings are anchored at 75 (`traced`, not executed): the SQL Server functional tests need a live instance, and the REVIEW-ONLY constraint ruled out authoring a probe test. Every step is anchored on committed code or on baselines already in the repo — including one of this change's own updated baselines, which proves the `CAST(LEN(...))` walk reaches the column. I independently re-verified the citations behind #1 and #2 (line anchors, the `ProcessNullNotNull` guard, the visitor ordering, `ConvertToValue`, and that `SqlBinaryExpression` admits `AndAlso`/`OrElse`/`Coalesce`); all match.
