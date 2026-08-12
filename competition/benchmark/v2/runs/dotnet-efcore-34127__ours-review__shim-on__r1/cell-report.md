I'll run the code-review skill as requested.
Build gate passed (exit 0). Dispatching the review wave.

**Review team** (preset `review` — explicit; roster N=6 derived from ~150 changed executable lines):
- `quick-reviewer` (always) · `broad-reviewer` (always)
- `adversarial-reviewer` — 73 new executable lines in a query-rewriting optimizer; correctness hinges on composition
- `test-reviewer` — hard gate: test files in changeset
- `dotnet-reviewer` — hard gate: C# + idiom surface (nullable annotations, recursion, expression-tree equality)
- `knowledge-reviewer` — new non-obvious optimization with a `TODO` and no rationale docs
- `consistency-reviewer`: dropped — roster N=6, ranked below the 5 specialists kept
- `performance-reviewer`: dropped — roster N=6, ranked below the 5 specialists kept
- `design-reviewer`: skipped — no public API/contract surface changed (local static functions inside an existing `protected virtual` method)
- `security-reviewer`: skipped — no trust-boundary trigger in the diff
- `data-migration-reviewer`: skipped — no migration artifacts (hard gate)
- `spec-compliance-reviewer`: skipped — no spec found (hard gate)
All six reviewers returned. There's strong convergence on a correctness claim. Running the nominated probes now (Step 4.5) — I'm the only actor on the tree.
Probes 2, 3, and 5 reproduce wrong results. Now confirming these are introduced by this change (base-commit comparison via a separate worktree — the review tree is untouched).
Confirmed: at the base commit all 7 probes agree; under the change, 3 diverge. Now checking the SQL Server code path (search-condition conversion), which SQLite doesn't exercise.
Both Criticals are now empirically confirmed. Verifying the remaining secondary claims.
✅ Review complete: `.decaf/code-reviews/CODE_REVIEW_2026-08-12_10-41-24.md`

**Verdict: ❌ NEEDS_CHANGES** — 2 Critical, 2 High, 1 Low, 5 Minor, 1 pre-existing.

Six reviewers ran; I then ran their nominated probes myself by building both this commit and the base commit (in a throwaway worktree — the review tree was never modified) and executing the queries against seeded SQLite plus rendering them to SQL Server T-SQL. Two Criticals reproduced.

**#1 `src/EFCore.Relational/Query/SqlNullabilityProcessor.cs:626`** — `NullPropagatedOperands` recurses into both operands of *every* `SqlBinaryExpression` without checking `OperatorType`. `AndAlso`/`OrElse` are valid operators and don't propagate NULL under SQL three-valued logic (`NULL AND FALSE = FALSE`). So `DropNotNullChecks` deletes a guard that isn't redundant.

`x.NullableBoolA != null ? (bool?)(x.NullableBoolA.Value && x.BoolB) : null` compiles to bare `"NullableBoolA" AND "BoolB"`. Row `A = NULL, B = false` returns `false`; base commit and LINQ-to-Objects both return `null`. 9 of 54 seeded rows disagree. Same for `||` and for `A > 5 && B`. Every probe passes at the base commit, so this is introduced. This file already carries the exact exclusion at line 2313 for the inverse transformation, with a comment explaining why.

**#2 `SqlNullabilityProcessor.cs:578`** — independent, and it survives the fix for #1. When the test is `<col> IS NOT NULL`, the column is marked non-nullable while the result is visited, so `VisitSqlBinary` skips its protective CASE wrap and `clause.Result` stays a bare *search condition*. Collapsing then hands that condition to `SearchConditionConvertingExpressionVisitor`, which emits `CASE WHEN <cond> THEN CAST(1 AS bit) ELSE CAST(0 AS bit) END` — no NULL arm. `x.NullableIntA != null ? (bool?)(x.NullableIntA > 5) : null` returns `false` on SQL Server where it returned `null`. There's no `AndAlso`/`OrElse` anywhere in that query. SQLite masks it (it emits the bare comparison), which is why the suite is green; no test projects a boolean conditional whose result references the checked column — `Select_null_propagation_negative1` escapes only because it checks `LeaderNickname` and uses `Nickname`. I confirmed this from generated T-SQL, not execution — no SQL Server instance was available.

Also: the soundness invariant is nowhere written down (High), and the five added tests cover only arithmetic and string concatenation with no negative cases (High) — the operator classes where the optimization is sound.

One correction to a reviewer claim: `broad-reviewer` reported a Critical `Coalesce` counterexample using `??`. I ran it — it's correct, because `SqlExpressionFactory.Coalesce` emits a `SqlFunctionExpression` with `argumentsPropagateNullability: [false, false]`, which the code handles properly. It survives only as latent risk (Low), since `SqlBinaryExpression` still sanctions a `Coalesce` operator no in-box code constructs.

