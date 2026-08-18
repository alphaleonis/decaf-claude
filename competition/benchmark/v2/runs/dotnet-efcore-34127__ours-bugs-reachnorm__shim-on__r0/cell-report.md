I'll invoke the requested skill.
No spec found (no `--spec`, no PR, no matching plan doc in the repo).

```
Review team (preset `bugs` — single seat · roster=1 · seat on session model · evidence self-calibrated · reach=norm):
- solo-reviewer (the preset's single seat) — session model
- wave agents: not evaluated — bugs is a single-seat path (use `bugs roster=N` for the wave)
```

Step 3.0 pre-flight is skipped on this path (the seat runs its own targeted gates).
✅ Review complete: `.decaf/code-reviews/CODE_REVIEW_2026-08-18_21-37-23.md`

**Mode**: `bugs` (single seat, roster=1) · `reach=norm` · `--report`. Verdict: ❌ **NEEDS_CHANGES** — 2 Critical, 1 Medium, 1 Low, plus 4 minor and 1 pre-existing.

Both Criticals say the new `VisitCase` rewrite in `src/EFCore.Relational/Query/SqlNullabilityProcessor.cs` drops the `IS NOT NULL` test in cases where the result does **not** actually propagate SQL NULL, producing wrong query results with no error:

1. **`SqlNullabilityProcessor.cs:626`** — `NullPropagatedOperands` descends into *every* `SqlBinaryExpression` with no `OperatorType` check. `AndAlso`/`OrElse` are not strict (`NULL AND FALSE` = `FALSE`), so `A != null ? (bool?)(A > 5 && BoolB) : null` collapses to `A > 5 AND BoolB` and returns `False` where it must return `null`. This was executed against SQLite at HEAD versus the parent commit; the parent commit matches LINQ-to-Objects on every row and HEAD does not. It also fires without a literal `&&`, because EF's own null-semantics expansion of `a == b` produces an `AndAlso`.

2. **`SqlNullabilityProcessor.cs:576`** — even a strictly-propagating *condition* result (`A > 5`) loses its NULL on SQL Server: `SearchConditionConvertingExpressionVisitor` runs later and maps `UNKNOWN` to `CAST(0 AS bit)`, so the deleted outer `CASE` was the only thing preserving `NULL`. Evidenced by the generated SQL at both commits; not executed against a live SQL Server, and the report says so.

3. **Medium (`NullSemanticsQueryTestBase.cs:2250`)** — all five new tests project non-boolean results (`~`, `+`, string concat). The whole dangerous region (boolean results, `AndAlso`/`OrElse`, comparisons) is untested, which is why the above is green in CI.

The suggested fix for both Criticals is one change: replace the unconditional binary arm with an allowlist of genuinely strict operators (arithmetic/bitwise/concat), which also excludes comparisons and closes the Low finding about `ExpressionType.Coalesce` (`SqlBinaryExpression.cs:102`) for free.

Caveats worth carrying: the seat could not run the repo's test suites (test projects fail to compile under the installed SDK 10.0.400, for reasons pre-dating this change), so it built the providers from source and drove them from a throwaway app against a worktree at the parent commit. The working tree is unchanged (`git status` shows only the new untracked `.decaf/`). One parked item in the report carries no closed-set reason, and the seat's own Minor count was off by one — corrected by recount, with no finding re-tiered.

