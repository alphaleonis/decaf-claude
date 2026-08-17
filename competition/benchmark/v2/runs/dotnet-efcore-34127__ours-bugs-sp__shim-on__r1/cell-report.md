I'll run the code review skill as requested.
I'll start by gathering the change context.
**Review team** (preset `bugs-sp` — explicit · roster=1 fixed · seat on session model · evidence self-calibrated · reach=narrow):
- `solo-reviewer` (the preset's single seat) — session model
- wave agents: not evaluated — bugs-sp replaces the wave

Pre-flight: skipped (bugs-sp — the seat runs its own targeted gates). Spec: none found.
Line references verified against HEAD; tree is clean. Writing the report.
✅ Review complete: `.decaf/code-reviews/CODE_REVIEW_2026-08-17_09-12-41.md`

No tracked file was modified (only the untracked `.decaf/` artifact directory was added); HEAD is still `afcfba2e9`. No previous reviews exist, so Step 7 (recurring findings) was skipped.

**Verdict: ❌ NEEDS_CHANGES** — 2 Critical, 3 Minor.

Both Criticals land on the same helper, `NullPropagatedOperands` in `src/EFCore.Relational/Query/SqlNullabilityProcessor.cs:626-630`, which descends into a `SqlBinaryExpression`'s operands regardless of operator type:

1. **`AndAlso`/`OrElse` don't propagate NULL.** Under three-valued logic `NULL AND FALSE = FALSE`, `NULL OR TRUE = TRUE`, so the guard is not redundant there. The reviewer built `EFCore.Relational`/`EFCore.Sqlite.Core` at both `afcfba2e9` and its parent `051c33a79` and ran identical queries over identical SQLite data against a LINQ-to-Objects oracle: `x.NullableBoolA != null ? (bool?)(x.NullableBoolA.Value || x.BoolB) : null` returns `True` at HEAD where the oracle and the parent commit both return `null`. In predicate position it changes the row set (rows `1,2,5` at HEAD vs `2,5` correct). This shape is reachable through EF's own null-semantics compensation, which emits `AndAlso`/`OrElse` when rewriting `a == b` / `a != b`.

2. **Boolean search-condition results lose NULL on SQL Server** — a *separate* defect with a separate fix, on a plain `Equal` node, so excluding the logical operators does not address it. When the collapsed result is a predicate, SQL Server's search-condition converter materializes it as `CASE WHEN <pred> THEN CAST(1 AS bit) ELSE CAST(0 AS bit) END`, folding `UNKNOWN` into `false`. The deleted outer `CASE … ELSE NULL END` was the only thing preserving the `NULL`. Confirmed by generating SQL at both commits; SQLite is unaffected, which is why the Sqlite functional tests can't see it.

The five new tests all use arithmetic/string results, which is exactly why neither defect trips them.

One caveat on verification, carried from the reviewer: the repo's own `EFCore.Specification.Tests` does not compile under the installed SDK (10.0.203 against `net8.0` sources), so the findings were verified through a standalone harness referencing the repo's own provider projects rather than the project's test suite — and it is **not** established whether any existing suite test already fails at HEAD.

