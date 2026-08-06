# subagent agent-ac66604c85ec15b04

Verdict: **confirmed**.

I read the actual code at `src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs:316-400` (the `GetStream` method) and traced the failure path with concrete ordinals. Key evidence:

- `sqlite3_column_table_name`/`sqlite3_column_database_name` (lines 324-325) return the origin (base) table/database name — this is documented SQLite C-API behavior; query aliases are not exposed by these routines.
- The cache key at line 328, `$"{blobDatabaseName}_{blobTableName}"`, is built purely from those base names, so two aliases of the same table produce the identical key.
- The inner scan (lines 339-349) that locates a candidate rowid/PK column also filters only by base `databaseName`/`tableName`, with no alias disambiguation, so it can match a column belonging to the *other* alias.
- `RowIds` (line 39) is a plain `Dictionary<string, RowIdInfo>` keyed by that colliding string, and line 329's `TryGetValue` means the second alias's blob lookup silently reuses the first alias's cached ordinal.

Confirmed via git history (`git log -- SqliteDataRecord.cs`, commit `9e69b85`, PR #32770 "Microsoft.Data.Sqlite.Core issue with multiple Blob columns") that this exact code is the change under review — not pre-existing — so attribution is correct.

The resulting behavior matches the finding exactly: for a self-join with both aliases' id and blob columns selected, the second alias's `GetStream` call reads the rowid from the wrong alias's id column and opens `SqliteBlob` against the wrong (but still valid) row in the shared base table, producing silently wrong blob bytes rather than a throw. No caller-side guard, framework constraint, or existing check in the file prevents this. The finding's location, category, and reasoning all hold up.
