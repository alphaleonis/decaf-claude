✅ Review complete: `.decaf/code-reviews/CODE_REVIEW_2026-08-17_19-47-02.md`

**Verdict: ❌ NEEDS_CHANGES** — 2 High, 2 Medium, 3 Low.

The change routes SQL identifiers through `quoteIdentifierIfNecessary` at three call sites. The direction is right (backtick quoting is correct for the vitess/go-mysql-server backend), but three things are wrong with how it lands:

**High — `SqlExpr.tsx:81` throws during render when the SQL expression is the only query.** `vars[0]` is `undefined` when `refIds` is empty, and `isValidIdentifier` (`mysql/sqlUtil.ts:52-56`) calls `identifier.toUpperCase()` unconditionally. Before the change this produced the harmless string `FROM undefined`. Reachable by deleting the last data query from a panel that still holds a SQL expression — `QueryEditorRows.onRemoveQuery` has no guard.

**High — `SqlExpr.tsx:81` breaks the alerting DAG.** The emitted expression is parsed back by `parseRefsFromSqlExpression` (`alerting/.../dag.ts:121`), whose `cleanTableName` strips `'`, `"`, `(`, `)` but *not* backticks. `` FROM `my-query` `` yields the ref `` `my-query` ``, no such node exists, `Graph.link` throws, and the SQL expression is dropped from the graph. This is a regression for any refId the predicate quotes but that has no space — `my-query`, `2024`, a reserved word like `left` — all of which worked before. The fix's own goal (spaced names in alert rules) also isn't met, since `cleanTableName` truncates at the first space.

**Low but notable — the three call sites don't actually use the same helper.** `metaSqlExpr.ts:15` has no import; it resolves to a file-local helper at `metaSqlExpr.ts:114` that is regex-only with no reserved-word check (I confirmed this directly). So for a query named `Values`, the editor emits `` FROM `Values` `` while the column-autocomplete meta query emits `FROM Values` — a backend parse error swallowed by `catch { return []; }`, leaving autocomplete silently empty.

Also: core → decoupled-plugin import direction (Medium), and both new test files fail `no-explicit-any` and Prettier (Medium) — trailing whitespace on 11 lines, 8 `as any`.

Two caveats on this run, both recorded in the report: `node_modules` is absent and there's no network, so nothing here was verified by running the project's own test suite — "executed" findings were verified against standalone reproductions of the cited source. And `bugs-sp` is a single-seat path with no validation wave, so these carry one agent's variance. The seat itself flagged one parked item (possible double-quoting at `metaSqlExpr.ts:15`) as wanting a re-check once dependencies are installed.

No code was modified; the only new file is the report.
