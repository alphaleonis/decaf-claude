I'll start by invoking the requested skill.
I'll start by gathering context on the change under review.
Let me classify the changeset and run pre-flight gates.
**Review team** (preset `bugs` — explicit; axes: `roster` N=4 capped, `models=low`, `evidence=strong`, `reach=narrow`):

- `quick-reviewer` (always) — cheap tier
- `broad-reviewer` (always) — cheap tier
- `adversarial-reviewer` — 73 changed executable lines in a query-translation optimizer; rank-1 specialist — session model
- `test-reviewer` — hard gate: test files present (baseline SQL assertions encode the correctness claim) — cheap tier
- `dotnet-reviewer`: **dropped — roster N=4 (`bugs` cap)**: gate matched (C# + nullable-annotation idiom surface) but ranked below the two specialists kept. Coverage trade worth naming — EF Core idiom depth is directly relevant here.
- `design-reviewer`: skipped — change confined to internals of an existing `protected virtual` method, no contract change
- `security-reviewer`: skipped — no trust-boundary trigger
- `performance-reviewer`: skipped — compile-time expression walk, no runtime query/IO surface
- `knowledge-reviewer`, `consistency-reviewer`: dropped — roster cap; ranked last (0.17 / 0.00 drop cost)
- `spec-compliance-reviewer`, `data-migration-reviewer`, `prior-feedback-reviewer`: skipped — hard gates unmet (no spec, no migrations, local diff not a PR)

**Pre-flight**: `dotnet build src/EFCore.Relational` — succeeded, 0 warnings / 0 errors. Full functional suites not run (SQL Server variants need a server instance).
Two reviewers reported Critical semantic bugs, with the adversarial reviewer providing end-to-end reproduction. Let me verify the working tree and independently confirm.
Both failure classes independently reproduced on the head build. Now confirming they're introduced (not pre-existing) by building the base commit.
Independently confirmed: **base is clean on all 7 probes; head is wrong on 6.** Let me check two remaining details before consolidating.
✅ Review complete: `.decaf/code-reviews/CODE_REVIEW_2026-08-12_10-21-10.md`

## Verdict: ❌ NEEDS_CHANGES — 1 Critical

**`src/EFCore.Relational/Query/SqlNullabilityProcessor.cs:626`** — the new `VisitCase` optimization drops `IS NOT NULL` guards it must keep, and the query silently returns wrong data.

`NullPropagatedOperands` recurses unconditionally into both operands of *every* `SqlBinaryExpression`:

```csharp
else if (expression is SqlBinaryExpression binary)
{
    NullPropagatedOperands(binary.Left, operands);
    NullPropagatedOperands(binary.Right, operands);
}
```

But `SqlBinaryExpression` legally carries `AndAlso`, `OrElse`, `And`, `Or` and `Coalesce` (whitelist at `SqlBinaryExpression.cs:95-107`), none of which propagates NULL: `NULL OR TRUE` = TRUE, `NULL AND FALSE` = FALSE.

**Two families, one cause.** Boolean connectives written into the THEN branch are the obvious one. The wider one is comparisons: because the WHEN test is visited with `preserveColumnNullabilityInformation: true`, the THEN branch is compiled under the guard's non-null fact and `A == B` comes out *as* `A = B AND B IS NOT NULL`. That synthesized `AND` is then walked by the same recursion — so the everyday pattern `x.Nullable != null ? (bool?)(x.Nullable == y) : null` is affected too.

**Verified by execution, base vs. head.** I built commit `051c33a79` separately and ran identical LINQ over identical SQLite data through each. Base: 0 mismatches on all 7 probes (intact `CASE` every time). Head: wrong values on 6 of 7 — e.g. `nbA != null ? (bool?)(nbA.Value || BoolB) : null` yields `True` where base yields `null`. Worst case escapes the projection: a `Where` returns **24 rows against base's 18**. The arithmetic control probe stays correct.

The five new `Is_not_null_optimizes_*` tests all pass — every one uses a THEN branch that genuinely propagates NULL (`+`, `~`, `LEN`, `COALESCE`). None has a boolean-valued THEN or a comparison in the THEN, so the test set cannot fail on this.

Fix is an operator gate on the recursion (exclude `AndAlso`/`OrElse`/`Coalesce` and boolean-typed `And`/`Or`; keep integer bitwise and `ExclusiveOr`, which do propagate). Full detail and the dismissed findings are in the report.

Two things worth flagging about the run itself:

- **Coverage traded**: `dotnet-reviewer`'s gate matched but the `bugs` preset's roster cap of 4 dropped it. EF Core idiom depth was directly on-topic here.
- **No test baseline**: `test/EFCore.Specification.Tests` does not compile under the installed SDK 10.0.203 (pre-existing, unrelated to this diff), so the in-repo functional suites never ran. Verification used standalone probe apps under `/tmp` instead. Tracked source was unmodified throughout (`git diff HEAD` empty); an untracked `test_null_concat_probe.cs` at the repo root predates my probes and I left it alone.

