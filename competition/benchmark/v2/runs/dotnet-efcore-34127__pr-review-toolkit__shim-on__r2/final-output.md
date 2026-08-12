The final agent (`code-reviewer`) independently reproduced **C1** and **C2**, including the SQL Server projection collapse. Two amendments:

**I1 (`func.Instance!`) — resolved in favor of keeping it.** The agents disagreed; I checked the constructor directly. `SqlFunctionExpression`'s `[EntityFrameworkInternal]` public constructor (`src/EFCore.Relational/Query/SqlExpressions/SqlFunctionExpression.cs:207-226`) validates **only** argument arity:

```csharp
if (Arguments?.Count != ArgumentsPropagateNullability?.Count) { throw ... }
```

Nothing ties `InstancePropagatesNullability == true` to `Instance != null`, so the `!` at `:635` asserts an invariant the type does not enforce — and `:2394` in the same file already guards with `{ Instance: not null, InstancePropagatesNullability: true }`. The finding stands, but I'd downgrade it to **robustness/consistency**, not a live crash: no in-tree producer constructs that combination, so it is reachable only via a third-party provider or precompiled-query codegen.

**One claim I'm glad I left out.** `IsNull` (`:1633`) also matches a null-valued `SqlParameterExpression`, which would make this a parameter-value-dependent rewrite. It isn't reachable here — `VisitSqlParameter` (`:1552-1562`) rewrites null-valued parameters into null constants before `IsNull` ever sees one on this path.

Everything else in the report is unchanged. The consensus across all six agents plus my own base-vs-head reproduction is that **C1, C2, and C3 are wrong-data regressions introduced by this diff**, and the added tests cannot detect them because none projects a `bool?`.

One point of method worth flagging for whoever acts on this: the sixth agent proposed a *blacklist* (`is not (AndAlso or OrElse or Coalesce)`). I'd keep the allow-list recommendation instead — `SqlBinaryExpression.IsValidOperator` is a list that can grow, and a blacklist fails open when it does.
