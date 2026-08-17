I'll invoke the skill first, then dispatch the reviewer subagent.
Reviewer report, verbatim:

---

## Review: SQL expression identifier quoting (`bcca6eb9..9a73ede3`)

**Inferred intent** (no written plan; derived from `8ca6d4b6` "fix: parsing for table names with spaces in SQL expressions" and the tests in `9a73ede3`): Grafana refIds are free-form user-editable strings (`public/app/features/query/components/QueryEditorRowHeader.tsx:51-68` validates only non-empty + uniqueness), so a refId like `gdp per capita` produces `SELECT * FROM gdp per capita`, which is a syntax error. The change backtick-quotes the refId in the three places the frontend emits it as a table name.

I verified the core premise end-to-end: I ran `TablesList` from `pkg/expr/sql/parser.go` against ``SELECT * FROM `gdp per capita` LIMIT 10`` and it correctly returns `["gdp per capita"]`. **The fix direction is right and the backend supports it.**

### Strengths

- Correct diagnosis and a minimal, surgical fix — 5 changed production lines, no backend changes (matches `AGENTS.md`'s "separate PRs for frontend and backend").
- All three emission sites in the diff are the right ones: initial query (`SqlExpr.tsx:81`), autocomplete insert text (`sqlCompletionProvider.ts:27`), and the metadata query (`metaSqlExpr.ts:15`).
- Reusing an existing helper rather than hand-rolling a regex is the right instinct, and the mysql helper is the stricter of the two available (it also handles reserved words).
- `TableDefinition.name` is left unquoted while only `completion` is quoted — the suggestion list still displays a clean name. That is a nicer UX than the mysql datasource's own `fetchMeta`, which displays the quoted form.
- Tests are meaningful assertions on real output strings (`rawSql`, `completion`, the generated expression), not mock-shape assertions. **All 16 tests in the three files pass** (`yarn jest` on each file).

### Issues

#### Critical

**1. `SqlExpr.tsx:81` — crashes the editor when `refIds` is empty (regression).**

```ts
const initialQuery = `SELECT\n  *\nFROM\n  ${quoteIdentifierIfNecessary(vars[0])}\nLIMIT\n  10`;
```

`vars = refIds.map((v) => v.value!)`, so `vars[0]` is `undefined` when `refIds` is `[]`. `quoteIdentifierIfNecessary(undefined)` reaches `sqlUtil.ts:54` `RESERVED_WORDS.includes(identifier.toUpperCase())` and throws — during render, unguarded.

**Verified empirically**, not inferred. In a throwaway worktree I rendered `<SqlExpr refIds={[]} …>`:
- At HEAD: `TypeError: Cannot read properties of undefined (reading 'toUpperCase')`, React unmounts the tree.
- At base `bcca6eb9`: renders fine, producing `FROM undefined`.

So this converts a cosmetic degradation into a hard crash of the expression editor / alert-rule editor. `refIds` is computed as `queries.filter((q) => q.refId !== query.refId)` (`ExpressionQueryEditor.tsx:118`, `alerting/…/Expression.tsx:100-102`), i.e. empty whenever the SQL expression is the only remaining query. The codebase already treats this as a live state — `GenAISQLSuggestionsButton.tsx:103` has `disabled={refIds.length === 0}` and both GenAI files use `refIds.length > 0 ? … : 'A'`.

**Fix:** `quoteIdentifierIfNecessary(vars[0] ?? 'A')` (matching the GenAI fallback), or guard the whole `initialQuery`. Add a `refIds={[]}` test — there is none.

#### Important

**2. `sqlCompletionProvider.ts:27` + `metaSqlExpr.ts:15,20` — quoting the table name breaks column autocomplete for exactly the names this PR fixes.**

The change emits backtick-quoted table names into the Monaco buffer, but nothing on the read-back path understands them:

- The editor is registered with `id: 'mysql'`, so Monaco's built-in mysql Monarch tokenizer applies. It tokenizes ``` `gdp per capita` ``` as **three** tokens — `identifier.quote`, `identifier`, `identifier.quote` (`node_modules/monaco-editor/esm/vs/basic-languages/mysql/mysql.js:866-871`).
- `SQLEditor.js:279` uses `customProvider.tables.parseName` if supplied, else `defaultTableNameParser`. This completion provider supplies no `parseName`, so the default runs: `getTableToken` takes the first non-whitespace token after `FROM` and `defaultTableNameParser` does `token.value.split('.')` (`tokenUtils.js:13-34`). For a quoted name that token is the bare backtick, yielding `{ table: '`' }`.
- That flows to `fetchSQLFields`, which re-quotes it (`metaSqlExpr.ts:15`) and filters `queries.filter((q) => q.refId === query.table)` (`metaSqlExpr.ts:20`) — a comparison that can never match a quoted or partial name.
- Even if the token were the full quoted string, `metaSqlExpr.ts:15` would double-quote it. I confirmed the resulting SQL is a hard parse failure: `TablesList` on ``SELECT * FROM ``gdp per capita`` LIMIT 1`` returns `error parsing sql: syntax error at position 24 near 'per'`.
- The failure is silent: `sqlCompletionProvider.ts:39` swallows it with `catch { return [] }`.

The mysql datasource's own provider handles this explicitly — `mysql/sqlCompletionProvider.ts:45,48,124-126` inspect `TokenType.IdentifierQuote` and pull the inner `TokenType.Identifier` value — which is why its metadata path then calls `unquoteIdentifier` (`sqlUtil.ts:59`, commented "remove identifier quoting from identifier to use in metadata queries"). This PR imports `quoteIdentifierIfNecessary` from that file but not its counterpart.

Severity is Important rather than Critical only because column autocomplete is gated on `sqlExpressionsColumnAutoComplete`, which is `FeatureStageExperimental` with `Expression: "false"` (`pkg/services/featuremgmt/registry.go:878-884`).

**Fix:** `unquoteIdentifier(query.table)` before both the re-quote at `:15` and the refId comparison at `:20`, and add a `tables.parseName` (or IdentifierQuote-aware token walk) to the expressions completion provider.

**3. Two divergent `quoteIdentifierIfNecessary` implementations are now in play.**

`SqlExpr.tsx:13` and `sqlCompletionProvider.ts:9` import the mysql one (valid-name check **plus** ~250 reserved words). `metaSqlExpr.ts:15` silently resolves to a *local* copy at `metaSqlExpr.ts:114-116` that has no reserved-word check. I ran both: a refId named `Order`, `Range`, `Key`, `System`, … is quoted in the initial query and the completion insert text, but left bare in the metadata query — `SELECT * FROM Order LIMIT 1`, a syntax error, again silently swallowed.

Whether or not you take the layering point in #7, the two call sites must agree. Pick one implementation.

**4. The two new test files fail CI lint and formatting.** Verified by running the repo's own commands:

```
yarn prettier --check  → [warn] metaSqlExpr.test.ts, sqlCompletionProvider.test.ts
yarn eslint            → 14 errors
```
- 13 × `@typescript-eslint/no-explicit-any` (`sqlCompletionProvider.test.ts:11,12,38,39`; `metaSqlExpr.test.ts:31,44,46,62`). This rule is `'error'` for `**/*.{js,jsx,ts,tsx}` with test files **not** in its ignore list (`eslint.config.js:557-569`). Note `consistent-type-assertions` *is* disabled for tests (`:571-578`), so `as SomeType` is fine — only `any` is banned. Use `as unknown as CompletionProviderGetterArgs`, or better, real typed fixtures.
- 1 × `import/order` (`metaSqlExpr.test.ts:3`).
- Trailing whitespace on 11 blank lines (`metaSqlExpr.test.ts:30,32,45,47,61,63`; `sqlCompletionProvider.test.ts:10,13,16,37,41`). `yarn prettier:write` fixes these.

**5. `sqlCompletionProvider.test.ts:42-46` — the second test can pass without asserting anything.**

Every assertion is inside `if (resolveFunc) { … }` and, unlike the first test, there is no `expect(resolveFunc).toBeDefined()` guard. If `provider.tables` ever stops being populated, this test goes green having verified nothing — the failure mode is indistinguishable from success. (The first test at `:14-29` has the same shape but is saved by its `toBeDefined()`.) Drop the conditional and assert unconditionally, e.g. `const resolve = provider.tables!.resolve;`.

This test also only checks `name`, never `completion`, so it does not exercise the changed line at all.

#### Minor

**6. `metaSqlExpr.test.ts:37-38` — `expect.anything()` hides the interesting argument.** The third argument is `queries.filter((q) => q.refId === query.table)` — the very filter that issue #2 breaks. `expect.anything()` matches `[]`, so this assertion passes whether or not the refId lookup succeeded. Assert `[{ refId: 'table with spaces' }]` explicitly.

**7. Core feature code now imports from a decoupled plugin workspace.** `SqlExpr.tsx:13` and `sqlCompletionProvider.ts:9` import `app/plugins/datasource/mysql/sqlUtil`. `mysql` is its own Yarn workspace (`@grafana-plugins/mysql`, `package.json:479-485`) and appears in the `decoupled-plugins-overrides` list (`eslint.config.js:463`). These are the only two such imports anywhere in `public/app/features` or `packages/`. Lint does not catch it (`import/no-restricted-paths` guards plugin→core, not core→plugin), but it couples core to a plugin being extracted and pulls the mysql `RESERVED_WORDS` table into the core bundle. Since `metaSqlExpr.ts:114` already owns a helper, the cheaper fix for #3 is to export a single reserved-word-aware helper from the expressions module (or add one to `@grafana/sql`, which exports no quoting utility today).

**8. Backticks inside identifiers are not escaped.** ``quoteIdentifierIfNecessary('a`b')`` returns ``` `a`b` ``` (I ran it), which vitess rejects. refIds are free-form, so this is reachable; it was equally broken before, so it is not a regression, and it is **not** a security issue — `runMetaSQLExprQuery` posts through `/api/ds/query` as a normal SQL expression subject to `parser_allow.go`, and the user already controls the expression text. Correct behavior is `` value.replace(/`/g, '``') `` before wrapping.

