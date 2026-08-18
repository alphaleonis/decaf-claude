I'll invoke the code-review skill as requested.
**Review team** (preset `bugs` — single seat · roster=1 · seat on session model · evidence self-calibrated · reach=norm):
- `solo-reviewer` (the preset's single seat) — session model
- wave agents: not evaluated — `bugs` is a single-seat path (use `bugs roster=N` for the wave)
- Spec: none found (no `--spec`, local commit range, no linked work item)

Pre-flight gates: skipped per the `bugs` path (the seat runs its own targeted gates).
✅ Review complete: `.decaf/code-reviews/CODE_REVIEW_2026-08-18_21-52-57.md`

**Verdict: ❌ NEEDS_CHANGES** — 1 Critical, 1 Medium, 4 Minor, 1 pre-existing (informational).

The critical defect is at `src/EFCore.Relational/Query/SqlNullabilityProcessor.cs:626`. `NullPropagatedOperands` recurses into both operands of **every** `SqlBinaryExpression`, but `AndAlso`, `OrElse` and `Coalesce` are legal operators there (`SqlBinaryExpression.cs:87-103`) and none of them propagates NULL — `NULL OR TRUE = TRUE`, `NULL AND FALSE = FALSE`. Operands reached through those nodes get added to the set, so `DropNotNullChecks` deletes an `IS NOT NULL` guard that was load-bearing, and when all conjuncts go the `CASE` vanishes entirely.

This is reached by any ternary with a boolean result, including EF Core's own null-semantics expansion (`a == b` → `a = b AND b IS NOT NULL`), which is only valid under the guard being dropped. The reviewer built both the base and changed commits and ran identical queries through SQLite: six probe shapes mismatched LINQ-to-Objects on the changed build and all matched on the base. One of them changes a `WHERE` row count (24 returned vs. 18 expected), so this is wrong rows, not just wrong projected values.

Suggested fix: invert the binary arm to an explicit allowlist of null-propagating operators so a future operator fails closed. The arithmetic and string-concatenation shapes the new tests cover are unaffected.

The Medium finding explains why CI would not catch this: all five new tests have value-typed `THEN` results, so none reaches the `AndAlso`/`OrElse` arms. They would pass byte-for-byte both before and after the fix.

Two things to note about the evidence. `test/EFCore.Specification.Tests` does not compile under the installed SDK 10.0.400 (nine pre-existing errors unrelated to this diff), so the functional suite was not run — the verification is a standalone `DbContext` comparison against both builds instead. And the pre-existing `RestoreNullValueColumnsList` counter mix-up at line 539 is inherited, not introduced; it is recorded as informational under `reach=norm`.

