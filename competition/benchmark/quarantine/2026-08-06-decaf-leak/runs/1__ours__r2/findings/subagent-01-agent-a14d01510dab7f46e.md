# subagent agent-a14d01510dab7f46e

```json
[
  {
    "file": "src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs",
    "line": 327,
    "severity": "High",
    "category": "performance",
    "issue": "[PERF_QUERY] The new `RowIds` dictionary caches only the found-rowid case. When no rowid/single-column INTEGER PK is discovered for a table (WITHOUT ROWID tables, composite primary keys, or blob columns without table lineage), `rowIdForOrdinal` stays null and is never added to `RowIds` (no `RowIds.Add(rowidkey, null-sentinel)` path exists). The old code permanently cached this negative result as `_rowidOrdinal = -1`. Now every call re-enters the `!RowIds.TryGetValue(...)` branch and reruns the full O(FieldCount) discovery loop, which for any INTEGER-typed PRIMARY KEY candidate column executes a real SQL command (`_connection.CreateCommand()` + `SELECT COUNT(*) FROM pragma_table_info($table) WHERE pk != 0` + `ExecuteScalar()`). `GetStream` is invoked from `GetBytes` (line 276, `using var stream = GetStream(ordinal);`), which is the ADO.NET chunked-blob-read API — callers invoke it repeatedly per row (and often multiple times per row for chunked reads of one large blob) via `SqliteDataReader.Read()`/`GetBytes()`. Because a single `SqliteDataRecord` instance (and its `RowIds` dictionary) persists for the entire result set (`_record` is created once per statement in `SqliteDataReader.NextResult()`, not per row — confirmed in SqliteDataReader.cs lines 142-183), this is not a one-off cost: for any table hitting the negative branch, the pragma_table_info command executes on every single row (or every chunk) for the life of the read loop — e.g. a 500k-row scan of a WITHOUT ROWID table streaming BLOBs executes ~500k extra prepared-statement compilations/executions against the same connection.",
    "fix": "Cache the negative result too, e.g. store a nullable/sentinel `RowIdInfo` (or a `Dictionary<string, RowIdInfo?>`) and `RowIds.Add(rowidkey, null)` before falling into the not-found branch, then check `RowIds.TryGetValue(rowidkey, out var entry)` and treat a present-but-null entry as \"use GetCachedBlob\" without rerunning the discovery loop or the pragma_table_info query.",
    "confidence": 100,
    "pre_existing": false
  }
]
```

## Considered But Not Flagged

- The positive (rowid-found) caching path is now correctly keyed per `database_table`, fixing the original join bug and behaving like the old sentinel cache for that case — reruns the scan only once per distinct table encountered in the result set, which is bounded and small. No regression there.
- `RowIdInfo` being a small heap-allocated class per distinct table (vs. the old bare `int?`) — bounded by number of distinct joined tables per query, not unbounded growth; not scale-sensitive.
- `GetCachedBlob(ordinal)` fully materializing the blob into memory for the not-found branch (`new MemoryStream(GetCachedBlob(ordinal), false)`) — this buffering behavior is pre-existing (present in the code before this diff) and its per-call frequency is unchanged by this diff, so not newly amplified; belongs to a pre-existing design question, not this changeset's cost regression.
- `sqlite3_table_column_metadata` calls inside the discovery loop for non-rowid, non-PK-hit columns — real C-API metadata lookups, not full SQL command executions; only rises to a finding via the pragma_table_info path already flagged above, which is the dominant cost.
- Dictionary key built via string concatenation (`$"{db}_{table}"`) — a potential correctness collision (e.g. db `"a_b"`/table `"c"` vs db `"a"`/table `"b_c"`), not a cost/scale issue — out of scope for this review, left for quick-reviewer/dotnet-reviewer.
