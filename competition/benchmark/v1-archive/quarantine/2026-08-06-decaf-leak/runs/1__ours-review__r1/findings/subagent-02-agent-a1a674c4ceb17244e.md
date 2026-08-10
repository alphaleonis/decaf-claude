# subagent agent-a1a674c4ceb17244e

```json
[
  {
    "file": "src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs",
    "line": 329,
    "severity": "High",
    "category": "performance",
    "issue": "[PERF_QUERY] Negative-result memoization was dropped when the cache was widened from a single nullable field (`_rowidOrdinal`) to a `Dictionary<string, RowIdInfo>` keyed by `\"{db}_{table}\"`. Before this change, both the found AND not-found outcomes were memoized (`_rowidOrdinal = -1` sentinel, then checked via `.HasValue`), so the metadata scan ran once per SqliteDataRecord. Now only the found case is added to `RowIds` (lines 354-355, 386-387); when the scan completes without a hit (WITHOUT ROWID tables, views, computed/aggregate blob expressions, or tables whose INTEGER PK is composite), nothing is cached, so `RowIds.TryGetValue` misses again on the next call. `GetStream`/`GetBytes` runs once per blob cell, so this re-executes the full field scan (up to FieldCount native `sqlite3_column_database_name`/`table_name`/`origin_name`/`sqlite3_table_column_metadata` calls) on every single row while streaming such a result set — and if any field is an INTEGER-pk candidate, it also re-opens and re-executes a `SELECT COUNT(*) FROM pragma_table_info($table) WHERE pk != 0` command (lines 375-381) per row, since the local `pkColumns` is reset to -1 on every call. For a result set of N rows over such a table, this is O(N) repeated metadata scans plus up to O(N) extra nested SQL executions on the same connection where before it was O(1).",
    "fix": "Cache the negative outcome too, e.g. store a nullable/sentinel entry in `RowIds` (or a `HashSet<string>` of \"known miss\" keys) when the scan completes without finding a rowid/single-INTEGER-pk column, and short-circuit straight to `GetCachedBlob` on a repeat miss instead of re-scanning.",
    "confidence": 100,
    "pre_existing": false
  },
  {
    "file": "src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs",
    "line": 324,
    "severity": "Low",
    "category": "performance",
    "issue": "[PERF_HOT_PATH] Every `GetStream` call now unconditionally calls `sqlite3_column_database_name`/`table_name` and builds a new interpolated string `$\"{blobDatabaseName}_{blobTableName}\"` as a dictionary key (lines 324-328), even on a cache hit. The prior implementation only needed to check `_rowidOrdinal.HasValue`. This is small per call but repeats once per blob cell per row for the lifetime of the reader.",
    "fix": "If the not-found caching fix above is applied, this cost is unavoidable overhead of the new keying scheme and is minor; could be trimmed by caching the key or RowIdInfo lookup result per-ordinal instead of re-deriving db/table names each call, but only worth doing after the larger negative-cache gap is fixed.",
    "confidence": 75,
    "pre_existing": false
  }
]
```

## Considered But Not Flagged

- The `Debug.Assert(rowIdForOrdinal != null)` at line 393 will fire in debug builds for the legitimate "no rowid available" case (previously always satisfied via the `-1` sentinel `HasValue` check) — this is a correctness/assert-validity issue, not a cost-at-scale one; out of scope for this persona (belongs to quick-reviewer/dotnet-reviewer).
- `sqlite3_table_column_metadata` and the per-field native name lookups inside the scan loop are inherent to resolving rowid metadata and unavoidable on the first (cache-miss) pass for any given table; only their *repetition* on every row (the primary finding above) is the introduced cost.
- Positive-path caching (found rowid) is correctly memoized per `{db}_{table}` key and shows no regression — not flagged.
- `GetCachedBlob`'s per-record `_blobCache` array is bounded by `FieldCount` and cleared each `Read()` (line 439-442) — bounded memory, not a growth concern.
