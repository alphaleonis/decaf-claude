# subagent agent-af9eddbda6fe30a77

## Summary

Fixes a bug in `SqliteDataRecord.GetStream` where the rowid ordinal used to resolve `SqliteBlob` streams was cached in a single `int?` field (`_rowidOrdinal`), shared across all columns read from the record. When a query joined multiple tables and streamed BLOB columns from more than one of them, the cached rowid ordinal from the first table was incorrectly reused for the second table's BLOB column, producing wrong or failing reads. The fix replaces the single cached ordinal with a `Dictionary<string, RowIdInfo>` keyed by `"{databaseName}_{tableName}"`, so each source table gets its own resolved rowid ordinal, and adds a regression test covering a two-table join with BLOB columns on both sides.

**Type:** bug fix
**Effort:** 2/5 — small, self-contained change (25 lines source / 38 lines test) confined to one method (`GetStream`), but requires understanding the SQLite blob/rowid-resolution caching logic to verify correctness of the new per-table keying.

## Walkthrough

| File | Change | Summary |
|------|--------|---------|
| src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs | Modified | Replaces single `_rowidOrdinal` field with a `Dictionary<string, RowIdInfo>` keyed by database+table name (new nested `RowIdInfo` class holding `Ordinal`/`TableName`), so `GetStream` resolves and caches a distinct rowid ordinal per source table instead of one shared value |
| test/Microsoft.Data.Sqlite.Tests/SqliteDataReaderTest.cs | Added | New `GetBytes_works_streaming_join` test joining two tables (A, B) and streaming BLOB columns from both via `GetBytes`, verifying the previously-failing multi-table rowid case now works |

## Related Issues & PRs

<!-- issue-linker output will be merged here — the orchestrator replaces this placeholder -->
