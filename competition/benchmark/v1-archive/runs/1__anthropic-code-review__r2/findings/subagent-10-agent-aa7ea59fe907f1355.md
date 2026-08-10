# subagent agent-aa7ea59fe907f1355

## Review: dotnet/efcore #32770 — SqliteDataRecord blob-stream fix

Reviewed the diff (`git show HEAD`) plus the surrounding `GetStream` method in the current file (`src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs:316-410`). Two genuine logic bugs in the new code; nothing found in the test file itself.

### 1. Dictionary key built by naive string concatenation — collision risk

**File:** `src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs`
**Lines:** 328 (key construction), 329/354-355/386-387 (lookup/insert using that key)

```csharp
string rowidkey = $"{blobDatabaseName}_{blobTableName}";
if (!RowIds.TryGetValue(rowidkey, out rowIdForOrdinal))
```

The key is `"{db}_{table}"` with a plain `_` separator and no escaping. Two distinct `(database, table)` pairs can produce the same string, e.g. database `"main_users"` + table `"x"` → `"main_users_x"`, and database `"main"` + table `"users_x"` → also `"main_users_x"`. This is realistic once `ATTACH DATABASE ... AS <name>` is used with underscore-containing names (common in multi-tenant/sharded setups), which is exactly the multi-table-join scenario this PR is meant to support.

**Failure scenario:** A query joins a blob column from `main."users_x"` and a blob column from `main_users."x"` in the same result set. Whichever table's rowid gets cached first under key `"main_users_x"` is silently reused for the second column's `GetStream()` call. Since only the rowid *ordinal* is looked up from the cache (the `blobDatabaseName`/`blobTableName` used to construct the actual `SqliteBlob` are still correct, computed fresh for the current ordinal), the code ends up reading `GetInt64` from the wrong result column and opening a `SqliteBlob` with a bogus/foreign rowid — returning wrong blob content, or throwing if that rowid doesn't exist in the target table.

**Reason flagged:** bug (dictionary key construction/collision), matching the exact class of the old single-scalar-cache bug this PR set out to fix.

### 2. "No rowid available" outcome is never cached — reachable, previously-inert `Debug.Assert` now fires

**File:** `src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs`
**Lines:** 327, 331-394 (loop), specifically line 393 `Debug.Assert(rowIdForOrdinal!=null);`

In the old code, `_rowidOrdinal` was unconditionally initialized to the sentinel `-1` *before* the search loop, so `Debug.Assert(_rowidOrdinal.HasValue)` was trivially always true — including for tables with no single-column INTEGER PRIMARY KEY (WITHOUT ROWID tables, composite primary keys, views). The `-1` sentinel was itself cached, so the "no rowid" outcome for that table was computed once and reused for every future `GetStream()` call.

In the new code, `rowIdForOrdinal` starts as `null` and is **only** written to `RowIds` inside the two `break`-reaching branches (lines 354-355 and 386-387). If the loop completes without ever finding a rowid or a single-column INTEGER PK, `rowIdForOrdinal` stays `null` and — unlike the old `-1` sentinel — is **never added to `RowIds`**.

Consequences:
- `Debug.Assert(rowIdForOrdinal != null)` at line 393 is now a *genuinely reachable, sometimes-false* assertion for any table/view without a single-column rowid — a real behavior regression from the old always-true assert (fires in Debug builds of the library where it never did before).
- Because the negative result isn't cached, every subsequent `GetStream()` call for a blob column on such a table re-runs the entire per-field scan (lines 332-391), including re-issuing the `SELECT COUNT(*) FROM pragma_table_info(...)` query (lines 375-381) via a brand-new command on the same connection, on every single call — a caching-correctness regression versus the old "compute once, cache negative result" behavior, not just a performance nit, since it changes the invariant the fix is supposed to establish ("resolve per-table rowid info once").

**Failure scenario:** Query joins a normal table with a WITHOUT ROWID table (or any table lacking a single-column INTEGER PRIMARY KEY) that also has a BLOB column, and the blob column from the rowid-less table is streamed via `GetStream`/`GetBytes` across multiple rows. Each access re-triggers the full scan + pragma query, and in a Debug build of `Microsoft.Data.Sqlite.Core` trips `Debug.Assert(rowIdForOrdinal!=null)`, which previously could never fail here.

**Reason flagged:** bug (cache-correctness / "tables without rowid" case broken by the new caching scheme; assert regression).

No other issues found in the reviewed hunks — the dictionary keyed by table correctly handles the PR's actual target scenario (distinct tables joined together, each with their own blob column), matching the added test `GetBytes_works_streaming_join`.
