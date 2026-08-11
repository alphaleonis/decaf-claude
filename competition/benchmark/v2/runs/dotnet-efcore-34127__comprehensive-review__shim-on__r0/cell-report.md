I'll run the comprehensive review skill as requested.
I'll start with Phase 0 pre-flight. Since `--local` is passed, provider operations are skipped entirely.
Change is small and focused. Launching the review agent roster now.
**Confirmed empirically.** Now verifying this is a regression introduced by this change, not pre-existing — building the base commit in a separate worktree.
Review complete. All 7 agents returned; the headline finding was reproduced against a live database.

---

# Comprehensive Review — `051c33a79b...afcfba2e91` (dotnet/efcore)

> Local review. No provider operations attempted; nothing posted, nothing modified. Working tree is clean.

## Summary

Adds a peephole optimization to `SqlNullabilityProcessor.VisitCase`: for a `CASE` with a single `WHEN` clause and an `ELSE NULL`, it collects the "null-propagated operands" of the `THEN` result and drops any `x IS NOT NULL` conjunct from the test when `x` is among them — collapsing e.g. `CASE WHEN c IS NOT NULL THEN LEN(c) ELSE NULL END = 5` to `LEN(c) = 5`. Plus 5 new specification tests and SQL baseline updates across SqlServer/TPC/TPT/Temporal/Sqlite GearsOfWar suites.

**Type:** refactor / query optimization · **Effort:** 4/5 — 73 production lines, but they encode a SQL three-valued-logic correctness argument in the query pipeline's hottest path.

## Walkthrough

| File | Change | Summary |
|---|---|---|
| `src/EFCore.Relational/Query/SqlNullabilityProcessor.cs` | +73 | The optimization + `DropNotNullChecks` / `NullPropagatedOperands` local statics |
| `test/EFCore.Relational.Specification.Tests/Query/NullSemanticsQueryTestBase.cs` | +46 | 5 new tests (unary, binary, partial, nested, mixed) |
| `test/EFCore.SqlServer.FunctionalTests/Query/NullSemanticsQuerySqlServerTest.cs` | +58 | SQL baselines for the 5 new tests |
| `.../{GearsOfWar,TPCGearsOfWar,TPTGearsOfWar,TemporalGearsOfWar}QuerySqlServerTest.cs`, `.../GearsOfWarQuerySqliteTest.cs` | −100/+25 | Existing baselines updated to the collapsed SQL |

---

## Review Findings

**Overall Risk: Critical** — this change silently returns wrong data for a realistic query shape.

### Critical (1)

**1. `NullPropagatedOperands` treats `AndAlso`/`OrElse` as null-propagating; the optimization then drops a required `IS NOT NULL` guard and changes query results** — `src/EFCore.Relational/Query/SqlNullabilityProcessor.cs:626`

```csharp
else if (expression is SqlBinaryExpression binary)   // ← no operator filter
{
    NullPropagatedOperands(binary.Left, operands);
    NullPropagatedOperands(binary.Right, operands);
}
```

The set is consumed at `:597` as "*if this operand is NULL, the whole result is NULL*" — the sole justification for dropping the guard. That implication fails for `AndAlso`/`OrElse` under SQL's three-valued logic: `NULL AND FALSE = FALSE`, `NULL OR TRUE = TRUE`. Both are valid `SqlBinaryExpression` operators (`SqlExpressions/SqlBinaryExpression.cs:88-97`), and C# `&&`/`||`/`&`/`|` over booleans map to them in value position too (`RelationalSqlTranslatingExpressionVisitor.cs:442-443`).

The same file already states this restriction verbatim 1,700 lines down — `SqlNullabilityProcessor.cs:2314-2321`: *"for AndAlso, OrElse we can't do this optimization"*. The new helper contradicts it.

**Verified, not inferred.** I built both commits against SQLite and compared each query's DB result to the LINQ-to-Objects oracle:

