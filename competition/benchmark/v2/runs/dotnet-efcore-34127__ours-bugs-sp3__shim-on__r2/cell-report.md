I'll run the requested code-review skill.
I'll follow the `bugs-sp` path. Starting with context gathering.
**Review team** (preset `bugs-sp` — explicit · roster=1 fixed · seat on session model · evidence self-calibrated · reach=narrow):
- `solo-reviewer` (the preset's single seat) — session model
- wave agents: not evaluated — `bugs-sp` replaces the wave

Spec discovery: none found (no PR, no `--spec`, no linked work item).
✅ Review complete: `.decaf/code-reviews/CODE_REVIEW_2026-08-17_14-37-47.md`

**Verdict: ❌ NEEDS_CHANGES** — 1 Critical, 0 High/Medium/Low.

## The finding

**`src/EFCore.Relational/Query/SqlNullabilityProcessor.cs:626`** — the new `NullPropagatedOperands` helper recurses into *every* `SqlBinaryExpression` operator, but `SqlBinaryExpression.IsValidOperator` also admits `AndAlso`, `OrElse`, and `Coalesce` — none of which propagate NULL over their operands. SQL's three-valued logic absorbs NULL (`FALSE AND NULL = FALSE`, `TRUE OR NULL = TRUE`).

So for `CASE WHEN a IS NOT NULL THEN (a AND b) ELSE NULL END`, `a` is wrongly recorded as null-propagated, `DropNotNullChecks` deletes the guard, and the CASE collapses to `a AND b` — yielding `FALSE` where the original yielded `NULL`.

This is reached by an ordinary shape, not an exotic one: EF's own null-semantics rewrite turns `a == b` into `a = b AND b IS NOT NULL`, so any `x.Nullable != null ? x.Nullable == x.Other : (bool?)null` is miscompiled. The rule being violated is already written in the same file at `:2314-2321`, where the mirror-image transform explicitly excludes `AndAlso`/`OrElse` with the comment *"for AndAlso, OrElse we can't do this optimization"*. The new helper is that traversal with the exclusion missing.

**Evidence (executed):** a standalone SQLite probe built against the repo's own `EFCore.Sqlite.Core`, run at HEAD and at the merge base in a separate worktree — **17/17 match at the base commit, 10 mismatches at HEAD**. Both wrong projected values (`null` → `false`/`true`) and wrong row sets in predicate contexts (e.g. expected Ids `[2,3,4,6]`, actual `[2,3,4,6,9]`). Failures are silent; nothing throws.

**Why CI is green:** the five new tests only cover `~int?`, `int? + int?`, and string concat — all genuinely null-propagating. No boolean or comparison result is tested anywhere in the new cases, so every added and updated baseline is consistent with the defect being present.

Suggested fix is an allow-list of genuinely null-propagating operators (which also closes the latent `Coalesce` case) rather than a two-operator deny-list. Note `And`/`Or` (bitwise) do propagate and stay in; `AndAlso`/`OrElse` (boolean) do not.

## Caveats on the evidence

The repository's own test suites were **not** run — `test/EFCore.Specification.Tests` does not compile in this environment (9 errors under SDK 10.0.203 rolling forward from the pinned 9.0 preview), and SQL Server functional tests need a live server. The execution evidence is entirely from the standalone probe. The SQL Server analysis (`SearchConditionConvertingExpressionVisitor` producing the same `null → false` corruption) is reasoned, not executed.

Working tree verified clean afterward: `git status --porcelain` empty, HEAD unchanged at `afcfba2e9`, no leftover worktrees. Nothing was posted anywhere and no code was modified.

Two notes on the report itself: 8 parked items carry proper tags, 1 (a procedural remark) does not — recorded as a count per the `bugs-sp` rules, not promoted. And this is a single-agent path with no validation wave, so the result carries one agent's variance; the Critical is backed by executed before/after evidence, but the parked items had no second reader.

