I'll start by invoking the review-pr skill.
Diff is scoped: one source file (`SqlNullabilityProcessor.cs`) plus test baselines. Dispatching the review agents in parallel now, and investigating the optimizer myself concurrently.
All six agents are running. Meanwhile, let me verify the soundness question myself.
Confirmed the ordering: search-condition conversion runs *after* nullability processing, so bare boolean binaries can be CASE results. Let me verify empirically with a scratch project outside the repo.
Confirmed a real correctness regression. Let me verify it's introduced by this change by running the same probe against the base commit.
Base is correct, head is wrong — a genuine regression. Let me broaden the probe to find the full blast radius.
Two more mismatches — including a **WHERE clause returning extra rows**. Confirming against base:
My probe definitively confirms reachability. Let me verify two secondary claims while the remaining agents finish.
`Not` and comparisons are safe. Now checking whether SQL Server's search-condition conversion widens the blast radius — generating SQL only, no server needed.
The regression is broader on SQL Server. Let me check whether existing tests should have caught this.
Existing tests don't cover this shape (`negative1` uses a *different* column in the guard than in the result). Checking on the remaining agents:
The test projects don't build under the installed SDK 10 (pre-existing, unrelated to this diff). Let me see the remainder of the SQLite baseline diff while agents finish.
That hypothesis is refuted — no shaper issue. Waiting on the last three agents.
Two agents remain. My SQL Server evidence shows a case the operator allow-list alone wouldn't fix — let me nail that down precisely.
Three agents converged on the same critical bug with independent reproductions. Waiting on the last one.
Confirmed by executing the exact SQL Server-shaped SQL: `NULL` becomes `0`. Waiting on the final agent.
Confirmed pre-existing (2023). Checking the final agent:
I'll wait for the last agent to land before finalizing.
Five of six agents are in, all converging, and I have my own reproduction. Delivering the consolidated report now; the sixth (code-reviewer) is still running and I'll amend if it adds anything.

# PR Review Summary

**Change under review:** `git diff 051c33a79 afcfba2e9` — adds a null-propagation optimization to `VisitCase` that strips redundant `IS NOT NULL` checks from `CASE WHEN <test> THEN <result> ELSE NULL END`, plus 5 new tests and 6 files of updated SQL baselines.

**Verdict: do not merge.** The optimization is unsound and silently returns wrong data. I reproduced this against a real database, and confirmed the base commit is correct.

---

## Critical Issues (3)

### C1 — `NullPropagatedOperands` recurses into every binary operator, including ones that do not propagate NULL
`src/EFCore.Relational/Query/SqlNullabilityProcessor.cs:626-630`

```csharp
else if (expression is SqlBinaryExpression binary)   // no operator filter
{
    NullPropagatedOperands(binary.Left, operands);
    NullPropagatedOperands(binary.Right, operands);
}
```

The set built here means *"if this operand is NULL, the whole result is NULL"* — that implication is the entire safety argument for deleting `x IS NOT NULL` from the test. The unary arm immediately above (`:621-622`) is a careful allow-list (`Not`/`Negate`/`Convert`); the binary arm has none. `SqlBinaryExpression.IsValidOperator` (`src/EFCore.Relational/Query/SqlExpressions/SqlBinaryExpression.cs:82-107`) admits `AndAlso`, `OrElse`, and `Coalesce`, none of which propagate NULL: `NULL AND FALSE` = `FALSE`, `NULL OR TRUE` = `TRUE`, `COALESCE(NULL,1)` = `1`.

