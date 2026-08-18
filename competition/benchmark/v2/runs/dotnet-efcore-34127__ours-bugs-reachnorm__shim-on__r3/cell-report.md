I'll start by invoking the requested skill.
Review team (preset `bugs` — single seat · roster=1 · seat on session model · evidence self-calibrated · reach=norm):
- solo-reviewer (the preset's single seat) — session model
- wave agents: not evaluated — bugs is a single-seat path (use `bugs roster=N` for the wave)

Spec: none found. Pre-flight: skipped (single-seat path runs its own targeted gates).
✅ Review complete: `.decaf/code-reviews/CODE_REVIEW_2026-08-18_22-56-11.md`

**Mode**: `bugs` (single seat, roster=1) · reach=norm · `--report` · no spec found · no prior reviews (Step 7 skipped).

**Verdict: ❌ NEEDS_CHANGES** — 1 Critical, 1 Medium, 1 Low, 3 Minor, plus 1 pre-existing.

## #1 🔴 Critical — `src/EFCore.Relational/Query/SqlNullabilityProcessor.cs:626`

`NullPropagatedOperands` recurses into both operands of *every* `SqlBinaryExpression` without checking `OperatorType`. `SqlBinaryExpression.IsValidOperator` admits `AndAlso` and `OrElse`, and neither propagates NULL from both operands in three-valued logic (`NULL AND FALSE = FALSE`, `NULL OR TRUE = TRUE`). The optimization therefore drops the `IS NOT NULL` guard on boolean-typed WHEN results where it is load-bearing, and the CASE collapses to an expression returning `false`/`true` where it previously returned NULL.

This changes `WHERE` row sets, not just projected values — and it does not require the user to write `&&`/`||`: EF's own null-semantics compensation injects `OR x IS NULL` into inequality translations, so plain `a != null ? (bool?)(a != b) : null` hits it.

The seat verified this empirically rather than by inspection: it built the Sqlite provider and ran a standalone repro against both this change and the base commit in a temporary worktree. Four scenarios (three projections, two `Where` clauses) produce results matching the in-memory oracle on `051c33a79` and diverging on `afcfba2e9`. Suggested fix is an explicit operator whitelist excluding `AndAlso`/`OrElse`/`Coalesce`.

## Supporting findings

- **#2 🟡 Medium** — `NullSemanticsQueryTestBase.cs:2250`: all five new tests use only unconditionally propagating operators (`~`, integer `+`, string concat). No boolean result, no comparison result, no `WHERE` position — the optimization's entire risk surface is untested, which is why #1 passed the suite.
- **#3 🟢 Low** — `SqlNullabilityProcessor.cs:578-584`: the operand `HashSet` is built before establishing that the test contains any `IS NOT NULL` to drop; `SqlExpression` hashing is structural and uncached, so this is O(N × depth) paid on every eligible CASE. Compile-time only, hence Low.
- **3 Minor (Consistency)** — `elseResult is null` (no ELSE) is semantically `ELSE NULL` but is not matched by the guard; the block states no soundness invariant; the two local functions are unreachable to providers overriding `VisitCase`.
- **P1 pre-existing** — `SqlNullabilityProcessor.cs:539` passes the non-nullable-columns watermark to `RestoreNullValueColumnsList`; the sibling call at :529 uses the correct one. Informational, outside this change's blast radius.

One report caveat: of the 8 parked items, one ("Probe not run") carries no closed-set parking tag. Per the single-seat rules it is counted in the header, not promoted or re-tagged. Nothing was posted or modified; the working tree is unchanged apart from the new review file.