| Query | Base `051c33a79b` | Head `afcfba2e91` | Correct |
|---|---|---|---|
| `nbA != null ? (nbA.Value && BoolB) : null` | `null, null, False` ✅ | `False, null, False` ❌ | `null, null, False` |
| `nbA != null ? (nbA.Value \|\| BoolA) : null` | `null, null, True` ✅ | `null, True, True` ❌ | `null, null, True` |
| `niA != null ? (niA > 1 && BoolB) : null` | `null, null, False` ✅ | `False, null, False` ❌ | `null, null, False` |

Head emits `SELECT "e"."NullableBoolA" AND "e"."BoolB"` where base emitted the full `CASE ... ELSE NULL END`. Rows where the checked column is NULL now yield `false`/`true` instead of `null`. This is a **new regression**, not pre-existing — all three cases pass at the base commit.

**Fix:** gate the recursion, mirroring the existing guard at `:2314`:
```csharp
else if (expression is SqlBinaryExpression { OperatorType: not (ExpressionType.AndAlso or ExpressionType.OrElse) } binary)
```
An allow-list of provably propagating operators would be safer still, so a future addition to `IsValidOperator` doesn't silently opt in.

### High (1)

**2. Test gap that let finding #1 through: no test puts a boolean `AndAlso`/`OrElse` in the `THEN` result** — `test/EFCore.Relational.Specification.Tests/Query/NullSemanticsQueryTestBase.cs:2252-2296`

All five new tests use `~` (unary), `+` (arithmetic), or string concat as the result — every one of which genuinely propagates NULL. `AndAlso` appears only in the *test* position (`..._with_mixed_checks`, `:2290`). The fixture already seeds the triggering row (`NullSemanticsData.cs`, `nullableBoolValues` includes `null`), so a single `AssertQuery` case such as `x.NullableBoolA != null ? (x.NullableBoolA & x.NullableBoolB) : (bool?)null` would have failed against the in-memory oracle.

Also unexercised: `SqlFunctionExpression.InstancePropagatesNullability` (`:632`), and `OrElse` as the *outer test* — which currently falls through `DropNotNullChecks` safely (`:613`) but has nothing pinning that no-op down against a future "generalize AndAlso to any logical operator" refactor.

### Medium (3)

**3. `IsNull(elseResult)` is `false` for a `CASE` with no `ELSE` at all, so equivalent trees get different SQL** — `src/EFCore.Relational/Query/SqlNullabilityProcessor.cs:578`

`IsNull` (`:1633`) matches only a null `SqlConstantExpression` or a null-valued parameter; `elseResult == null` (no `ELSE` clause) fails the pattern. But `CASE WHEN t THEN r END` ≡ `CASE WHEN t THEN r ELSE NULL END`, and `VisitCase` itself treats them identically for nullability three lines earlier (`:562`, `nullable |= elseResult == null`). Missed optimization plus an internal inconsistency — SQL shape now depends on how the `CaseExpression` happened to be built upstream. Fix: `(elseResult is null || IsNull(elseResult))`.

**4. The correctness invariant is nowhere written down, and `null` is an undocumented tri-state sentinel** — `src/EFCore.Relational/Query/SqlNullabilityProcessor.cs:595-600, 617`

The rule that licenses the whole rewrite — *membership in `nullPropagatedOperands` means `x IS NULL ⇒ result IS NULL`* — appears in no comment. `DropNotNullChecks` returns `SqlExpression?` where `null` means "unconditionally true," explained only by `return null; // true` at `:600`; the `AndAlso` recursion at `:604-609` and the caller at `:585-588` both depend on that convention without restating it. `NullPropagatedOperands` is a noun-named `void` mutator with no summary at all. Finding #1 is precisely the mistake a written invariant would have caught at review time.

**5. The analysis is closed to providers, inside a `protected virtual` extensibility point** — `src/EFCore.Relational/Query/SqlNullabilityProcessor.cs:595-649`