**Reproduced** (SQLite, real rows, LINQ-to-Objects as oracle; built from this commit's `src/`):

| Query | SQL at head | Row | Expected | Actual |
|---|---|---|---|---|
| `NBool != null ? (bool?)(NBool.Value \|\| BoolB) : null` | `SELECT NBool OR BoolB` | `NBool=NULL, BoolB=true` | `NULL` | **`True`** |
| `NBool != null ? (bool?)(NBool.Value && BoolB) : null` | `SELECT NBool AND BoolB` | `NBool=NULL, BoolB=false` | `NULL` | **`False`** |
| `NA != null ? (bool?)(NA == NB) : null` | `SELECT NA = NB AND NB IS NOT NULL` | `NA=NULL, NB=NULL` | `NULL` | **`False`** |

**It also corrupts filtering, not just projection.** `Where(x => (x.NA != null ? (bool?)(x.NA != x.NB) : null) == true)` becomes `WHERE NA <> NB OR NB IS NULL` and returns **row Id=1 (`NA=NULL, NB=NULL`), which must be excluded** — expected `[4]`, got `[1, 4]`.

Every one of these **matches at base commit `051c33a`** (the `CASE` wrapper is retained) and **mismatches at head**. Unambiguously introduced by this diff.

`Coalesce` is currently safe only by accident — `SqlExpressionFactory.Coalesce` (`src/EFCore.Relational/Query/SqlExpressionFactory.cs:485-511`) emits a `SqlFunctionExpression` with `argumentsPropagateNullability: [false, false]`, which the function arm correctly skips. Verified: it does not regress. But the type permits `SqlBinaryExpression{Coalesce}`, so this is one refactor (or one third-party provider) away from live.

**Fix:** allow-list the safe operators so a future addition to `IsValidOperator` fails closed, rather than blacklisting.

### C2 — On SQL Server the optimization is wrong even for operators that *do* propagate NULL
`src/EFCore.Relational/Query/SqlNullabilityProcessor.cs:576-591`

This is a second, independent defect, and **an operator allow-list does not fix it.**

`SearchConditionConvertingExpressionVisitor` runs *after* nullability processing (`src/EFCore.SqlServer/Query/Internal/SqlServerParameterBasedSqlProcessor.cs:45` — after `base.Optimize`). So during `VisitCase`, a `bool?` result is still a bare *predicate*; afterwards `ConvertToValue` (`src/EFCore.SqlServer/Query/Internal/SearchConditionConvertingExpressionVisitor.cs:40-50`) wraps it as `CASE WHEN <pred> THEN true ELSE false END`. That collapses `UNKNOWN` into **false**, destroying the NULL the outer guard used to preserve.

Generated SQL Server SQL for `x.NA != null ? (bool?)(x.NA == 1) : null`:

```sql
-- base 051c33a (correct)          -- head afcfba2 (wrong)
SELECT CASE                        SELECT CASE
  WHEN [NA] IS NOT NULL THEN CASE      WHEN [NA] = 1 THEN CAST(1 AS bit)
    WHEN [NA] = 1 THEN CAST(1 AS bit)  ELSE CAST(0 AS bit)
    ELSE CAST(0 AS bit)            END
  END
  ELSE NULL
END
```

Executing both shapes verbatim against `NA IN (NULL, 1, 2)`: base yields `[NULL, 1, 0]`, head yields `[0, 1, 0]`. The NULL row silently becomes `false`.

This hits **every** `bool?` projection guarded by `IS NOT NULL`, including plain comparisons (`>`, `==`) that are perfectly null-propagating in three-valued logic. SQLite is unaffected here because it renders booleans natively; the bug is provider-visible only on SQL Server. Confirmed via generated SQL plus direct execution of that SQL shape — I had no SQL Server instance, so the end-to-end run is by SQL semantics, not by round-tripping EF against the server.

**Fix direction:** the optimization must not fire when `clause.Result` is a search condition / boolean-typed, or must account for the later bit conversion.

### C3 — The result is specialized under the very test being deleted
`src/EFCore.Relational/Query/SqlNullabilityProcessor.cs:512-514` interacting with `:576-591`

The `WHEN` result is deliberately visited with the test's non-nullable-column knowledge in scope (`preserveColumnNullabilityInformation: true`, with the comment *"we can use column nullability information we got from visiting Test, in the Result"*). So `A == B` is specialized to `A = B AND B IS NOT NULL` — an `AndAlso` whose right arm exists *precisely* to convert `UNKNOWN` to `FALSE` under the guard. The new code then walks through that `AndAlso`, finds `A`, and deletes the guard the specialization was predicated on. **The optimizer invalidates its own premise.**

This is the root cause behind several C1 rows, and it means the allow-list is a patch over a premise violation rather than a fix. It is also nowhere documented, so the next person editing `:512` has no way to know they can break `:583`. Related: the block at `:578` never consults `allowOptimizedExpansion`, so it cannot distinguish a predicate context (where NULL→false is licensed) from a projection (where it is not).

---

## Important Issues (2)

### I1 — `func.Instance!` contradicts the established pattern in this same file
`src/EFCore.Relational/Query/SqlNullabilityProcessor.cs:633-636`

`SqlFunctionExpression`'s `[EntityFrameworkInternal]` public constructor (`src/EFCore.Relational/Query/SqlExpressions/SqlFunctionExpression.cs:189-227`) takes `instance` and `instancePropagatesNullability` as independent parameters and validates only argument arity — nothing rejects `instance: null, instancePropagatesNullability: true`. Line 2394 of this very file already guards correctly:

```csharp
if (sqlFunctionExpression is { Instance: not null, InstancePropagatesNullability: true })
```

The new code drops the `Instance: not null` half and silences the resulting warning with `!`. Failure mode is an `NRE` from inside a local function during query compilation. (The adjacent `!func.IsNiladic` guard at `:638` is correct — `IsNiladic` carries `[MemberNotNullWhen(false, ...)]` at `SqlFunctionExpression.cs:242`.)

### I2 — The tests are structurally incapable of catching this bug class
`test/EFCore.Relational.Specification.Tests/Query/NullSemanticsQueryTestBase.cs:2250-2294`

All five new tests project `int?` or `string`. **Not one projects a `bool?`** — which is where every failure above lives. The tests are otherwise good (`AssertQuery` compares live DB results against a LINQ oracle, the seed data is a full null cross-product, and SQLite inherits and executes them), so a single added test would have failed loudly at authoring time:

```csharp
x => x.NullableBoolA != null ? (bool?)(x.NullableBoolA != x.NullableBoolB) : null
```

The existing `Select_null_propagation_negative1/2` (`test/EFCore.SqlServer.FunctionalTests/Query/GearsOfWarQuerySqlServerTest.cs:1074, :1091`) look like they cover this but do not — they use a *different* column in the guard than in the result, so nothing can match the hash set. The PR adds zero negative tests.

Also untested: the `InstancePropagatesNullability` branch (`:633-636`, only reachable via spatial/hierarchyid providers), the niladic guard (`:638`), and the `right is null ? left` arm (`:608`).

---

## Suggestions (5)

- **Missed optimization — no-`ELSE` form skipped.** `src/EFCore.Relational/Query/SqlNullabilityProcessor.cs:578`. `IsNull(null)` is `false` (`:1633`), so `CASE WHEN x IS NOT NULL THEN x END` — semantically identical to `ELSE NULL`, and acknowledged as such at `:562` and `:573` — never optimizes. Widen to `(elseResult is null || IsNull(elseResult))`.
- **`null`-means-TRUE sentinel is undocumented and inverts local convention.** `:595`, `:600`, `:585`. Everywhere else in this method a null `SqlExpression?` means *absent* (`operand` `:505`, `elseResult` `:554`). The entire contract rests on the two-character comment `// true`. The file already has a canonical encoding (`IsTrue`/`Constant(true)`, used at `:521-532`). The `static` on the local function — an allocation micro-optimization — is what forced the sentinel into the return type.
- **9 stale `// issue #16050` comments.** The marker flags known-suboptimal baselines; this PR made the SQL beneath these optimal but left the comments: `GearsOfWarQuerySqlServerTest.cs:1018, :1031, :1044`; `TPTGearsOfWarQuerySqlServerTest.cs:1231, :1247, :1263`; `TPCGearsOfWarQuerySqlServerTest.cs:1410, :1429, :1448`. Still valid for `optimization2/3/4`.
- **Naming and structure.** `NullPropagatedOperands` (`:617`) is a noun phrase on a `void` procedure — every sibling helper is a verb (`DropNotNullChecks`, `TryMakeNonNullable`, `AddNonNullableColumn`). The tense is also backwards: these operands *propagate* null, matching EF's own `ArgumentsPropagateNullability`. Reversing that reading is precisely the C1 bug. `CollectNullPropagatingOperands` would be clearer.
- **O(n²) hashing on the compilation path.** `:619` inserts every traversed subtree into a `HashSet<SqlExpression>`, and no `SqlExpression` caches its hash code (`SqlBinaryExpression.cs:173`, `SqlUnaryExpression.cs:137` both recurse into children). Inserting an *n*-node result costs O(n²). Walking the test's 1-3 conjuncts against the result would be O(t·n) and allocation-free. The set is also built before it is known to be needed.

---

## Adjacent, out of scope

`src/EFCore.Relational/Query/SqlNullabilityProcessor.cs:539` passes `currentNonNullableColumnsCount` to `RestoreNullValueColumnsList` where `currentNullValueColumnsCount` is intended (compare the correct pairing at `:528-529`). `git blame` dates it to 2023-10-23 — **pre-existing, not this diff** — but the new optimization's correctness is now coupled to exactly this state tracking.

---

## Strengths

- The core idea is sound and valuable: the changed baselines collapse genuine noise (`Select_null_propagation_optimization7`, the identity `SELECT [c].[Name]` cases, `WHERE LEN(x) = 5`). I checked each changed baseline and all are semantically equivalent rewrites.
- Several scoping decisions are well judged: `testIsCondition` correctly restricts to searched `CASE`; `DropNotNullChecks` correctly declines to decompose `OrElse` *tests*; unrecognized nodes are treated as opaque (fail-safe, missed optimization only); the `SqlFunctionExpression { IsNullable: true }` filter is correct in both directions.
- `Is_not_null_optimizes_binary_op_with_partial_checks` is a genuinely good test — its baseline pins the asymmetric interaction with string-concat null protection.
- Tests use real behavioral assertions against a live DB, not SQL-text-only, and `AssertResultCount` prevents passing on an empty set.

---

## Recommended Action

1. **C2 first** — decide whether the optimization may fire at all on boolean/search-condition results. This constrains the shape of every other fix.
2. **C3** — document (or eliminate) the dependency on test-driven result specialization.
3. **C1** — add the operator allow-list; this also permanently closes the `Coalesce` hazard.
4. **I1** — `is { Instance: not null, InstancePropagatesNullability: true }`, matching `:2394`.
5. **I2** — add `bool?` negative tests *before* the fixes, so they demonstrably go red first.

Two notes on method: the repo's test projects do not compile under the installed SDK 10.0.203 (`test/EFCore.Specification.Tests/CustomConvertersTestBase.cs:1202`, CS0023 — pre-existing, unrelated to this diff), so all reproduction ran from standalone apps in `/tmp` project-referencing `src/`. The repo working tree was not modified; the base-commit comparison used `git archive` into `/tmp`.
That notification was my own timer, not the agent. The `code-reviewer` agent is still running — the report above stands on the five that completed plus my own reproduction. I'll amend if it surfaces anything new.
The final agent landed, confirming C1/C2 independently — but it contradicts two other agents on `func.Instance!`. Let me resolve that myself rather than take either at face value.
The final agent (`code-reviewer`) independently reproduced **C1** and **C2**, including the SQL Server projection collapse. Two amendments:

**I1 (`func.Instance!`) — resolved in favor of keeping it.** The agents disagreed; I checked the constructor directly. `SqlFunctionExpression`'s `[EntityFrameworkInternal]` public constructor (`src/EFCore.Relational/Query/SqlExpressions/SqlFunctionExpression.cs:207-226`) validates **only** argument arity:

```csharp
if (Arguments?.Count != ArgumentsPropagateNullability?.Count) { throw ... }
```

Nothing ties `InstancePropagatesNullability == true` to `Instance != null`, so the `!` at `:635` asserts an invariant the type does not enforce — and `:2394` in the same file already guards with `{ Instance: not null, InstancePropagatesNullability: true }`. The finding stands, but I'd downgrade it to **robustness/consistency**, not a live crash: no in-tree producer constructs that combination, so it is reachable only via a third-party provider or precompiled-query codegen.

**One claim I'm glad I left out.** `IsNull` (`:1633`) also matches a null-valued `SqlParameterExpression`, which would make this a parameter-value-dependent rewrite. It isn't reachable here — `VisitSqlParameter` (`:1552-1562`) rewrites null-valued parameters into null constants before `IsNull` ever sees one on this path.

Everything else in the report is unchanged. The consensus across all six agents plus my own base-vs-head reproduction is that **C1, C2, and C3 are wrong-data regressions introduced by this diff**, and the added tests cannot detect them because none projects a `bool?`.

One point of method worth flagging for whoever acts on this: the sixth agent proposed a *blacklist* (`is not (AndAlso or OrElse or Coalesce)`). I'd keep the allow-list recommendation instead — `SqlBinaryExpression.IsValidOperator` is a list that can grow, and a blacklist fails open when it does.

