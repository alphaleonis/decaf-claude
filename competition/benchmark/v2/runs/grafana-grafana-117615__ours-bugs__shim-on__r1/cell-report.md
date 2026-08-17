I'll run the code-review skill as requested.
I'll start by gathering context on the changeset.
**Review team** (preset `bugs` — explicit · roster N=4 (derived: ~120 executable lines, capped at 4 by `bugs`) · models=low · evidence=strong · reach=narrow):

- `quick-reviewer` (always) — mid tier
- `broad-reviewer` (always) — mid tier
- `adversarial-reviewer` — ~120 changed executable lines ≥ 50 — session model
- `test-reviewer` — test files present in changeset (hard gate) — mid tier
- `typescript-reviewer`: dropped — roster N=4 (derived): ranked below the 2 specialists kept (TS idiom surface traded for the cap)
- `consistency-reviewer`, `knowledge-reviewer`: dropped — roster N=4: ranked last under `bugs`
- `design-reviewer`: skipped — no public API/contract, data model, or concurrency surface change
- `security-reviewer`: skipped — no trust-boundary trigger (client-side construction of the user's own SQL expression)
- `performance-reviewer`, `data-migration-reviewer`, `spec-compliance-reviewer`, `prior-feedback-reviewer`, other stack reviewers: skipped — hard gates unmet

Pre-flight: `yarn install --immutable` is running in the background; no gate results available at dispatch, so reviewers reason statically and nominate probes.
Install finished. Now running the nominated probes (I'm the only actor on the tree).
Probes confirmed the crash and the DAG mis-parse. Dispatching validators on the two findings whose consequence chains rest on static reading.
✅ Review complete: `.decaf/code-reviews/CODE_REVIEW_2026-08-17_19-09-06.md`

No previous reviews exist in this repo, so the Recurring Findings step was skipped. Working tree is otherwise untouched — only the report was added; both probe test files were created untracked and deleted.

## Verdict: ❌ NEEDS_CHANGES — 1 Critical, 1 High, 3 Medium, 1 Minor

**#1 🔴 Critical — `SqlExpr.tsx:81` throws during render when the expression has no sibling query.** `vars[0]` is `undefined` when `refIds` is `[]`, and `isValidIdentifier` calls `identifier.toUpperCase()` unguarded (`mysql/sqlUtil.ts:54`). Before the change the plain interpolation rendered `"undefined"`; now it crashes. Reproduced:
```
TypeError: Cannot read properties of undefined (reading 'toUpperCase')
  at isValidIdentifier (public/app/plugins/datasource/mysql/sqlUtil.ts:54:61)
  at SqlExpr (.../SqlExpr.tsx:81:31)
```

**#2 🟠 High — the backticked `FROM` target breaks the alerting DAG, so the expression stops being evaluated.** `cleanTableName` (`dag.ts:198`) strips `['"()]` but not backticks. Measured: `` FROM `left` `` → `["`left`"]` (was `["left"]` — a regression for reserved-word/hyphenated refIds, which the rename input permits), and `` FROM `gdp per capita` `` → `` ["`gdp"] `` — so the targeted bug is **not** fixed on the alerting path. Confirmed end-to-end through `graph.link` → `createDAGFromQueriesSafe` → `AlertingQueryRunner.prepareQueries`.

**#3–#5 🟡 Medium** — both new test files fail `prettier:check` (CI-blocking, verified); `fetchSQLFields` never unquotes the identifier read back from the editor, so column autocomplete builds a garbage meta query (the parser hands it a lone backtick); and the new call at `metaSqlExpr.ts:15` binds to the file's own weaker helper rather than the reserved-word-aware one the other two call sites import. The last two sit behind the default-off `sqlExpressionsColumnAutoComplete` toggle and fail silently.

Two caveats on scope worth flagging: the roster cap dropped `typescript-reviewer` even though the diff is entirely TS/TSX, and clustering/screening ran inline rather than as separate agents — both recorded in the report.

