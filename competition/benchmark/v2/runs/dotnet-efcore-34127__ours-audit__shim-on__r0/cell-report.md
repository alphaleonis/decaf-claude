I'll run the code review skill as requested.
I'll start by gathering context on the changeset.
Build succeeds. Now dispatching the review team.

**Review team** (preset `audit` — explicit; roster uncapped, `models=high`, `evidence=any`, `reach=wide`):
- `quick-reviewer`, `broad-reviewer` (always)
- `knowledge-reviewer`, `consistency-reviewer` — substantive logic change
- `design-reviewer` — `protected virtual VisitCase` is provider-extensible surface
- `adversarial-reviewer` — 73 executable lines, semantics-critical
- `performance-reviewer` — recursive tree walk in query compilation
- `dotnet-reviewer` — C# present, pattern matching / collection expressions / nullable
- `test-reviewer` — test files present (hard gate)
- `security-reviewer` — SQL generation surface (audit opens judgment gates)
- Skipped: `spec-compliance-reviewer` (no spec), `data-migration-reviewer` (no migrations), `prior-feedback-reviewer` (not a PR), `typescript`/`cpp`/`go`/`rust`-reviewer (hard gate)
All ten reviewers returned. Verifying tree integrity and independently confirming the headline claim.
Tree clean and unmodified. Now running my own independent repro to confirm the headline finding.
Confirmed independently — the optimization produces wrong results and changes WHERE row visibility. Verifying two secondary claims directly.
Two claims verified directly (line 2394 canonical guard confirmed; Sqlite `ef_sum` override returns a COALESCE function node, so that example is actually safe). Dispatching one validator on the remaining unsettled claim.
Validator **refuted** the "test-as-premise" finding — the new block runs after `RestoreNonNullableColumnsList` (line 565), and every premise-driven elision removes *non*-strictness, so it makes the emitted expression more null-propagating, not less. Writing the report.
✅ Review complete: `.decaf/code-reviews/CODE_REVIEW_2026-08-11_17-37-06.md`

No source file was modified — the only working-tree change is the untracked report directory.

## Verdict: ❌ NEEDS_CHANGES

**The optimization is unsound and produces silently wrong query results.** I confirmed this by execution, not inference.

### The defect — `SqlNullabilityProcessor.cs:626`

`NullPropagatedOperands` recurses into **every** `SqlBinaryExpression` operator:

```csharp
else if (expression is SqlBinaryExpression binary)   // no operator filter
```

`IsValidOperator` admits `AndAlso`, `OrElse` and `Coalesce`, none of which satisfy the required `e IS NULL ⟹ R IS NULL` under three-valued logic. So an operand reachable only through one of them gets admitted, `DropNotNullChecks` deletes its guard, and the CASE collapses to something with different semantics. The file already states the rule this violates, at line 2321: `// for AndAlso, OrElse we can't do this optimization`.

Executed against SQLite built from this tree:

```
x.NullableIntA != null ? (bool?)(x.NullableIntA > 0 || x.IntB > 0) : null
  → SELECT "NullableIntA" > 0 OR "IntB" > 0      server=True  correct=NULL

.Where(x => (…same…) == true)
  → WHERE "NullableIntA" > 0 OR "IntB" > 0       server=[1,2] correct=[2]
```

The WHERE case matters most: EF applications routinely express row-level authorization as such predicates, so `NULL → TRUE` is a fail-open row-visibility change. The unary arm (whitelisted) and function arm (consults `ArgumentsPropagateNullability`) are both correct — only the binary arm is blanket. Fix is an operator allowlist with a non-recursing `default`.

### Why CI is green — `NullSemanticsQueryTestBase.cs:2250`

All five new tests project `~int?`, `int?+int?`, or string concat — every one genuinely strict. No `bool?` projection, no `&&`/`||`/`??` in a result, no WHERE-position test, and no negative test pinning that the CASE is *retained*. The suite is structurally incapable of failing on the defect.

### Also worth acting on
- **`:539`** — `RestoreNullValueColumnsList(currentNonNullableColumnsCount)` passes the wrong counter (pre-existing, `17a9035ad`; sibling lines 529 and 566 both pair correctly).
- **`:576`/`:617`** — the soundness invariant is written down nowhere, which is precisely how the binary arm diverged from the rules `ProcessNullNotNull` already encodes 1,700 lines below.
- **`:633`** — `func.Instance!` drops the `Instance: not null` half of the canonical guard at line 2394.

### One notable refutation
Three reviewers (one rating it Critical) claimed dropping the test invalidates the `_nonNullableColumns` premise the result was simplified under. **Refuted** — the new block runs *after* `RestoreNonNullableColumnsList` at line 565, and every premise-driven elision removes *non*-strictness, making the emitted expression more null-propagating, not less. A 30-query battery found only `AndAlso`/`OrElse`-topped mismatches, all subsumed by the allowlist fix. Recorded in Considered But Not Flagged rather than reported.

