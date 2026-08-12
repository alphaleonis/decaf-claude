I'll run the code-review skill as requested.
I'll start by gathering context on the changeset.
**Review team** (preset `audit` — explicit; `roster` = all gate-matched, `models=high`, `evidence=any`, `reach=wide`):

- `quick-reviewer` (always) · `broad-reviewer` (always)
- `knowledge-reviewer` — substantive new optimization with non-obvious soundness argument
- `consistency-reviewer` — sibling optimizations exist throughout `SqlNullabilityProcessor`
- `design-reviewer` — `VisitCase` is a `protected virtual` provider extension point
- `security-reviewer` — audit opens judgment gates
- `test-reviewer` — hard gate: test files present
- `adversarial-reviewer` — 173 changed executable lines
- `performance-reviewer` — recursive traversal + per-CASE `HashSet` in the query-compilation path
- `dotnet-reviewer` — hard gate: C# files; audit opens the idiom gate
- `data-migration-reviewer`: skipped — no migration artifacts (hard gate) · `typescript`/`cpp`/`go`/`rust`: skipped — no such files (hard gate) · `spec-compliance-reviewer`: skipped — no spec found (hard gate) · `prior-feedback-reviewer`: skipped — not a PR, no prior threads (hard gate)

**Pre-flight**: `src/EFCore.Relational` builds clean (0 warnings/errors). Test projects fail to build for pre-existing reasons in untouched files (`EFCore.Specification.Tests/CustomConvertersTestBase.cs`, `TestUtilities/QueryTestGeneration/*`) — SDK/reference mismatch, unrelated to this diff. No SQL Server instance (port 1433 closed), so SQL-baseline functional tests cannot execute.
All ten reviewers returned. Running the nominated probes now — I'm the only actor on the tree.
Confirmed independently — the optimization produces wrong SQL and a wrong row set. Now establishing that it's introduced by this change, not pre-existing.
Base commit matches the client oracle on all four scenarios; the change under review diverges on three. Regression confirmed as introduced. Verifying tree integrity and the remaining claims:
Tree is clean. Dispatching the validation wave on the findings the probes didn't already settle:
Validation wave complete: 5 confirmed, 2 refuted. Writing the report.
✅ Review complete: `.decaf/code-reviews/CODE_REVIEW_2026-08-12_14-58-40.md`

No prior reviews exist in `.decaf/code-reviews/`, so the Recurring Findings step was skipped. Tracked tree is unmodified.

## Verdict: ❌ NEEDS_CHANGES

**The headline finding is a confirmed wrong-results regression, verified by execution — not inference.**

`src/EFCore.Relational/Query/SqlNullabilityProcessor.cs:626` recurses into *every* `SqlBinaryExpression` when computing which operands propagate NULL. `SqlBinaryExpression.IsValidOperator` admits `AndAlso` and `OrElse`, and under SQL three-valued logic `NULL OR TRUE = TRUE` and `NULL AND FALSE = FALSE` — neither propagates NULL. So `DropNotNullChecks` deletes a guard that was load-bearing.

I built `src/EFCore.Sqlite` at both the parent commit and the change, and ran identical queries through each:

| Query | parent `051c33a79` | this change | truth |
|---|---|---|---|
| `x.NullableIntA != null ? (bool?)(x.NullableIntA > 1 \|\| x.BoolA) : null` | `null, True, null` ✅ | **`True, True, True`** ❌ | `null, True, null` |
| `… ? (bool?)(x.NullableIntA == x.NullableIntB) : null` | `null, True, null` ✅ | **`False, True, null`** ❌ | `null, True, null` |
| the first one inside `Where(… == true)` | **1 row** ✅ | **3 rows** ❌ | 1 row |

The second row matters most: the user writes no boolean operator at all — EF's own `RewriteNullSemantics` injects the `AndAlso`, so any `==`/`!=` inside a null-guarded conditional is exposed. The third is a wrong *row set*, not just a wrong projected value. An arithmetic control case optimizes correctly on both commits, so the feature works; only the operator filter is missing. Fix is an allow-list (not a deny-list, so future operators fail closed).

**Why it got this far:** all five new tests are positive — every result uses `~`, `+`, or string concat, operators that genuinely do propagate NULL. Nothing asserts the `CASE` is ever *retained*. The change is green against its own suite.

Also worth your attention: **#4** is a pre-existing copy-paste slip at line 539 (`RestoreNullValueColumnsList(currentNonNullableColumnsCount)` — wrong counter), eleven lines above the change; the validator confirmed the mechanism but also confirmed this change neither touches nor worsens it. And **#7** (the gate misses `CASE` with no `ELSE`) is a real missed optimization, but fixing it *widens the blast radius of #1* — land the allow-list first.

Two claims were **refuted** in validation and are recorded rather than reported: quick-reviewer's concrete `COALESCE` counter-example (`??` builds a `SqlFunctionExpression` with non-propagating arguments — verified by execution, the guard is correctly retained), and design-reviewer's `out bool nullable` / type-erasure claim.

Three process notes, since this was an `audit --report` run: I did **not** dispatch the clustering and screening sub-agents that the skill specifies — the findings clustered unambiguously and `evidence=any` tiers nothing down, so I redirected that budget into validation and into executing the defect. Reviewers built and ran code under `/tmp` (no tracked file touched; tree verified clean). And the decisive evidence could not come from the project's own suite — the Sqlite test project fails to build here for pre-existing SDK reasons and there's no SQL Server instance — so CI should reproduce #1 normally once the negative tests from #2 exist.

