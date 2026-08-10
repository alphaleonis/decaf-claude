# subagent agent-aaf30ea46d101470e

```json
[
  {
    "file": "src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs",
    "line": 329,
    "severity": "High",
    "category": "performance",
    "issue": "[PERF_CACHING] Negative outcome (\"no rowid discoverable for this table\") is no longer cached. Old code set `_rowidOrdinal = -1` unconditionally before the search loop, so a table with no discoverable rowid alias was memoized after the first miss. New code only calls `RowIds.Add(rowidkey, ...)` inside the two \"found\" branches (lines 354-355, 386-387); if the FieldCount loop completes without a match (WITHOUT ROWID tables, composite-PK join/junction tables with a BLOB column, or any table whose single-column INTEGER PK isn't confirmed), nothing is written to `RowIds` for that db_table key. Every subsequent `GetStream` call for that column — i.e. every `GetBytes`/`GetString`/`GetChars` call, per chunk of a streamed blob and per row — re-runs the full O(FieldCount) column scan, re-issues `sqlite3_table_column_metadata` native calls per candidate PK column, and (when a same-table INTEGER-typed PK-flagged column is present) re-prepares and re-executes a brand-new `SqliteCommand` (`SELECT COUNT(*) FROM pragma_table_info($table) WHERE pk != 0;`) against the live connection, because `pkColumns` is re-initialized to -1 on every miss. At scale (bulk export of a composite-PK/junction table with BLOB payload, or chunked reads of a large blob field over many rows), this turns a one-time schema lookup into a repeated statement-prepare-and-execute on the hot read path.",
    "fix": "Cache the negative outcome too: e.g. store a sentinel `RowIdInfo` (or a nullable wrapper / `TryAdd` with a `NotFound` marker) in `RowIds` when the loop exits without a match, mirroring the old `_rowidOrdinal = -1` semantics, so the expensive metadata/pragma lookup runs at most once per distinct table per reader instance.",
    "confidence": 100,
    "pre_existing": false
  },
  {
    "file": "src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs",
    "line": 328,
    "severity": "Medium",
    "category": "performance",
    "issue": "[PERF_MEMORY] A new dictionary key string is allocated on every `GetStream` call via `$\"{blobDatabaseName}_{blobTableName}\"`, even on the cache-hit path where the old code did a zero-allocation `_rowidOrdinal.HasValue` check. Since `GetBytes`/`GetChars` call `GetStream` fresh per invocation, streaming a large blob in chunks (default buffer sizes are typically a few KB, so a multi-MB blob means thousands of calls for a single row) or iterating many rows both multiply this allocation, adding avoidable Gen0 garbage on a path that is otherwise identical work to before.",
    "fix": "Replace the interpolated string key with a non-allocating composite key, e.g. `Dictionary<(string db, string table), RowIdInfo>` using a value-tuple key, or key directly by blob ordinal once resolved (`Dictionary<int, RowIdInfo>`) to avoid rebuilding a key on every call.",
    "confidence": 75,
    "pre_existing": false
  }
]
```

## Considered But Not Flagged

- **Full FieldCount scan + native `sqlite3_column_database_name`/`table_name` calls at the top of `GetStream`** (lines 324-325): unconditional per call, but these two native calls existed identically in the pre-change code (used later for the `SqliteBlob` constructor) — not amplified by this diff, so not reported.
- **`RowIds` dictionary growth**: bounded by the number of distinct `(database, table)` combinations referenced by blob columns in a single query/reader instance — small and finite, not cleared per row (correctly, since schema doesn't change row to row). No unbounded-growth concern.
- **`GetOrdinal`'s O(n) case-insensitive fallback scan** (lines 155-168): pre-existing, untouched by this diff, and only triggered on a cache miss for a name not found in the exact-match dictionary — cold path, not amplified here.
- **`Sqlite3AffinityType`'s LINQ `Select().FirstOrDefault()` over a freshly-allocated delegate array** (lines 508-524): pre-existing, unrelated to this diff, and only invoked when a `SQLITE_NULL` type needs affinity resolution — not touched or amplified by this change.
- **Debug.Assert(rowIdForOrdinal != null) at line 393 being a no-op in Release when the loop found nothing**: this is a correctness/behavior concern (silent fallthrough to the blob-cache path), not a cost-at-scale issue — left for quick-reviewer/dotnet-reviewer.