`SqlNullabilityProcessor` is the documented provider surface (it exposes `VisitCustomSqlExpression` at `:466` and a `protected virtual` hook per node type). The new walk is two local statics knowing only `SqlUnaryExpression`, `SqlBinaryExpression`, and `SqlFunctionExpression` — it doesn't recognize in-box propagating nodes like `CollateExpression`, `AtTimeZoneExpression`, or `JsonScalarExpression`, and a provider wanting its own nodes recognized must copy the whole method. Fall-through is conservative (missed optimization, not unsoundness), so this is a design/consistency point, not a bug.

### Low (2)

**6. The lead comment materially understates what the code does** — `src/EFCore.Relational/Query/SqlNullabilityProcessor.cs:576`

`// optimize expressions such as expr != null ? expr : null` reads as a narrow identity special case. The code is a general recursive null-propagation analysis that strips *each* redundant conjunct from an arbitrary `AndAlso` chain. A reader who trusts the comment will not expect the tree walk — and will not think to ask which operators are safe to walk.

**7. `MakeBinary(ExpressionType.Coalesce, ...)` can construct a raw `Coalesce` binary the walk would mis-handle** — `src/EFCore.Relational/Query/SqlExpressionFactory.cs` (`MakeBinary`), consumed at `SqlNullabilityProcessor.cs:626`

Defensive only. In-box, `??` always goes through `SqlExpressionFactory.Coalesce`, which builds a `SqlFunctionExpression("COALESCE", argumentsPropagateNullability: [false, false])` — correctly *not* recursed into by the `:631` branch. I verified this at runtime: `niA != null ? (niA ?? 0) : null` is left un-optimized on both commits and returns correct results. But `MakeBinary` accepts `ExpressionType.Coalesce` and returns a bare `SqlBinaryExpression` with no routing, so excluding `Coalesce` alongside `AndAlso`/`OrElse` in the fix for #1 costs nothing.

> Two agents reported a `Coalesce`-in-`THEN` data-corruption scenario as Critical/High. **That claim is refuted** — see the runtime evidence above. Reporting it would have been a false positive.

The `// TODO: optimize expr == null ? null : expr` at `:577` was checked against house style: `src/EFCore.Relational` carries ~55 bare TODOs without issue links. Not a finding.

## Positive Observations

- The `SqlFunctionExpression` branch (`:631-646`) is exactly right — it consults `IsNullable`, `InstancePropagatesNullability`, and per-argument `ArgumentsPropagateNullability` rather than assuming. That discipline is why `COALESCE` is safe; the binary branch simply doesn't follow it.
- `SqlUnaryExpression` recursion is correctly limited to `Not`/`Negate`/`Convert` and correctly excludes `Equal`/`NotEqual` (`IS NULL`/`IS NOT NULL` never produce NULL).
- Unknown node types fall through without recursing — the default is "no optimization," not "assume propagation."
- `DropNotNullChecks` handles only `AndAlso`, leaving `OrElse` alone — the correct conservative direction on the consumer side.
- Placement is right: after when-clause pruning and after the `whenClauses.Count == 0` early return, so it can't resurrect eliminated clauses.
- Every updated GearsOfWar/Sqlite baseline was hand-traced and is semantically correct — all involve `LEN`/`CAST`/string-concat results that genuinely propagate NULL. None are affected by finding #1.
- `HashSet<SqlExpression>` works as intended: `ColumnExpression`, `SqlUnaryExpression`, `SqlBinaryExpression`, and `SqlFunctionExpression` all override structural `Equals`/`GetHashCode`.

## Recommended Actions

