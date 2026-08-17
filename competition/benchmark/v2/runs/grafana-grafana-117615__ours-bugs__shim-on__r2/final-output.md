✅ Review complete: `.decaf/code-reviews/CODE_REVIEW_2026-08-17_sql-expr-backticks.md`

Tracked source is byte-identical to the change under review — the only new path is the report itself.

## Verdict: ❌ NEEDS_CHANGES — 2 High, 1 Medium, 2 Minor

**#1 High — `SqlExpr.tsx:81` crashes the editor when the SQL expression is the only query.** `refIds` is "all *other* queries," so an expression-only panel or alert rule gives `vars[0] === undefined`. The old `${vars[0]}` rendered the harmless text `undefined`; the new call reaches `identifier.toUpperCase()` in `sqlUtil.ts:54` and throws during render. I reproduced the `TypeError` with a probe and confirmed via a revert probe that the same test passes once line 81 is reverted — so this line introduces it.

**#2 High — the two new test files fail `prettier --check` and `eslint` (14 errors).** Verified by running both gates with the repo's own config. Thirteen are `no-explicit-any` on the `as any` casts, so this isn't a formatting-only pass. Those same casts are what let the tests accept shapes the production callers can't produce — which is how #3 hid.

**#3 Medium — backticks don't round-trip.** The change fixes the write side but not the read side: Monaco tokenizes `` `gdp per capita` `` into three tokens, `getTableToken` returns only the lone opening backtick, so `fetchSQLFields` builds `SELECT * FROM ``` LIMIT 1` and its unchanged `refId` filter matches nothing. I verified all four links in the installed deps and reproduced the SQL. `unquoteIdentifier` already exists for exactly this and `mySqlMetaQuery.ts:39` is the precedent. Bounded by `sqlExpressionsColumnAutoComplete` being off by default.

**One notable negative result.** The only other 2-finder cluster — broad-reviewer at High, quick-reviewer at Medium: "reserved-word table names stay unquoted in `metaSqlExpr.ts`" — was **refuted**. For a bare reserved word the new call is a no-op; I confirmed it emits `SELECT * FROM order LIMIT 1`, exactly what the pre-change line produced. Under `narrow` reach that's an incomplete fix, not an introduced defect. The underlying observation still holds and pairs naturally with #3's fix, so it's recorded rather than discarded.

Two caveats on coverage: the `bugs` roster cap of 4 dropped `typescript-reviewer` and `security-reviewer`, both of whose gates matched on a TS-only change that builds SQL from non-constant input. And clustering/screening ran inline rather than as dispatched agents — a deliberate deviation for 10 findings with distinct anchors, recorded in the report.
