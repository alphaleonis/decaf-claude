I'll run the code review skill as requested.
I'll start by gathering context on the changeset.
Let me gather key context before dispatching the review team.
Build passes. Dispatching the audit roster.

**Review team** (preset `audit`, explicit · `roster`=all gate-matched · `models`=high · `evidence`=any · `reach`=wide):
- `quick-reviewer`, `broad-reviewer` — always (floor)
- `dotnet-reviewer` — C# files present (hard gate) + idiom surface (audit opens judgment gate)
- `adversarial-reviewer` — 173 changed executable lines
- `test-reviewer` — test files present (hard gate)
- `knowledge-reviewer`, `consistency-reviewer`, `design-reviewer`, `performance-reviewer`, `security-reviewer` — audit opens all judgment gates
- `data-migration-reviewer`: skipped — no migration artifacts (hard gate)
- `spec-compliance-reviewer`: skipped — no spec discoverable (hard gate)
- `prior-feedback-reviewer`: skipped — local commit range, no PR threads (hard gate)
- `typescript`/`cpp`/`go`/`rust`-reviewer: skipped — no such files (hard gate)
All 10 reviewers returned with strong convergence on one Critical. Let me verify the crux claims directly.
Confirmed the mechanism. Let me verify empirically with a scratch project outside the repo (no repo files modified).
**Probe C confirms a wrong result.** Let me expand to pin down the full failure surface.
Empirically confirmed — four wrong-result cases and a wrong row set in WHERE position. Now confirming these are regressions introduced by this change, using an isolated worktree (working tree untouched).
Decisive: all five probes **match** at the parent commit and **mismatch** at the change under review. Cleaning up and verifying a few remaining claims.
Working tree verified clean and unmodified. Running a focused validation wave on the two design claims I haven't verified myself.
Both design Highs refuted — verified: `VisitUnary` at `SqlNullabilityProcessor.cs:2392-2429` already uses the reverse direction of those flags (pre-existing), and non-virtual private helpers are the file's norm. Writing the report.
✅ Review complete: `.decaf/code-reviews/CODE_REVIEW_2026-08-12_09-35-10.md`

**Verdict: ❌ NEEDS_CHANGES** — 1 Critical, 2 High, 4 Medium, 2 Low, 8 Minor.

## The finding that matters

`src/EFCore.Relational/Query/SqlNullabilityProcessor.cs:626` — `NullPropagatedOperands` recurses into **every** `SqlBinaryExpression` with no operator filter:

```csharp
else if (expression is SqlBinaryExpression binary)
{
    NullPropagatedOperands(binary.Left, operands);
    NullPropagatedOperands(binary.Right, operands);
}
```

`IsValidOperator` admits `AndAlso`, `OrElse`, `Coalesce` and the six comparisons. None propagate NULL — `NULL AND FALSE` = `FALSE`, `NULL OR TRUE` = `TRUE`, and comparisons yield `UNKNOWN`, which materializes as `false`. So the `IS NOT NULL` guard gets dropped when it was load-bearing.

**This isn't inferred — I ran it.** Rather than edit tracked test files, I built the assemblies from this tree and drove them from a scratch project in `/tmp` against SQLite, then repeated it against a `git worktree` at the parent commit. All five probes **match at `051c33a79` and mismatch at `afcfba2e9`**:

| Query | Expected | @ change | @ parent |
|---|---|---|---|
| `A != null ? (bool?)(A > 5 && IntB > 100) : null` | `NULL,NULL,False` | **`False,NULL,False`** | ✅ |
| `A != null ? (bool?)(A > 5 \|\| BoolB) : null` | `NULL,NULL,True` | **`NULL,True,True`** | ✅ |
| `A + IntB != null ? (bool?)(A == C) : null` | `NULL,NULL,True` | **`False,False,True`** | ✅ |
| **WHERE** `(A != null ? (bool?)(A > 5 \|\| BoolB) : null) == true` | ids `3` | **ids `2,3`** | ✅ |

The WHERE case is the worst: it returns a row it must not. EF global query filters are ordinary LINQ predicates, so for apps doing tenancy that way this is a row leak.

Notably, **the fix is already written 1700 lines below in the same file** — `ProcessNullNotNull:2314-2321` guards the analogous rule with `!= AndAlso && != OrElse` and the comment *"for AndAlso, OrElse we can't do this optimization"*.

## Other primary findings

- **High** — No negative test pins the boundary. All five new tests use only null-propagating operators (`~`, `+`, concat); nothing asserts the CASE is *preserved*. The seed data would have caught this had a test of the right shape existed.
- **High, pre-existing** — `:539` passes `currentNonNullableColumnsCount` to `RestoreNullValueColumnsList`. Dates to 2023; included under `reach=wide` because this change makes that state load-bearing for a semantic rewrite.
- **Medium** — Populate-then-check ordering plus recursive unmemoized `GetHashCode` (verified at `SqlBinaryExpression.cs:173`) → quadratic on left-deep concat chains, and ~80% of qualifying CASEs pay the walk for nothing.
- Plus: undocumented soundness invariant, the `null`-means-"statically true" sentinel, and `func.Instance!` dropping the `Instance: not null` check its sibling block at `:2394` performs.

## What validation killed

Two sole-finder **High** design findings were **refuted**: the "contract strengthening" claim (the reverse direction of those nullability flags was already load-bearing at `:2392-2429`, pre-dating this change) and the "no provider seam" claim (non-virtual private helpers are this file's norm). I also corrected one reviewer's claim that `??` reaches the unfiltered arm — `SqlExpressionFactory.Coalesce` emits a `SqlFunctionExpression`, so Coalesce is safe in-box and only latent via `MakeBinary`.

Two caveats on this run: the repo's own test suites were **never executed** (they need SQL Server, unavailable here), and I clustered/screened inline instead of dispatching those agents — both recorded in the report. The working tree is unmodified (`git status` clean, HEAD still `afcfba2e9`); the only new file is the report itself.

