✅ Review complete: `.decaf/code-reviews/CODE_REVIEW_2026-08-17_09-27-21.md`

**Verdict: ❌ NEEDS_CHANGES** — 2 Critical, 1 Medium, 2 Minor.

The production change is 73 lines in `src/EFCore.Relational/Query/SqlNullabilityProcessor.cs`; everything else is tests and SQL baselines.

**#1 🔴 `SqlNullabilityProcessor.cs:626` — `NullPropagatedOperands` recurses through `AndAlso`/`OrElse`.** Those operators don't propagate NULL (`NULL AND FALSE = FALSE`, `NULL OR TRUE = TRUE`), so for `CASE WHEN x IS NOT NULL THEN (x AND y) ELSE NULL END` the guard gets erased and the expression yields `FALSE` where it used to yield `NULL`. The same file already encodes this rule at line 2314 (`ProcessNullNotNull`, guarded with *"for AndAlso, OrElse we can't do this optimization"*) — I confirmed that guard exists and the new helper omits it. The reviewer executed this against real SQLite rows on both commits: 4 of 6 probes regress, with the two controls still matching. It corrupts `Where` filtering, not just projections.

**#2 🔴 `SqlNullabilityProcessor.cs:576` — boolean-typed results are unsafe on SQL Server even after fixing #1.** A comparison like `x > 2` genuinely propagates NULL as a three-valued condition, so the guard is legitimately dropped — but `SearchConditionConvertingExpressionVisitor` runs *afterwards* and lowers it to `CASE WHEN <cond> THEN CAST(1 AS bit) ELSE CAST(0 AS bit) END`, where UNKNOWN falls into the `ELSE` and becomes `0`. NULL is no longer producible. This one is **traced, not executed** — no SQL Server instance available — but the evidence is generated-SQL text diffed against the base commit, and SQLite (which emits the condition directly) executed clean, so it's provider-specific and a SQLite-only run won't catch it.

**#3 🟡** The binary-operator null-propagation table is hardcoded in the shared relational base with no provider seam; string `Add` is the risky entry for dialects where `'abc' || NULL` isn't NULL. Read-only inference about out-of-tree providers, anchor 50.

Two caveats on the evidence, both recorded in the report: the repo's own test suites **could not be run** (SDK 10.0.203 vs. the pinned 9.0.100-preview — `test/EFCore.Specification.Tests` fails to compile), so the seat built the providers and drove them through a standalone harness in `/tmp` instead; and it created a temporary `git worktree` at the base commit. I verified afterwards that the tree is clean, `git worktree list` shows only the original checkout, and HEAD is unchanged. Nothing was posted or modified.

Worth noting for the fix: none of the five new `Is_not_null_optimizes_*` tests uses a boolean-typed result, which is exactly why the suite is silent about both Criticals.
