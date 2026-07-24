# subagent agent-acee981a453454ea8

## Summary

Fixes a bug in `SqliteDataRecord.GetStream` where a single cached `_rowidOrdinal` field caused blob reads to return wrong data when a query joined multiple tables, each needing its own rowid ordinal. The fix replaces the single nullable ordinal with a `Dictionary<string, RowIdInfo>` keyed by `database_table`, so each table's rowid ordinal is resolved and cached independently. A regression test with a two-table join exercises reading blob columns from both tables.

**Type:** bugfix
**Effort:** 2/5 — small, localized change (one method rewritten, ~25 net lines) plus a new test; no public API surface change

## Walkthrough

| File | Change | Summary |
|------|--------|---------|
| src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs | Modified | Replaces single `_rowidOrdinal` field with per-table `RowIdInfo` cache (new nested class + `Dictionary<string, RowIdInfo>` keyed by db/table name) in `GetStream`, fixing incorrect rowid reuse across joined tables |
| test/Microsoft.Data.Sqlite.Tests/SqliteDataReaderTest.cs | Added | New `GetBytes_works_streaming_join` test verifying blob streaming works correctly when reading from two joined tables in one query |

Notes for reviewers (not part of the generated overview, flagged separately):
- `src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs:39` — the new `RowIds` field has no explicit access modifier (defaults to `private`, which is correct) but uses PascalCase naming, inconsistent with the surrounding `_camelCase` private-field convention in this file (e.g., `_blobCache`, `_columnNameCache`).
- Minor style nits introduced by the diff: a stray blank line added right after the `namespace` opening brace (`SqliteDataRecord.cs:17`), and `Debug.Assert(rowIdForOrdinal!=null)` (`SqliteDataRecord.cs:396`) lacks spaces around `!=`, unlike existing code style.
- `RowIds.TryGetValue(rowidkey, out rowIdForOrdinal)` pattern (`SqliteDataRecord.cs:329`) reimplements what could be `RowIds.TryGetValue(rowidkey, out var rowIdForOrdinal)` — a trivial idiom simplification, not a correctness issue.