**9. Empty-string identifier.** `sqlCompletionProvider.ts:27`: if both `label` and `value` are absent, `quoteIdentifierIfNecessary('')` returns ` `` ` — a completion item that inserts two backticks.

**10. The fix does not reach the GenAI prompt surface.** `GenAISQLSuggestionsButton.tsx:35,62` and `GenAISQLExplainButton.tsx:47` still `join(', ')` raw refIds into the LLM prompt, so generated SQL will keep producing `FROM gdp per capita`. Out of the diff's scope, but it is the same defect class and worth a follow-up.

### Recommendations

1. Fix #1 before anything else — it is a one-line guard on a crash the base commit did not have, and it has no test.
2. Treat quoting as a round trip, not a one-way transform. Every place that *reads* a table name back out of the editor (`metaSqlExpr.ts:15` and `:20`, and the completion provider's table-token parsing) needs the matching `unquoteIdentifier`. The mysql datasource is the working reference for both halves.
3. Collapse to one `quoteIdentifierIfNecessary`. Two implementations that disagree on reserved words, reached from three call sites in the same feature, will drift again.
4. Run `yarn prettier:write` and `yarn lint:fix` on the new tests, and replace the `as any` casts with typed fixtures.
5. Add the missing cases: `refIds: []`, a reserved-word refId, and an already-quoted `query.table` fed to `fetchSQLFields`. Each of those is a currently-broken path with no coverage.

### Assessment

**Ready to merge?** No.

**Reasoning:** The premise is correct and I confirmed the backend resolves backtick-quoted table names to refIds, but the change introduces a verified render-time crash when `refIds` is empty, and it emits quoted identifiers into the editor without any corresponding unquoting on the read-back path — so column autocomplete breaks for precisely the table names the PR sets out to fix. The two new test files also fail the repo's own lint and prettier checks.

