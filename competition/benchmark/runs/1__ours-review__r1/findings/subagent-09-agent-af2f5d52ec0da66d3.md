# subagent agent-af2f5d52ec0da66d3

```json
{
  "finding": "rowid cache key does not uniquely identify the rowid source — two distinct failure modes",
  "verdict": "confirmed",
  "reason": "Read src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs lines 316-404 directly. (a) Line 328: `string rowidkey = $\"{blobDatabaseName}_{blobTableName}\";` is a raw underscore-concatenation of db+table names with no delimiter escaping, so (db=\"main\", table=\"foo_bar\") and (db=\"main_foo\", table=\"bar\") both hash to \"main_foo_bar\" — a genuine, reproducible key collision. (b) The scan loop (lines 332-391) matches candidate rowid/PK columns purely by `sqlite3_column_database_name`/`sqlite3_column_table_name` string equality (lines 340, 346), and `sqlite3_column_table_name` returns the underlying table name, not the query alias — this is documented SQLite C-API behavior. So for a self-join `SELECT a.blob, b.blob FROM T a JOIN T b ...`, both blob columns key to \"main_T\"; the second GetStream call hits the cache (line 329) and reuses the RowIdInfo ordinal discovered while resolving the first alias's blob, applying alias a's row/rowid ordinal to alias b's blob fetch (line 402/404). Both mechanisms are real and independently derivable from the code as written — this is a narrow but genuine regression-shaped gap in the same class of bug (#32747) the PR is fixing. Reachability is low (requires underscore-colliding db/table names, or a self-join with two dereferenced blob columns from different aliases in one row), consistent with a Medium severity rather than High.",
  "corrections": null
}
```
