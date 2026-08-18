I'll invoke the requested skill.
**Review team** (preset `bugs` — single seat · roster=1 · seat on session model · evidence self-calibrated · reach=narrow):
- `solo-reviewer` (the preset's single seat) — session model
- wave agents: not evaluated — `bugs` is a single-seat path (use `bugs roster=N` for the wave)

**Spec**: none found. **Pre-flight**: skipped (single-seat path runs its own targeted gates).
✅ Review complete: `.decaf/code-reviews/CODE_REVIEW_2026-08-18_23-19-03.md`

**Verdict: ❌ NEEDS_CHANGES** — 1 Critical finding.

### #1 🔴 Critical — `src/EFCore.Relational/Query/SqlNullabilityProcessor.cs:626`

`NullPropagatedOperands` recurses into `binary.Left`/`binary.Right` for **every** `SqlBinaryExpression` operator type. `SqlBinaryExpression.IsValidOperator` admits `AndAlso`, `OrElse`, and `Coalesce`, none of which propagate NULL (`NULL OR TRUE` = `TRUE`; `NULL AND FALSE` = `FALSE`). Operands reached only through such a node are wrongly recorded as null-propagating, so `DropNotNullChecks` deletes their `IS NOT NULL` test and the CASE wrapper is removed — yielding wrong scalars and wrong rows.

The same file already states the rule the new code violates, at `:2315-2321`: *"for AndAlso, OrElse we can't do this optimization"*.

**Verified by execution.** `EFCore.Sqlite` was built at head and at base (via `git worktree`) and driven through an out-of-tree differential harness over the null cross-product. Three of six probes regress at head; all six match at base. Example: `x.NullableStringA != null ? (bool?)(x.NullableStringA != x.NullableStringB) : null` emits `A <> B OR B IS NULL` at head and returns `True` for the `(NULL, NULL)` row instead of `null`; the predicate form returns an extra row. One regressing case uses a plain user-written `||`, so the defect does not depend on EF's null-semantics rewrite.

**Fix:** exclude `AndAlso`/`OrElse`/`Coalesce` from the recursion (an allow-list of arithmetic/bitwise/comparison operators is safer against future `IsValidOperator` additions). This still permits every shape the five new tests assert. Regression tests for the two failing shapes, in both projection and predicate position, are needed — no existing or added test covers them, so CI would go green on this.

### Caveats on the verification environment
- `test/EFCore.Specification.Tests` does not compile under the installed SDK 10.0.400 — at **base** as well as head (18 `CS` errors), so this is pre-existing. Consequently **no in-repo test suite ran**; the finding rests on the out-of-tree harness.
- No SQL Server instance was reachable, so the SQL Server baselines updated in this diff were not executed. `SqlNullabilityProcessor` is provider-agnostic, so the defect is not SQLite-specific.

Six further observations were parked as minor or false (including a `Coalesce` variant that no core-translator path currently reaches, and a `func.Instance!` dereference that is inconsistent with its sibling at `:2394` but not exploitable). Two parked entries are process notes carrying no closed-set tag; per the single-seat rules they were counted, not re-tiered.