1. **Block on #1.** Exclude `AndAlso`/`OrElse` (and defensively `Coalesce`) from the binary recursion at `:626`, or switch to an explicit allow-list.
2. **Add the regression test from #2** before re-review — a `bool?` result built with `&`/`|` over the null-checked column, asserted via `AssertQuery` so the in-memory oracle distinguishes `null` from `false`.
3. Write the invariant above `NullPropagatedOperands`, rename it to a verb, and document the `null`-means-`true` return of `DropNotNullChecks` (#4).
4. Accept `elseResult is null` in the `:578` guard (#3).
5. Decide explicitly whether the analysis should be a `protected virtual` provider hook or is intentionally closed (#5); widen the lead comment at `:576` (#6).

---

**Agents:** pr-summarizer, code-reviewer, architecture-reviewer, blind-hunter, edge-case-hunter, adversarial-general, comment-analyzer, pr-test-analyzer. Skipped: security-reviewer (no trust-boundary surface in the diff), issue-linker (`--local`), type-design-analyzer (no type definitions), silent-failure-hunter (no error-handling constructs), CVE check (no dependency manifests changed).

**Verification performed:** built `EFCore.Sqlite.Core` at both commits and ran 5 queries against in-memory SQLite, comparing DB results to the LINQ-to-Objects oracle. Scratch projects removed; repo working tree unmodified.
A late agent reported an escalation to the critical finding — that no user-written `&&` is needed to trigger it. Verifying that claim before amending.
The claim holds. Amending the report — this materially widens the blast radius of the critical finding.

## Addendum to Finding #1 — escalation (verified)

**No user-written `&&` is required to trigger the bug.** EF's own null-semantics compensation emits the dangerous `AND` shape.

`src/EFCore.Relational/Query/SqlNullabilityProcessor.cs:513-514` visits the `THEN` branch with `preserveColumnNullabilityInformation: true`, so a comparison inside the result is rewritten *using* the knowledge the guard provides. The new optimization then deletes the guard that rewrite depends on.

```csharp
x => x.NullableIntA != null ? (bool?)(x.NullableIntA == x.NullableIntB) : null
```

| | SQL emitted | Result | Correct (LINQ oracle) |
|---|---|---|---|
| Base `051c33a79b` | `CASE WHEN A IS NOT NULL THEN A = B AND B IS NOT NULL ELSE NULL END` | `null, null, True, False` ✅ | `null, null, True, False` |
| Head `afcfba2e91` | `SELECT A = B AND B IS NOT NULL` | `null, **False**, True, False` ❌ | |

Row 2 is `A = null, B = null`: the ternary's condition is false, so the answer is `null`; head returns `false`. Executed against SQLite on both commits; repo left clean.

So the trigger is not "the user wrote `&&` inside a null-guarded ternary" — it is **"the user wrote a guarded comparison between two nullable columns,"** which is the single most idiomatic shape this optimization targets. Severity stands at Critical; likelihood of being hit in real queries is much higher than my original write-up implied.

The fix is unchanged (gate the recursion at `:626`), but this makes the case for an **allow-list** of provably-propagating operators rather than a deny-list: the compensation logic can synthesize `AndAlso` nodes that were never in the user's expression tree.

## One additional item, explicitly unverified

**[Unverified] Possible broader SQL Server exposure** — `src/EFCore.SqlServer/Query/Internal/SearchConditionConvertingExpressionVisitor.cs:41-51`

`ConvertToValue` wraps a search condition used in value position as a two-arm `CASE WHEN <cond> THEN 1 ELSE 0 END`, which has no `NULL` arm and therefore maps `UNKNOWN → false`. The suggestion is that on SQL Server this collapses `null` to `false` for *any* boolean-typed `THEN` branch, even after finding #1 is fixed.

I could not test this — no SQL Server instance is available, and my SQLite reproductions cannot exhibit it (SQLite has no search-condition/value split). I also have **not** established whether this is introduced by this change or pre-existing at the base commit; it may well be the latter, in which case it is out of scope here. Treat it as a question to answer with a SQL Server run, not as a finding: add `x != null ? (bool?)(x == <const>) : null` to `NullSemanticsQuerySqlServerTest` and compare against the oracle on both commits.

Everything else in my previous report stands unchanged, including the refutation of the `Coalesce`-in-`THEN` data-corruption claim (`COALESCE` is a `SqlFunctionExpression` with `argumentsPropagateNullability: [false, false]`; verified un-optimized and correct at runtime on both commits).

