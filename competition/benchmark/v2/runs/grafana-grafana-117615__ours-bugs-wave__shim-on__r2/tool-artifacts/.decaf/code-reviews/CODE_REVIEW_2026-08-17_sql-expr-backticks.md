# Code Review

**Mode**: bugs (explicit) · roster N=4 (derived: ~135 executable lines incl. tests; `bugs` caps at 4) — 4 gate-matched agents dropped | **Reviewers**: quick-reviewer, broad-reviewer, adversarial-reviewer, test-reviewer | **Date**: 2026-08-17
**Source**: local commit range `bcca6eb9533af2185fc2a5234c4e9658c7ce76ca..9a73ede33d5b715c75e8de873e52c23d7874cb7e` (`8ca6d4b6 fix: parsing for table names with spaces in SQL expressions` + `9a73ede3 add: tests for sql editor expression backticks`) — proposed, not merged
**Scope**: 6 files changed, +135/-3 lines (production: 3 modified lines + 2 imports; the rest is new tests)
**Spec**: none found
**Axes**: roster=4 · models=low · evidence=strong · reach=narrow
**Validation**: 2 confirmed, 1 refuted, 0 uncertain, 2 waived (probe-confirmed / gate-verified)
**Pre-flight gates**: ran late — `node_modules` was absent at dispatch; `yarn install --immutable` completed (exit 0) after the wave launched. Then: jest on the 3 changed test files **PASS** (16/16); `prettier --check` on the new test files **FAIL** (2 files); `eslint` on the changed files **FAIL** (14 errors). See finding #2.

## Agent Selection Rationale

Preset `bugs` was given explicitly, so Step 2a.5 did not run. Roster cap N=4 derived from ~135 changed executable lines (tests included), which `bugs` caps at 4.

- `quick-reviewer` — always (review floor) — mid tier
- `broad-reviewer` — always (review floor) — mid tier
- `adversarial-reviewer` — ≥50 changed executable lines; rank-1 specialist by measured drop cost — session model (judgment tier)
- `test-reviewer` — hard gate: 3 test files in changeset; rank-2 specialist — mid tier
- `typescript-reviewer`: **dropped** — roster N=4: its hard gate matched (TS/TSX files present, unvalidated-runtime-boundary-data idiom surface) but it ranked below the 2 specialists kept. **Coverage traded for the cap** — this is a TS/JS-only change, so a stack reviewer was a defensible seat.
- `security-reviewer`: **dropped** — roster N=4: gate matched (SQL string built from non-constant identifier input at `metaSqlExpr.ts:15`), ranked below the 2 kept
- `knowledge-reviewer`, `consistency-reviewer`: **dropped** — roster N=4: ranked last under `bugs` (measured drop cost 0.17 and 0.00)
- `design-reviewer`: skipped — no public API/contract, data-model, module-boundary, or concurrency surface change
- `spec-compliance-reviewer`: skipped — no spec available (hard gate)
- `data-migration-reviewer`, `prior-feedback-reviewer`, `dotnet`/`cpp`/`go`/`rust` reviewers: skipped — hard gates not met

`models=low` policy applied: judgment agents (adversarial-reviewer) on the session model; volume agents (quick, broad, test) and all verification agents (validators) on the mid tier.

## Summary

| Severity | Count |
|----------|-------|
| 🔴 Critical | 0 |
| 🟠 High | 2 |
| 🟡 Medium | 1 |
| 🟢 Low | 0 |
| 🔵 Minor | 2 |

Critical/High/Medium/Low are **primary** findings and drive the verdict. **Minor** counts reported-but-non-blocking findings.

**Verdict**: ❌ NEEDS_CHANGES (2 High)

---

## Findings

### #1 🟠 High: `quoteIdentifierIfNecessary(vars[0])` throws a TypeError and fails the render when the SQL expression is the only query

| | |
|---|---|
| **File** | `public/app/features/expressions/components/SqlExpressions/SqlExpr.tsx:81` |
| **Category** | correctness / null-safety |
| **Confidence** | 100 |
| **Verified** | empirically — probe reproduced the crash; revert probe proved this line introduces it |
| **Found by** | adversarial-reviewer (High), quick-reviewer (High) |

**Issue:** `vars` is `refIds.map((v) => v.value!)` (line 61), and `refIds` is built by the caller as *all queries other than this expression* — `ExpressionQueryEditor.tsx:118`: `queries!.filter((q) => query.refId !== q.refId).map((q) => ({ value: q.refId, label: q.refId }))`. When the SQL expression is the only query in the panel or alert rule, `refIds` is `[]` and `vars[0]` is `undefined`.

