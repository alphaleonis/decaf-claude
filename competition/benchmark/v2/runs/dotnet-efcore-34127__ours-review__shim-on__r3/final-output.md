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
