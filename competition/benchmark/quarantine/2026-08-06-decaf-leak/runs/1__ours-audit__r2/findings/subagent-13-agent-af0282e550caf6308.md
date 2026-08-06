# subagent agent-af0282e550caf6308

I have the full picture. Let me record my system model and evaluate each design point.

## System model

`SqliteDataRecord` wraps one `sqlite3_stmt` and is used single-threaded per reader (no concurrency surface added). `GetStream(int)` is a public virtual API returning either a live `SqliteBlob` (streaming, keyed by rowid) or a `MemoryStream` fallback when the source column's table has no usable rowid. The change replaces a single `int? _rowidOrdinal` cache with `Dictionary<string, RowIdInfo> RowIds` keyed per (database, table) so joined queries resolve the correct rowid ordinal per table. Cache lifetime = the record instance.

Findings below.

```json
[
  {
    "file": "src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs",
    "line": 328,
    "severity": "High",
    "category": "design",
    "issue": "[DATA_MODEL] The rowid cache key is built by string concatenation with a '_' separator ($\"{blobDatabaseName}_{blobTableName}\"), which is ambiguous: database=\"a_b\"/table=\"c\" and database=\"a\"/table=\"b_c\" both produce key \"a_b_c\". Underscores are ubiquitous in SQLite schema aliases (ATTACH ... AS main_data) and table names, so two distinct (database, table) pairs in one joined result set can collide. On collision the second pair reuses the first pair's cached RowIdInfo.Ordinal, so GetInt64 reads the rowid from the wrong table's column and SqliteBlob is opened with the wrong rowid — silently returning another row's blob or throwing. This reintroduces the exact cross-table rowid-confusion class the PR set out to fix (#32747).",
    "fix": "Key the cache on a composite value that cannot be aliased by concatenation — e.g. a (database, table) ValueTuple or an equatable struct — instead of an ambiguous concatenated string. RowIdInfo already carries TableName; alternatively validate rowIdForOrdinal.TableName == blobTableName on a cache hit and re-scan on mismatch.",
    "confidence": 75,
    "pre_existing": false
  },
  {
    "file": "src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs",
    "line": 393,
    "severity": "Medium",
    "category": "design",
    "issue": "[DATA_MODEL] The new cache can no longer represent the 'searched, no rowid found' state distinctly from 'not yet searched' — both are dictionary-absence. The old int? sentinel stored -1 to memoize the negative. Two consequences: (1) for any blob column whose table has no usable rowid (WITHOUT ROWID / composite-PK / view sources), every GetStream call misses the cache and re-runs the full FieldCount scan plus the 'SELECT COUNT(*) FROM pragma_table_info' query — the negative result is never cached; (2) on that legitimate not-found path rowIdForOrdinal stays null, so Debug.Assert(rowIdForOrdinal != null) at line 393 fires in debug builds, whereas the old Debug.Assert(_rowidOrdinal.HasValue) passed because -1 was stored.",
    "fix": "Represent the negative outcome explicitly in the cache (e.g. store a sentinel RowIdInfo/marker, or use a nullable value in the dictionary) so the not-found result is memoized and the assertion reflects 'search completed' rather than 'rowid found'. Remove or correct the assertion so it does not fire on the designed not-found branch.",
    "confidence": 100,
    "pre_existing": false
  },
  {
    "file": "src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs",
    "line": 23,
    "severity": "Low",
    "category": "design",
    "issue": "[DATA_MODEL] RowIdInfo.TableName is written in the constructor but never read anywhere (verified by grep across the project). It is a dead field. Notably it is precisely the value that would let a cache hit be validated against blobTableName to neutralize the key-collision in the line-328 finding, so the disambiguation data was captured but never wired in.",
    "fix": "Either use TableName to validate cache hits (re-scan on mismatch), or drop the field and store only Ordinal. Do not carry unused state on a cache entry.",
    "confidence": 100,
    "pre_existing": false
  },
  {
    "file": "src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs",
    "line": 20,
    "severity": "Low",
    "category": "design",
    "issue": "[API_CONTRACT] RowIdInfo models effectively-immutable data (an ordinal + table name fixed at construction) but exposes public mutable get/set setters. Because entries are stored by reference in the RowIds dictionary, a future caller mutating a returned RowIdInfo would corrupt the shared cache entry in place. A readonly struct / ValueTuple (as suggested on the PR) or get-only properties would make the immutability a compile-time contract.",
    "fix": "Make the members get-only (or convert to a readonly struct / (int Ordinal, string TableName) ValueTuple) so cached entries cannot be aliased and mutated.",
    "confidence": 50,
    "pre_existing": false
  }
]
```

## Considered But Not Flagged

- **Concurrency of the new dictionary**: `SqliteDataRecord` is not documented as thread-safe and is used single-threaded per reader; `RowIds` is only touched inside `GetStream` on the owning thread. No new synchronization obligation is created. Sound.
- **`RowIds` field naming / `rowidkey` casing**: PascalCase private field and lowercase local diverge from the file's `_camelCase` convention, but this is consistency/style (consistency-reviewer scope), not a design defect.
- **Unbounded growth of `RowIds`**: bounded by the number of distinct (database, table) pairs in a single statement's result — small and record-scoped. Not a memory concern.
- **`GetInt64(rowIdForOrdinal.Ordinal)` when the wrong-ordinal column is non-integer**: this is a downstream symptom of the line-328 collision finding, not an independent issue; folded into that finding.

Note: findings at line 393 (assertion fires) and the wrong-ordinal read border on quick-reviewer/line-level territory, but I report them here because both are direct, observable consequences of the two data-model decisions (dropping the negative sentinel; the ambiguous key) rather than isolated coding slips.