The old code interpolated that directly (`${vars[0]}`), which harmlessly rendered the literal text `undefined` as the table name. The new code passes it to `quoteIdentifierIfNecessary`, which calls `isValidIdentifier`, whose second line is `RESERVED_WORDS.includes(identifier.toUpperCase())` — an unguarded property access on `undefined`. `initialQuery` is computed in the **component body**, not inside a hook, so the throw happens during render and takes the whole SQL expression editor down.

The `v.value!` non-null assertion at line 61 is what hides this from the type checker.

**Verification performed:** an untracked probe test rendering `<SqlExpr refIds={[]} … />` fails on current HEAD with:

```
TypeError: Cannot read properties of undefined (reading 'toUpperCase')
  at isValidIdentifier (public/app/plugins/datasource/mysql/sqlUtil.ts:54:61)
  at quoteIdentifierIfNecessary (public/app/plugins/datasource/mysql/sqlUtil.ts:45:10)
  at SqlExpr (public/app/features/expressions/components/SqlExpressions/SqlExpr.tsx:81:31)
```

The same probe **passes** once line 81 is reverted to `${vars[0]}`, confirming this change introduces the crash. A second probe case (`refIds={[{ label: 'no value here' }]}`, i.e. a refId with no `value`) fails identically. The working tree was restored byte-identical afterwards.

**Fix:**
```tsx
const tableName = vars[0] ? quoteIdentifierIfNecessary(vars[0]) : '';

const initialQuery = `SELECT
  *
FROM
  ${tableName}
LIMIT
  10`;
```
Or harden `isValidIdentifier` in `sqlUtil.ts` to guard its input. Note there is currently no test covering the empty-`refIds` case — worth adding alongside the fix.

---

### #2 🟠 High: The two new test files fail the repo's format and lint gates — CI-blocking

| | |
|---|---|
| **File** | `public/app/features/expressions/utils/metaSqlExpr.test.ts:3`, `public/app/features/expressions/components/SqlExpressions/CompletionProvider/sqlCompletionProvider.test.ts:11` |
| **Category** | build-breakage / convention |
| **Confidence** | 100 |
| **Verified** | empirically — both gates executed with the repo's own config |
| **Found by** | test-reviewer (Low — prettier half only), pre-flight gates (eslint half) |

**Issue:** Both new test files violate gates this repo enforces in CI. `AGENTS.md` documents `yarn lint` and `yarn prettier:write` as standard commands.

`yarn prettier --check` (trailing whitespace on blank lines inside both files):
```
[warn] public/app/features/expressions/utils/metaSqlExpr.test.ts
[warn] public/app/features/expressions/components/SqlExpressions/CompletionProvider/sqlCompletionProvider.test.ts
[warn] Code style issues found in 2 files.
```

`yarn eslint` — **14 errors**:
```
sqlCompletionProvider.test.ts
  11:78, 12:43, 12:65, 38:78, 39:43, 39:65  error  Unexpected any  @typescript-eslint/no-explicit-any

metaSqlExpr.test.ts
   3:1   error  There should be at least one empty line between import groups  import/order
  31:35, 31:51, 44:20, 46:50, 46:66, 62:50, 62:66  error  Unexpected any  @typescript-eslint/no-explicit-any
```

