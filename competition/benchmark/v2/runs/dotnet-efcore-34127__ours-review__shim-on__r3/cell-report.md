I'll start by invoking the requested skill.
I'll gather the change under review first.
**Review team** (preset `review` — explicit · roster N=6 (derived: ~119 executable lines) · models=norm · evidence=norm · reach=norm):

- `quick-reviewer` (always) — mid tier
- `broad-reviewer` (always) — mid tier
- `adversarial-reviewer` — 119 changed executable lines (≥50) — session model
- `dotnet-reviewer` — C# files present (hard gate) + idiom surface: nullable annotations, pattern matching, `HashSet<T>` equality semantics — mid tier
- `test-reviewer` — test files present (hard gate) — mid tier
- `knowledge-reviewer` — substantive change embedding non-obvious null-semantics assumptions — session model
- `consistency-reviewer`: dropped — roster N=6 (derived: 119 executable lines): ranked last among gate-matched specialists
- `design-reviewer`: skipped — change confined to a method body; no public contract, data model, or concurrency surface change
- `performance-reviewer`: skipped — compile-time expression rewrite; no DB query execution, I/O loop, async, or caching in the diff
- `security-reviewer`: skipped — no trust-boundary trigger
- `spec-compliance-reviewer`: skipped — no spec found (hard gate)
- `data-migration-reviewer`: skipped — no migration artifacts (hard gate)
- `prior-feedback-reviewer`: skipped — local commit range, no PR threads (hard gate)
Build pre-flight passed (exit 0). Now verifying the converged finding empirically.
Test projects fail to compile under the available SDK (pre-existing errors in untouched files). Building a standalone probe outside the repo instead.
**Confirmed empirically.** Probe 1 reproduces a wrong result. Now running the control probe per Step 4.5.
Tree restored byte-identical. Verifying the remaining secondary claims directly.
Now writing the consolidated report.
✅ Review complete: `.decaf/code-reviews/CODE_REVIEW_2026-08-18_11-15-37.md`

## Verdict: ❌ NEEDS_CHANGES

**One Critical defect, confirmed by execution.**

### #1 🔴 `src/EFCore.Relational/Query/SqlNullabilityProcessor.cs:626` — wrong query results

`NullPropagatedOperands` recurses into **every** `SqlBinaryExpression` with no operator filter. `IsValidOperator` permits `AndAlso` and `OrElse`, through which SQL NULL does not propagate (`NULL OR TRUE = TRUE`, `NULL AND FALSE = FALSE`). The optimization therefore deletes a load-bearing `IS NOT NULL` guard.

The file's own `ProcessNullNotNull` (line 2314) already guards this exact pair, with the comment *"for AndAlso, OrElse we can't do this optimization"*. The new code has no equivalent.

I reproduced it against SQLite with EF Core built from this changeset:

```sql
-- x.NullableBoolA != null ? (bool?)(x.NullableBoolA.Value || x.BoolA) : null
SELECT ..., "e"."NullableBoolA" OR "e"."BoolA" AS "V"   -- guard gone
```

| `NullableBoolA` | `BoolA` | database | correct |
|---|---|---|---|
| NULL | true | **True** | NULL |
| NULL | false (`&&` variant) | **False** | NULL |

Control run: adding the operator guard restores the CASE, removes both mismatches, and leaves the intended `Add` optimization intact. The working tree was restored byte-identical.

The optimized CASE also reaches `WHERE` (see the regenerated `Null_propagation_optimization5/6` baselines), so this changes which rows match — including under `ExecuteDelete`/`ExecuteUpdate`.

**Fix:** allow-list the null-propagating operators rather than deny-listing, so a future operator addition fails closed.

### Also
- 🟡 **#2** `NullSemanticsQueryTestBase.cs:2250` — all five new tests use only NULL-propagating operators (`~`, `+`); the one family the code gets wrong is the one family untested. The `SqlFunctionExpression.Instance` arm is likewise uncovered.
- 🟡 **#3** `SqlNullabilityProcessor.cs:617` — the 3VL soundness invariant is written down nowhere; nothing signals that adding an operator obliges revisiting this function.
- 🟢 **#4** `:595` — `null`-means-vacuously-TRUE sentinel documented only by a trailing `// true`, thirty lines from where `null` means the opposite.
- Plus 1 pre-existing (`SqlConstantExpression.GetHashCode` contract) and 3 minor (stale `// issue #16050` markers, test naming, no SQLite `AssertSql` coverage).

**Refuted:** the `??`/`Coalesce` counterexample one reviewer raised — I probed it, and the guard is correctly preserved (`??` becomes a COALESCE function with `argumentsPropagateNullability: [false, false]`).

Two caveats on method: the functional test projects do not compile under the SDK available here (pre-existing errors in files this change does not touch), so probes ran as a standalone program outside the repo; and clustering/screening were done inline rather than dispatched. Both are recorded in the report's anomalies section.

