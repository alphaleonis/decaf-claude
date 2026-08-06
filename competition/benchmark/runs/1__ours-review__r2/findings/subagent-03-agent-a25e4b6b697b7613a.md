# subagent agent-a25e4b6b697b7613a

Reviewed the diff description and cache logic in `SqliteDataRecord.GetStream`. One clear performance regression found regarding negative-result caching.

```json
[
  {
    "file": "src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs",
    "line": 328,
    "severity": "High",
    "category": "performance",
    "issue": "[PERF_CACHING] Negative (\"no rowid column\") result is never added to `RowIds`. When `rowIdForOrdinal` stays null after the scan loop, the code falls through to `Debug.Assert` and the `MemoryStream` fallback without any `RowIds.Add(rowidkey, ...)` call. On the *next* `GetStream` call for the same `\"{db}_{table}\"` key, `RowIds.TryGetValue` misses again, so the full `for (i < FieldCount)` scan re-runs — including `sqlite3_column_database_name`/`_table_name`/`_origin_name` native calls per column, `sqlite3_table_column_metadata` per candidate INTEGER column, and (if an INTEGER PK column is seen) a fresh `SELECT COUNT(*) FROM pragma_table_info($table)` command execution. `GetStream` is the streaming-BLOB API, so it is typically called once per row inside a `while(reader.Read())` loop; for a WITHOUT ROWID table, a table with a composite primary key, or a view/computed-column result set, this full rescan (plus the pragma query) repeats on every row for the lifetime of the reader instead of being paid once. Before this change, the single `int? _rowidOrdinal` field cached the -1 (not-found) sentinel too, so the scan ran at most once per reader regardless of table shape.",
    "fix": "Cache the negative result too, e.g. `RowIds.Add(rowidkey, RowIdInfo.None)` (a sentinel instance, or make `RowIdInfo` nullable-friendly) when the loop exits without finding a rowid column, and check for that sentinel before taking the `GetCachedBlob` fallback path.",
    "confidence": 100,
    "pre_existing": false
  }
]
```

## Considered But Not Flagged

- `pkColumns` is a per-call local (reset to `-1L` each invocation) rather than cached alongside `RowIds`, so within a single not-found call it avoids re-issuing the `pragma_table_info` query for multiple candidate columns — but this is subsumed by the primary finding above (the whole call, pragma query included, repeats every row anyway since there's no cross-call negative cache).
- `Dictionary<string, RowIdInfo> RowIds` unbounded growth: keyed by distinct `db_table` pairs from the query's schema, not by row data — bounded by schema shape, not row count. Anchor 0, not a finding.
- `$"{blobDatabaseName}_{blobTableName}"` string allocation per `GetStream` call: small, bounded, unavoidable for the lookup key. Anchor 25, not reported.
- Positive-path caching (rowid found) is correctly scoped per-table via the dictionary and is strictly better than the prior single-field cache (which could wrongly reuse one table's rowid ordinal for another table) — improvement, not a finding.

### Probe Requests

None.