The changed **production** files are lint-clean; this is confined to the new tests. Only the `import/order` error is auto-fixable — the thirteen `as any` casts need real types, so this is not a pure formatting pass. Those casts are also what let the tests pass shapes the production callers cannot produce (see finding #3).

**Fix:** run `yarn prettier:write` on both files, add the missing blank line between import groups in `metaSqlExpr.test.ts:3`, and replace the `as any` casts with real types — `Partial<SQLQuery>` / `DataQuery[]` for `fetchSQLFields`, `CompletionProviderGetterArgs` (and `SelectableValue<string>[]` for `refIds`) for `getSqlCompletionProvider`.

---

### #3 🟡 Medium: Backtick-quoted table names do not round-trip — column autocomplete builds `SELECT * FROM ``` LIMIT 1` and passes an empty `queries` array

| | |
|---|---|
| **File** | `public/app/features/expressions/utils/metaSqlExpr.ts:15` (contributing cause at `CompletionProvider/sqlCompletionProvider.ts:27`) |
| **Category** | composition / incomplete-fix |
| **Confidence** | 75 |
| **Verified** | confirmed by validator; runtime output reproduced; all four links read in the installed dependencies |
| **Found by** | adversarial-reviewer (Medium) |

**Issue:** The change fixes the **write** side (backticks now go into the editor buffer) but not the **read** side that parses the table name back out of that buffer, so the column-autocomplete path mishandles exactly the identifiers this fix enables.

The chain, each link verified in the installed packages:

1. Monaco's mysql Monarch tokenizer splits `` `gdp per capita` `` into **three** tokens — `` ` `` (`identifier.quote`), `gdp per capita` (`identifier`), `` ` `` — `node_modules/monaco-editor/esm/vs/basic-languages/mysql/mysql.js:866-871`.
2. `@grafana/plugin-ui`'s `linkedTokenBuilder` creates one `LinkedToken` per Monaco token with no merging — `.../SQLEditor/utils/linkedTokenBuilder.js`.
3. `getTableToken` returns only `fromToken.getNextNonWhiteSpaceToken()` — a **single** token, here the lone opening backtick. An `identifier.quote` token is neither `isVariable()` nor `isKeyword()`, so it is returned rather than skipped. `defaultTableNameParser` then splits that one-character value on `.`, yielding `{ table: '`' }` — `.../SQLEditor/utils/tokenUtils.js`. The completion provider supplies no `tables.parseName` override, so this default applies (`SQLEditor.js:279`).
4. `SqlExpr.tsx` forwards it verbatim: `fetchSQLFields({ table: identifier.table }, queries)`.

Observed output from the real `fetchSQLFields`:

```
fetchSQLFields({table: '`'},                [{refId:'gdp per capita'}])
  -> rawSql = "SELECT * FROM ``` LIMIT 1"                 queries passed = []
fetchSQLFields({table: '`gdp per capita`'},  [{refId:'gdp per capita'}])
  -> rawSql = "SELECT * FROM ``gdp per capita`` LIMIT 1"   queries passed = []
```

Two separate faults in one call: the identifier is re-quoted rather than normalized, and the unchanged `queries.filter((q) => q.refId === query.table)` on the next line matches nothing, so no upstream data is sent with the metadata query. `sqlCompletionProvider.ts:36-40` swallows the resulting error and returns `[]`, so the user just sees no column suggestions and one malformed backend request per suggest trigger.

**Why this is introduced rather than pre-existing:** before the change, backticks reached the buffer only if a user typed them by hand; the change now emits them automatically for every space-containing table, both in the initial query template and in every accepted completion. The validator confirmed this clears the "introduced" bar even though a different, milder space-handling bug existed beforehand.

**Scope note (from the validator):** `sqlExpressionsColumnAutoComplete` is `Stage: Experimental`, `Expression: "false"` in `pkg/services/featuremgmt/registry.go:877-882` — **off by default**. That bounds real-world impact to users who explicitly opted in, and is the main reason this stays Medium.

**Note on the new test:** `metaSqlExpr.test.ts` passes `{ table: 'table with spaces' }` — a shape the only production caller cannot produce for a quoted table. That is why this round trip looks covered but is not.

**Fix:** normalize before re-quoting, and use the normalized value for the `queries` filter too. `mysql/sqlUtil` already exports `unquoteIdentifier` for exactly this ("remove identifier quoting from identifier to use in metadata queries"), and `mySqlMetaQuery.ts:39` is the precedent:
```ts
const table = unquoteIdentifier(query.table);
const queryString = `SELECT * FROM ${quoteIdentifierIfNecessary(table)} LIMIT 1`;
// ...
queries.filter((q) => q.refId === table)
```
Alternatively (or additionally) supply `tables.parseName` in the completion provider so quoted table tokens are reassembled into the full identifier — that is the more complete fix, since step 3 truncates the name before `fetchSQLFields` ever sees it.

---

## Minor Findings

### Consistency

- `public/app/features/expressions/components/SqlExpressions/CompletionProvider/sqlCompletionProvider.test.ts:31` — the second test (`'should use label if provided, otherwise value for table name'`) asserts only `.name`, never `.completion`. `name` is byte-identical before and after this change (only line 27's `completion` moved), so this test passes with the fix reverted and provides no regression protection for it. It also wraps its assertions in `if (resolveFunc) { … }` with no `expect(resolveFunc).toBeDefined()` guard, unlike the sibling test above it. Validator downgraded this from Medium to **Low**: the assertions are true, the title honestly describes what it covers, and `getSqlCompletionProvider` returns `tables: { resolve }` as an unconditional object literal — so the "zero assertions silently pass" scenario is structurally impossible today and the missing guard is an inconsistency rather than a live false-pass. (test-reviewer)
- `public/app/features/expressions/components/SqlExpressions/SqlExpr.tsx:13`, `CompletionProvider/sqlCompletionProvider.ts:9` — core feature code now imports a bundled datasource plugin's internal helper: `import { quoteIdentifierIfNecessary } from 'app/plugins/datasource/mysql/sqlUtil'`. Verified this is the only `public/app/features/**` → `public/app/plugins/datasource/mysql/**` import in the repo, and that **no lint rule blocks it** (the changed production files are eslint-clean), so this is a design concern rather than a violation. SQL Expressions is backed by its own Go engine (`pkg/expr/sql`, vitess), not the MySQL datasource, so the dependency is coincidental — a change to `mysql`'s `RESERVED_WORDS` or `isValidIdentifier` would silently alter SQL Expressions' generated queries. `SqlExpr.tsx` already imports from the shared `@grafana/sql`, which has no such helper (`grep -rn "quoteIdentifier" packages/grafana-sql/src` → nothing); that or `features/expressions/utils/` would be a more natural home. (broad-reviewer)

---

## Agent Summary

| Agent | Issues Found | Unique Issues |
|-------|:------------:|:-------------:|
| adversarial-reviewer | 2 | 1 |
| test-reviewer | 2 | 2 |
| quick-reviewer | 1 | 0 |
| broad-reviewer | 1 | 1 |
| **Total** | **5** | |

Notes:
- Refuted findings are excluded. broad-reviewer's High (#C2 below) was refuted, leaving it with one surviving finding.
- adversarial-reviewer was the only finder of #3, the finding that required tracing four dependency layers.
- test-reviewer's #2 was raised at Low (prettier only); the eslint half that lifts it to High came from the pre-flight gate run.

---

## Specialist Notes

### Considered But Not Flagged

**Refuted by the validation wave:**

- `metaSqlExpr.ts:15` — *"change leaves `metaSqlExpr.ts` on a weaker quoting rule than the two call sites it fixed; reserved-word table names stay unquoted"* (broad-reviewer High, quick-reviewer Medium — the only 2-finder cluster besides #1). **Refuted by validator:** before this commit all three call sites interpolated the table name with no quoting at all. For a bare reserved word such as `order`, the file-local regex-only helper at `metaSqlExpr.ts:114-116` returns it unquoted — byte-identical to the old `${query.table}`. I confirmed the runtime output: `fetchSQLFields({table:'order'}, …)` → `rawSql = "SELECT * FROM order LIMIT 1"`, the same string the pre-change line produced. The commit narrows a three-way failure to a one-way failure; under `reach=narrow` that is an incomplete fix (an absence), not a change-introduced defect. The `pre_existing: false` claim and the High severity were both unsupported.
  *The two reviewers' underlying observation is still true and worth acting on — `metaSqlExpr.ts` really does have a private duplicate helper that now diverges from the imported one, and unifying them is the natural companion to finding #3's fix. It is simply not a defect this change introduced.*

**Tiered down by the `evidence=strong` screen:**

- `metaSqlExpr.test.ts:53-65` — the third new test (`'should quote field names with spaces in the returned selectable values'`) exercises **field**-name quoting at `metaSqlExpr.ts:29`, which this change does not touch; it is coverage of pre-existing behavior, not a regression test for the fix. Correct and harmless; screen score ~30. (test-reviewer, Low)
- `test-reviewer` rated the missing `toBeDefined()` guard **Critical**. Not carried at that severity: the validator established the failure mode is structurally unreachable today. Merged into the Minor/Consistency entry above.

**Pre-existing, out of reach (`reach=narrow`) — recorded from reviewers' own sections:**

- Neither `quoteIdentifierIfNecessary` implementation escapes a backtick *inside* the value, so a refId like `` a`b `` yields `` `a`b` ``. Both function bodies predate the change, and the emitted text is SQL in the user's own editor that they can already edit freely — no new failure mode, no trust boundary crossed. (broad-reviewer, adversarial-reviewer)
- `SqlExpr.tsx:61`'s `refIds.map((v) => v.value!)` non-null assertion — the line is not in the diff; cited only as the reason finding #1 escapes the type checker. (quick-reviewer)
- `SqlExpr.tsx:81` uses `refId.value` while `sqlCompletionProvider.ts:26-27` uses `refId.label || refId.value`. Both production callers (`ExpressionQueryEditor.tsx:118`, `alerting/unified/components/expressions/Expression.tsx:100-103`) set `value` and `label` to the same `q.refId`, so the two strategies are currently equivalent; latent inconsistency only. The diff did not change which field is read. (broad-reviewer, adversarial-reviewer)
- `@grafana/plugin-ui`'s tokenizer could not extract a multi-word table name before this change either (unquoted `FROM gdp per capita` parses as `gdp`). The specific *new* malformed output is reported as #3; the general tokenizer limitation is pre-existing. (broad-reviewer)
- `SqlQueryActions` receives the quoted `initialQuery` but the raw unquoted `refIds={vars}` (`SqlExpr.tsx:233-234`), so GenAI-generated SQL may reference space-containing tables unquoted. An absence in an unchanged component. (adversarial-reviewer)
- `SQLEditor.js:286` appends a `" $0"` tab stop only when `completion === name`, which quoting now makes false for space-containing tables, so that trailing tab stop disappears for those completions. Cursor still lands at end of insert; cosmetic, below threshold. (adversarial-reviewer)
- `metaSqlExpr.test.ts`'s `uuid` `v4` mock is not load-bearing — the assertion uses `expect.objectContaining` and never checks `refId`. Dead setup, not a defect. (test-reviewer)
- `SqlExpr.test.tsx`'s new test reads `onChange.mock.calls[0][0]` after only `waitFor(() => expect(onChange).toHaveBeenCalled())`. This matches the file's existing first test (lines 78-93); consistent with local convention. (test-reviewer)
- `quoteIdentifierIfNecessary('')` at `sqlCompletionProvider.ts:27` returns a pair of empty backticks. Reachable only if a refId has neither `label` nor `value`; screen score 25. (quick-reviewer)

**Probes run (Step 4.5):** 5 nominated, 5 run, 0 skipped. All 3 revert probes confirmed their tests are genuine regression guards (each fails with its production line reverted); both round-trip probes reproduced the predicted output. Two extra probe cases were added by the orchestrator (`refIds` with a value-less entry; already-quoted table input). Working tree verified byte-identical to the change under review after every probe — `git diff --stat` empty, all probe files untracked and deleted.

---

## Session Metrics (--report)

Wave dispatched as a single message, 4 parallel reviewers, all `run_in_background: false`. Validation wave dispatched as a single message, 3 parallel validators. Figures below are the harness-reported values from each tool result, verbatim.

| Agent | Kind | Model tier | Tokens | Tool calls | Duration | Findings submitted |
|---|---|---|---:|---:|---:|---:|
| quick-reviewer | reviewer | mid | 82,540 | 10 | 158,007 ms | 2 |
| broad-reviewer | reviewer | mid | 126,086 | 35 | 520,020 ms | 2 |
| adversarial-reviewer | reviewer | session (judgment) | 88,584 | 21 | 251,342 ms | 2 |
| test-reviewer | reviewer | mid | 82,234 | 8 | 137,832 ms | 4 |
| validator (#2, refuted) | validator | mid | 62,950 | 6 | 76,672 ms | verdict: refuted |
| validator (#3, confirmed) | validator | mid | 71,457 | 18 | 107,288 ms | verdict: confirmed |
| validator (minor, confirmed) | validator | mid | 53,797 | 4 | 48,724 ms | verdict: confirmed (severity → Low) |

Totals: 7 agents, 567,648 subagent tokens, 102 tool calls.

**Steps skipped and why:**
- Step 4.9 clustering was done **inline by the orchestrator, not by a dispatched agent** — 10 raw findings across 4 reviewers, every one carrying a distinct `file:line` + category anchor. The mid-tier round trip would have cost more than the orchestrator thinking it saved. Recorded as a deviation from the skill's default. All 10 input findings landed in exactly one of 8 clusters; count asserted.
- Step 4.95 screening was likewise applied inline over 8 clusters rather than dispatched per cluster, for the same reason. Scores assigned: #1 = 95, #2 = 100, #3 = 85, reserved-word cluster = 70 (2 finders, promoted over the `strong` bar by corroboration, then refuted at validation), coupling = 45, test-guard = 55, test-insensitivity = 85, pre-existing-coverage test = 30. 4 clusters tiered down (2 to Minor, 2 to Considered But Not Flagged); nothing was dropped.
- Step 5.6 selection: #1 and #2 were **waived** — #1 is empirically probe-confirmed in both directions (stronger evidence than a validator opinion), #2 was verified by running the gates themselves. The remaining 3 clusters within 15 points of the bar, or carrying dissenting severities, were all validated.

**Anomalies:** 1. Pre-flight gates could not run before dispatch because `node_modules` was absent — reviewers were told so explicitly and instructed to reason statically and nominate probes rather than run installs in a shared tree. Gates ran after the wave joined; their results are folded into finding #2. No reviewer reported a build/test observation that later failed to reproduce. One stray file was created outside the repo during probe setup and immediately deleted; it never entered the repository.
