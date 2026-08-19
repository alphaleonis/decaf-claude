I'll run the code review skill as requested.
I'll start by gathering context on the change under review.
Small, focused changeset. Let me read the relevant source files and the helper being used.
Found several promising leads. Let me verify the key data flow and run pre-flight gates.
Deps installing in the background. Announcing the team and dispatching the wave.

**Review team** (preset `bugs` — explicit · roster N=4 (derived: ~135 executable lines incl. tests, capped at 4 by `bugs`) · models=low · evidence=strong · reach=narrow):
- `quick-reviewer` (always — floor) — mid tier
- `broad-reviewer` (always — floor) — mid tier
- `adversarial-reviewer` — ≥50 changed executable lines; rank-1 specialist — session model
- `test-reviewer` — hard gate: 3 test files in changeset — mid tier
- `typescript-reviewer`: **dropped** — roster N=4: hard gate matched (TS/TSX files, unvalidated-boundary-data idiom surface), ranked below the 2 specialists kept. Coverage traded for the cap.
- `security-reviewer`: **dropped** — roster N=4: gate matched (SQL string built from non-constant identifier input), ranked below the 2 kept
- `knowledge-reviewer`, `consistency-reviewer`: **dropped** — roster N=4: ranked last under `bugs`
- `design-reviewer`: skipped — no public API/contract, data-model, or concurrency surface change
- `spec-compliance-reviewer`: skipped — no spec found (hard gate)
- `data-migration-reviewer`, `prior-feedback-reviewer`, other stack reviewers: skipped — hard gates not met
Deps landed and the wave has joined. I'm now the only actor on the tree — running Step 4.5 nominated probes.
Baseline is green. Now the probes — writing them as **untracked** temp files (tracked source stays byte-identical).
**Probe A CONFIRMED** — crash at `SqlExpr.tsx:81` → `sqlUtil.ts:54`. Now the revert half, to prove the change introduced it.
Tree restored. Now Probe B — the completion→column-fetch round trip. Let me verify the tokenizer claim in the installed `@grafana/plugin-ui`.
Both remaining links confirmed statically. Now the empirical half of Probe B.
Probe failures are only Grafana's `console.log` guard — the logged values stand. Cleaning up and verifying the remaining claims.
**Prettier failure CONFIRMED** — both new test files fail `prettier --check`, which is CI-enforced. Now the lint boundary claim.
Let me check reachability of the empty-`refIds` crash before finalizing severity.
Reachable — `refIds` is "all other queries", so a panel/rule whose only query is the SQL expression yields `[]`. Now the validation wave on the three findings the screen left open.
Validation complete: **C2 refuted** (reserved-word divergence is a no-op — pre-existing), **C3 confirmed**, **C6 confirmed but downgraded to Low**. Writing the report.
✅ Review complete: `.decaf/code-reviews/CODE_REVIEW_2026-08-17_sql-expr-backticks.md`

Tracked source is byte-identical to the change under review — the only new path is the report itself.

## Verdict: ❌ NEEDS_CHANGES — 2 High, 1 Medium, 2 Minor

**#1 High — `SqlExpr.tsx:81` crashes the editor when the SQL expression is the only query.** `refIds` is "all *other* queries," so an expression-only panel or alert rule gives `vars[0] === undefined`. The old `${vars[0]}` rendered the harmless text `undefined`; the new call reaches `identifier.toUpperCase()` in `sqlUtil.ts:54` and throws during render. I reproduced the `TypeError` with a probe and confirmed via a revert probe that the same test passes once line 81 is reverted — so this line introduces it.

**#2 High — the two new test files fail `prettier --check` and `eslint` (14 errors).** Verified by running both gates with the repo's own config. Thirteen are `no-explicit-any` on the `as any` casts, so this isn't a formatting-only pass. Those same casts are what let the tests accept shapes the production callers can't produce — which is how #3 hid.

**#3 Medium — backticks don't round-trip.** The change fixes the write side but not the read side: Monaco tokenizes `` `gdp per capita` `` into three tokens, `getTableToken` returns only the lone opening backtick, so `fetchSQLFields` builds `SELECT * FROM ``` LIMIT 1` and its unchanged `refId` filter matches nothing. I verified all four links in the installed deps and reproduced the SQL. `unquoteIdentifier` already exists for exactly this and `mySqlMetaQuery.ts:39` is the precedent. Bounded by `sqlExpressionsColumnAutoComplete` being off by default.

**One notable negative result.** The only other 2-finder cluster — broad-reviewer at High, quick-reviewer at Medium: "reserved-word table names stay unquoted in `metaSqlExpr.ts`" — was **refuted**. For a bare reserved word the new call is a no-op; I confirmed it emits `SELECT * FROM order LIMIT 1`, exactly what the pre-change line produced. Under `narrow` reach that's an incomplete fix, not an introduced defect. The underlying observation still holds and pairs naturally with #3's fix, so it's recorded rather than discarded.

Two caveats on coverage: the `bugs` roster cap of 4 dropped `typescript-reviewer` and `security-reviewer`, both of whose gates matched on a TS-only change that builds SQL from non-constant input. And clustering/screening ran inline rather than as dispatched agents — a deliberate deviation for 10 findings with distinct anchors, recorded in the report.

