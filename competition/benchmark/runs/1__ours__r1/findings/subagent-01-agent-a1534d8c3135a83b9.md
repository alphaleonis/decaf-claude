# subagent agent-a1534d8c3135a83b9

## Verification Summary

I read the live file (`src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs`) and the PR diff directly.

**1. Key construction as quoted** — confirmed verbatim at line 328:
```csharp
string rowidkey = $"{blobDatabaseName}_{blobTableName}";
```
backed by `readonly Dictionary<string, RowIdInfo> RowIds = new Dictionary<string, RowIdInfo>();` (line 39).

**2. Collision-to-harm path traced end-to-end.** On a cache hit (`RowIds.TryGetValue(rowidkey, out rowIdForOrdinal)` succeeds), the code jumps straight to:
```csharp
var rowid = GetInt64(rowIdForOrdinal.Ordinal);
return new SqliteBlob(_connection, blobDatabaseName, blobTableName, blobColumnName, rowid, readOnly: true);
```
Critically, `RowIdInfo` *does* carry a `TableName` field (set at construction, lines 20-30, 354, 386) but it is **never read back** to sanity-check a cache hit against the current call's actual `blobTableName`. The scan loop that *populates* the cache (lines 330-392) correctly filters by the real `databaseName`/`tableName` of the column being scanned — that part is sound. But once populated under a colliding key, a second (db, table) pair whose concatenation happens to match reuses the first pair's `Ordinal` unconditionally. The `SqliteBlob` is built with the *current* call's genuinely-correct `blobDatabaseName`/`blobTableName` strings, but the *wrong* `rowid` value (read from an ordinal that belongs to the other table's rowid column in the same row). This produces exactly the failure the reviewer describes: silently-wrong blob data, or a `SqliteException` if that value isn't a valid rowid in the actual target table. Also confirmed the `SqliteDataRecord` instance (and its `RowIds` dict) is created once per statement in `SqliteDataReader.NextResult()` and persists across every row of that result set — so a collision, once triggered, corrupts every row read from that statement, not just the first.

**3. SQLite identifier/ATTACH rules** — `sqlite3_column_database_name` returns the schema name (the `ATTACH ... AS <alias>` alias, e.g. `"main"`, `"temp"`, or a custom alias), not a file path. Unquoted SQLite identifiers (table names, ATTACH aliases) follow standard `[A-Za-z_][A-Za-z0-9_]*` rules — underscores are legal and idiomatic. `ATTACH DATABASE 'x.db' AS archive_v2;` and a table named `v2_data` are both valid, unquoted SQL. The collision scenario is realizable with ordinary SQL, no exotic quoting needed. Requires a query joining columns from two differently-aliased/attached databases within one statement — narrow but real (matches the reviewer's framing).

**4. Severity note (informational only, not altering verdict)**: the trigger genuinely requires multi-database queries with underscore-coincident alias/table names in a single statement — a narrow, specific precondition. That's consistent with the dissenting Medium ratings; the Critical anchor came from severity-escalation on a correctness/silent-data-corruption category, which is a legitimate but separate axis from trigger-likelihood. Not mine to adjust.

**5. Not pre-existing** — confirmed via `git diff HEAD~1..HEAD`: the prior code used `private int? _rowidOrdinal;`, a single scalar with no key at all. This PR introduces the entire `RowIds`/`RowIdInfo`/string-concatenation-key mechanism from scratch, replacing the old (differently-bugged, single-cache) approach. The finding's claim that this is new code is accurate.

**Fix sanity**: replacing the key with `Dictionary<(string?, string?), RowIdInfo>` (or equivalent tuple/composite key) eliminates the encoding ambiguity since tuple equality compares components independently — the fix addresses the actual defect.

```json
{
  "finding": "#2",
  "verdict": "confirmed",
  "reason": "Verified on disk at SqliteDataRecord.cs:328 that the dictionary key is naive string concatenation with '_', and traced that a cache hit under a colliding key is consumed with no validation against the stored RowIdInfo.TableName (which exists but is never read back) before reusing its Ordinal for GetInt64 — so a genuine (db, table) collision reuses the wrong rowid ordinal while constructing the SqliteBlob with the correct current-call db/table strings, producing wrong-row/wrong-table blob access. Confirmed via git diff that the prior code used a single scalar `_rowidOrdinal` (no keying at all), so this is newly introduced by this PR, not pre-existing.",
  "corrections": {
    "line": 328,
    "pre_existing": false
  }
}
```
