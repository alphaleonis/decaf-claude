# subagent agent-ad966b755809babc1

```json
{
  "finding": "#1",
  "verdict": "confirmed",
  "reason": "Traced execution directly: RowIds (SqliteDataRecord.cs:39) is a single instance-scoped Dictionary<string, RowIdInfo> keyed only by the concatenated string `$\"{db}_{table}\"`. For two blob columns whose true (database, table) pairs differ but concatenate to the same string (e.g. db=\"a\", table=\"b_c\" vs db=\"a_b\", table=\"c\"), the first column's scan correctly filters candidate columns by exact `databaseName == blobDatabaseName && tableName == blobTableName` and caches under the collided key. The second column's lookup (line 329, `RowIds.TryGetValue(rowidkey, ...)`) hits this cache entry immediately and short-circuits — it never re-enters the per-column filtering loop that would have caught the name mismatch. Notably, `RowIdInfo` even carries a `TableName` field (SqliteDataRecord.cs:20-30) that is populated at cache-write time but never checked against `blobTableName` at cache-read time, so there is no guard that would catch or reject the stale/foreign entry. `GetInt64(rowIdForOrdinal.Ordinal)` at line 402 then reads from an ordinal that indexes the wrong table's rowid column, and the resulting `SqliteBlob` is opened with a mismatched rowid. Reachability requires ATTACHed databases (or careful use of `_` in identifiers) arranged so two blob columns collide, which is a real, if narrow, path through public SQLite features (ATTACH + cross-schema query selecting blob columns) — not merely theoretical.",
  "corrections": null
}
```
