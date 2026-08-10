# subagent agent-a107ffc5dad408172

## Review Scope

Reviewed the diff for dotnet/efcore PR #32770 (commit `9e69b85`, base `7128186`):
- `src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs` (the `RowIdInfo`/`RowIds` refactor of `GetStream`)
- `test/Microsoft.Data.Sqlite.Tests/SqliteDataReaderTest.cs` (new `GetBytes_works_streaming_join` test)

Cross-checked against pre-existing tests (`GetStream_works_when_composite_pk`, `GetStream_works_when_composite_pk_and_rowid`) and `.editorconfig`/`stylecop.json` naming rules.

## Critical / High

**1. `Debug.Assert` now encodes a false invariant and fires on an existing, correctly-handled code path**
`src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs:393`
Confidence: 90

```csharp
Debug.Assert(rowIdForOrdinal!=null);
```

In the old code, `_rowidOrdinal` was pre-seeded to `-1` before the scan loop, so `Debug.Assert(_rowidOrdinal.HasValue)` was trivially always true regardless of whether a rowid was actually found — it asserted nothing meaningful. In the new code `rowIdForOrdinal` starts as `null` and is only assigned inside the loop's two `break` branches (rowid alias found, or single-column INTEGER PK found). For a table with a composite primary key (or a `WITHOUT ROWID` table/view) where no rowid column was selected, the loop legitimately completes with `rowIdForOrdinal == null` — and the very next block (`if (rowIdForOrdinal == null) return new MemoryStream(...)`) is the intended handling for exactly that case. This is not a hypothetical: the pre-existing test `GetStream_works_when_composite_pk` (`test/Microsoft.Data.Sqlite.Tests/SqliteDataReaderTest.cs:516-541`) exercises precisely this path and expects a `MemoryStream` result. So the assert now fires on a known-good, tested scenario.

Fix: delete the assert (it no longer expresses a true invariant), or move any invariant check inside the `break` branches where it would actually hold.

**2. Negative lookup result is never cached, causing repeated table scans + extra SQL round-trips**
`src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs:327-394`
Confidence: 85

`RowIds.Add(rowidkey, rowIdForOrdinal)` is only called inside the two `break` branches. When no rowid/single-PK column is found (composite PK, view, `WITHOUT ROWID` table), nothing is stored under `rowidkey`. Every subsequent `GetStream` call on a blob column of that table therefore re-runs the full `FieldCount` scan and re-executes the `pragma_table_info` `ExecuteScalar` query, instead of short-circuiting as the old `_rowidOrdinal = -1` sentinel did.

Fix: cache the negative result too, e.g. use `Dictionary<string, RowIdInfo?>` and unconditionally do `RowIds[rowidkey] = rowIdForOrdinal;` after the loop; check membership with `TryGetValue` (which correctly reports "found, value null" vs "not found").

**3. Dictionary key built by naive string concatenation risks collisions between distinct tables**
`src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs:328`
Confidence: 78

```csharp
string rowidkey = $"{blobDatabaseName}_{blobTableName}";
```

Because `_` is both the separator and a legal character in SQLite identifiers, two different `(database, table)` pairs can produce the same key — e.g. database `main`, table `foo_bar` vs. database `main_foo`, table `bar` both yield `"main_foo_bar"`. If that happens, `GetStream` would reuse a `RowIdInfo` (ordinal/ ) computed for the wrong table, silently opening a `SqliteBlob`/reading a rowid against the wrong column — a data-correctness bug, not just a cosmetic one.

Fix: use a proper composite key instead of concatenation, e.g. `Dictionary<(string Database, string Table), RowIdInfo>`.

## Medium / Low (convention & quality)

**4. New field doesn't follow this file's private-field naming convention**
`src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs:39`
Confidence: 90

```csharp
readonly Dictionary<string, RowIdInfo> RowIds = new Dictionary<string, RowIdInfo>();
```

Every other field in this class is declared `private` and `_camelCase` (`_connection`, `_addChanges`, `_blobCache`, `_typeCache`, `_columnNameOrdinalCache`, `_columnNameCache`, `_stepped`, `_alreadyThrown`, `_alreadyAddedChanges`). `RowIds` uses PascalCase with no explicit access modifier, which is inconsistent with the established local convention (`.editorconfig` also defines a `_camelCase` naming style for this purpose).

Fix: `private readonly Dictionary<string, RowIdInfo> _rowIds = new();` and update all call sites.

**5. Local variable naming inconsistent with the rest of the method**
`src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs:328`
Confidence: 78

`rowidkey` breaks camelCase, unlike sibling locals in the same method (`blobDatabaseName`, `blobTableName`, `blobColumnName`, `pkColumns`). Should be `rowIdKey`.

**6. `RowIdInfo.TableName` is set but never read**
`src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs:23,28,354,386`
Confidence: 82

Verified via grep — `TableName` is assigned in the constructor and at both call sites but never consumed anywhere else in the codebase. It's dead data that adds confusion about what actually distinguishes cache entries (the real key is the `rowidkey` string, not this field).

Fix: drop the unused `TableName` property/parameter, or use it to replace the concatenated string key (addressing finding 3) so it's not dead weight.

**7. Leftover debug output and narrative comment in the new test**
`test/Microsoft.Data.Sqlite.Tests/SqliteDataReaderTest.cs:171,179`
Confidence: 80

```csharp
Console.WriteLine($"A.ID={reader.GetInt32(0)} B.ID={reader.GetInt32(2)}");
...
reader.GetBytes(3, 1, bbuff, 0, bbuff.Length);  //this was failing. now should be fixed
```

This is the only `Console.WriteLine` in the entire test file — looks like a leftover debugging artifact rather than an intentional assertion, and the comment narrates the bug-fix history rather than describing current behavior (tests elsewhere in the file rely solely on `Assert.*`).

Fix: remove the `Console.WriteLine` (it asserts nothing) and replace the comment with one describing what the assertion verifies (e.g. "verifies the second table's blob column resolves its own rowid, not the first table's").

## Summary

The core approach (caching rowid lookups per source table instead of one field per `SqliteDataRecord`) correctly addresses the multi-table-join bug described in the PR, and the new join test is a reasonable regression test. However, the refactor introduces a logic defect in the `Debug.Assert` (finding 1, reachable via an existing pre-existing test), drops the negative-result caching that the original sentinel-based design relied on (finding 2), and uses a collision-prone string-concatenation cache key (finding 3). There are also several naming/convention deviations from the surrounding file (findings 4-6) and test hygiene nits (finding 7).
