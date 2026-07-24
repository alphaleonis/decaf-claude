# subagent agent-a9ee1542bbe814ad8

## Summary

**PR Title:** Microsoft.Data.Sqlite.Core issue with multiple Blob columns

**URL:** https://github.com/dotnet/efcore/pull/32770

**Linked Issue:** #32747

### What Changed & Why

The fix addresses a bug in `SqliteDataRecord` where streaming blob data from SQL queries with joins failed when multiple tables had blob columns. The original implementation stored only a single `_rowidOrdinal` value, which couldn't distinguish between rowids from different tables in a join. The change introduces a new inner class `RowIdInfo` that stores both the ordinal position and the associated table name for each rowid, then replaces the single nullable int field with a dictionary keyed by `{databaseName}_{tableName}`. This allows the `GetStream()` method to correctly look up the rowid for each blob column based on its source table, enabling proper streaming in joined result sets.

### Changed Files

| File | Additions | Deletions |
|------|-----------|-----------|
| src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs | 25 | 9 |
| test/Microsoft.Data.Sqlite.Tests/SqliteDataReaderTest.cs | 38 | 0 |

### Notable Implementation Details

- **New RowIdInfo class:** Replaces the single nullable int with a structured type holding ordinal and table name
- **Dictionary-based cache:** `RowIds` dictionary maps composite keys (`{database}_{table}`) to `RowIdInfo` objects, enabling multiple rowid tracking
- **GetStream() refactoring:** Updated to perform dictionary lookup before iterating columns; stores `RowIdInfo` objects instead of plain int values
- **Test coverage:** New `GetBytes_works_streaming_join()` test verifies the fix works correctly with a join of two tables (A and B), reading blob columns from both with `GetBytes()`
