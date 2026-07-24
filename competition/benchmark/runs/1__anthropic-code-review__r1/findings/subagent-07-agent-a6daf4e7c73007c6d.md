# subagent agent-a6daf4e7c73007c6d

## Summary

**Problem:** PR #32770 fixes issue #32747 — `SqliteDataRecord` could only handle a single rowid, causing failures when executing SQL queries with joins and multiple blob columns from different tables.

**Approach:** The fix replaces the single nullable `_rowidOrdinal` field with a dictionary-based caching strategy:
- Introduces a new `RowIdInfo` class to store both the column ordinal and the table name it references
- Replaces the global nullable `int?` with a `Dictionary<string, RowIdInfo>` keyed by `"{databaseName}_{tableName}"` to track rowids per table
- When retrieving a blob stream, the code now caches the rowid information by table reference rather than globally, enabling proper handling of multiple blob columns from different tables in join queries

**Files Modified:**

1. **SqliteDataRecord.cs** — Core logic changes:
   - Adds inner `RowIdInfo` class with `Ordinal` and `TableName` properties
   - Replaces `_rowidOrdinal` field with `Dictionary<string, RowIdInfo> RowIds`
   - Modifies `GetStream()` method to use the dictionary with a table-based key
   - Updates the rowid lookup and caching logic to handle multiple tables

2. **SqliteDataReaderTest.cs** — Test coverage:
   - Adds `GetBytes_works_streaming_join()` test that validates blob streaming from multiple tables in a join scenario
   - Creates two tables with blob columns and executes a join query
   - Verifies that reading blob bytes from both tables succeeds correctly

The fix allows Entity Framework Core to properly handle scenarios where queries retrieve blob data from multiple tables, resolving a regression in blob column handling for complex queries.
