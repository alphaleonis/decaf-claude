# subagent agent-a398fe565f34590fe

```json
[
  {
    "file": "src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs",
    "line": 393,
    "severity": "High",
    "category": "error-handling",
    "issue": "[BUG_LOGIC] `Debug.Assert(rowIdForOrdinal!=null)` now fires on a legitimate, expected code path — any blob column whose owning table has no single-column INTEGER PRIMARY KEY (composite PK, WITHOUT ROWID table, etc.) leaves `rowIdForOrdinal` null after the search loop, which is the normal 'fall back to a cached-blob MemoryStream' case handled a few lines below. This is verifiably reached by the pre-existing test `GetStream_works_when_composite_pk` (test/Microsoft.Data.Sqlite.Tests/SqliteDataReaderTest.cs:515-541): table `DataTable(Id1 INTEGER, Id2 INTEGER, Data BLOB, PRIMARY KEY (Id1, Id2))` has `pkColumns == 2`, so the loop never sets `rowIdForOrdinal`, and the assert trips. In the original code this same case was harmless because `_rowidOrdinal` was pre-set to the sentinel `-1` before the loop ran, so `_rowidOrdinal.HasValue` was trivially true and the assert never fired for this scenario.",
    "fix": "Remove the assert, or replace it with a check that only fires for a genuine internal-invariant violation, not for the expected 'no qualifying rowid/PK column' outcome. E.g. drop `Debug.Assert(rowIdForOrdinal!=null)` entirely since the following `if (rowIdForOrdinal == null)` branch already handles this case correctly.",
    "confidence": 100,
    "pre_existing": false
  },
  {
    "file": "src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs",
    "line": 396,
    "severity": "Medium",
    "category": "performance",
    "issue": "[QUALITY_ERROR_HANDLING] Negative lookup results are never cached. `RowIds.Add(rowidkey, ...)` is only called inside the two branches where a rowid/PK ordinal is actually found; when no such column exists for a (database, table) pair (composite PK, no rowid, etc.), nothing is written to `RowIds`. The original code cached the negative outcome too (`_rowidOrdinal = -1` before the loop). As a result, every subsequent `GetStream`/`GetBytes` call on a blob column from such a table — i.e. once per row in a result set — re-runs the full metadata-discovery loop, including a fresh `sqlite3_table_column_metadata` call per column and a `SELECT COUNT(*) FROM pragma_table_info($table)` sub-query via `command.ExecuteScalar()`, instead of hitting the cache.",
    "fix": "After the loop, cache the outcome unconditionally (even when null), e.g. `RowIds[rowidkey] = rowIdForOrdinal;` right before the `Debug.Assert`/fallback check, so a 'no qualifying rowid' result is remembered per (database, table) just like a found one.",
    "confidence": 100,
    "pre_existing": false
  },
  {
    "file": "src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs",
    "line": 328,
    "severity": "Medium",
    "category": "other",
    "issue": "[BUG_LOGIC] The cache key `$\"{blobDatabaseName}_{blobTableName}\"` is built by naive string concatenation with a fixed `_` separator, which is not collision-free: two distinct (database, table) pairs can produce the same key if a name contains an underscore at the right position (e.g. database `main`, table `A_B` vs. database `main_A`, table `B` both yield `main_A_B`). Since `RowIds` maps this key straight to a cached column ordinal, a collision would cause the wrong table's rowid ordinal to be reused for another table's blob — the exact class of bug (#32747) this PR is fixing, just requiring specific attached-database/table naming instead of a plain multi-table join.",
    "fix": "Key the dictionary on a tuple instead of a concatenated string, e.g. `Dictionary<(string? Database, string? Table), RowIdInfo>` keyed by `(blobDatabaseName, blobTableName)`, which removes any possibility of concatenation collisions.",
    "confidence": 50,
    "pre_existing": false
  },
  {
    "file": "src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs",
    "line": 23,
    "severity": "Low",
    "category": "unused-code",
    "issue": "[QUALITY_DUPLICATION] `RowIdInfo.TableName` is set in the constructor but never read anywhere in the file (only `Ordinal` is consumed at line 402); it's dead state carried on every cache entry.",
    "fix": "Drop the `TableName` property/constructor parameter from `RowIdInfo` (keep just `Ordinal`), or use it if it was intended to replace the local `tableName`/`blobTableName` variables.",
    "confidence": 100,
    "pre_existing": false
  }
]
```

## Considered But Not Flagged

- **`RowIds` field naming** (`readonly Dictionary<string, RowIdInfo> RowIds = ...`) breaks from the file's established `_camelCase` private-field convention (`_connection`, `_blobCache`, `_stepped`, etc.). `.editorconfig` defines a `_camelCase` naming style but no active `dotnet_naming_rule` actually binds it to private fields, so this isn't a documented/enforced convention violation — it's an unwritten pattern only visible by comparing against sibling code in the same class, which is consistency-reviewer's territory, not mine.
- **Extra blank line** inserted after the `namespace` opening brace (line 17) — trivial whitespace noise, not worth flagging on its own.
- **Null `blobDatabaseName`/`blobTableName` collapsing to a single `"_"` key** for expression/literal blob columns without a source table — this reproduces the same "one bucket for all non-table blobs" behavior the original single-field cache already had, so it's not a new regression introduced by this diff.
- **Public setters on `RowIdInfo.Ordinal`/`TableName`** (`{ get; set; }` instead of read-only/init-only) — a minor design nit with no observable behavioral effect since both are only ever set from the constructor; not worth a finding on its own.
- **`GetBytes_works_streaming_join` test correctness** — verified the test's own logic is sound: both tables have a genuine single-column `INTEGER PRIMARY KEY`, so `pkColumns == 1` is reached for each and `rowIdForOrdinal` is found without tripping the assert; the test itself is not defective, it simply doesn't exercise the composite-PK/no-rowid path where the regression above lives.
