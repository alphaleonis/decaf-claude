I'll run the code review skill as requested.
I'll start by gathering context on the change under review.
**Review team** (preset `bugs`, explicit — roster N=4, models=low, evidence=strong, reach=narrow):
- `quick-reviewer` (always) · `broad-reviewer` (always)
- `adversarial-reviewer` — 73 changed executable lines in a SQL null-semantics optimizer; composition failures are the risk
- `test-reviewer` — test files present (hard gate); the SQL baselines *are* the assertions
- `dotnet-reviewer`: skipped — C# present (hard gate ✓) but no idiom surface (no async/Task, disposal, change tracking, deferred LINQ, threading)
- `knowledge`/`consistency`/`design`/`security`/`performance`/`data-migration`/`spec-compliance`/`prior-feedback`: dropped or gate-unmatched
Build succeeded (exit 0). All four reviewers converged on one issue. Let me verify it myself with targeted probes.
**CASE 2 reproduces a wrong result.** Now let me confirm it's a regression introduced by this change, using a separate worktree at the base commit.
**Regression confirmed.** At the base commit, all cases match LINQ-to-Objects exactly; after the change, two produce wrong values. Let me check the Coalesce path too, then clean up.
Main tree clean and untouched. Running the validation wave on the Critical finding.
Confirmed. Writing the report.
✅ Review complete: `.decaf/code-reviews/CODE_REVIEW_2026-08-11_bugs.md`

No prior reviews exist in this repo, so the Recurring Findings step was skipped. Tracked source is untouched (only the untracked `.decaf/` report was added); the scratch probe project and base-commit worktree have been removed.

## Verdict: ❌ NEEDS_CHANGES — 1 Critical

**`src/EFCore.Relational/Query/SqlNullabilityProcessor.cs:626` — `NullPropagatedOperands` treats `AND`/`OR` as null-propagating, producing wrong query results.**

The helper's contract is "if this operand is NULL, the whole `CASE` result is NULL" — that's what licenses `DropNotNullChecks` to delete the guarding `X IS NOT NULL`. Every other descent respects it: the unary arm is restricted to `Not`/`Negate`/`Convert`, and the function arm consults `ArgumentsPropagateNullability`. The binary arm never inspects `OperatorType`, but `SqlBinaryExpression.IsValidOperator` admits `AndAlso`, `OrElse`, and `Coalesce`. SQL absorbs NULL for the logical pair — `NULL OR TRUE = TRUE`, `NULL AND FALSE = FALSE` — so the guard is deleted on a premise that doesn't hold, and the `CASE` collapses to the bare result.

I reproduced it against both commits with a standalone SQLite probe:

| Query | `051c33a79` (base) | `afcfba2e9` (this change) |
|---|---|---|
| `NullableBoolA != null ? NullableBoolA \| BoolA : null` | `null,true,false,null` ✅ | `true,true,false,null` ❌ |
| `NullableBoolA != null ? NullableBoolA & BoolA : null` | `null,false,false,null` ✅ | `null,false,false,false` ❌ |

The base commit matches LINQ-to-Objects on every row; the change under review does not. EF Core's `AssertQuery` treats that equality as the contract, so these are wrong results, not accepted divergences. The failure is silent — no exception, just a `TRUE`/`FALSE` where `NULL` belongs. `e.NullableBoolA | e.BoolA` reaches `VisitCase` as `OrElse`, so this is an ordinary user query.

The fix is a one-line operator filter excluding `AndAlso`/`OrElse`/`Coalesce` from the recursion, plus regression tests for both shapes. All four new tests in the diff use arithmetic or string concatenation, where NULL genuinely does propagate — none exercises the broken arm.

Two things I want to flag about the report's confidence:

- **`Coalesce` is not a live defect.** Two reviewers flagged it independently; my probe refutes it as reachable — EF routes `??` to a `SqlFunctionExpression` with `argumentsPropagateNullability: [false, false]`, which the helper correctly declines to descend. Excluding it is cheap insurance for third-party providers, not a fix.
- **A SQL Server–specific second manifestation is [Unverified].** `adversarial-reviewer` traced a comparison-result variant that depends on `SearchConditionConvertingExpressionVisitor` wrapping a bare condition with `ELSE CAST(0 AS bit)`. I could not reproduce it — SQLite has no bit/search-condition distinction and no SQL Server instance was available. Same root cause and line, but if it holds it widens the fix to comparison operators in value position. Worth checking before settling on the operator list.

