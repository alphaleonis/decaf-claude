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
