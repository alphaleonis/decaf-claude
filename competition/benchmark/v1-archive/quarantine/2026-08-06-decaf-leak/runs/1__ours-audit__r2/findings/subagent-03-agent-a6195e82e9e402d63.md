# subagent agent-a6195e82e9e402d63

Confirmed: `_record` is disposed and recreated on every `NextResult()` (lines 142-145, 180), so `RowIds` lifetime matches a single statement's column layout — column ordinals are stable for the record's life. The seed's "stale cache across NextResult" concern does not hold; no finding there.

Depth: standard — ~20 executable lines, but external-API (native SQLite blob) integration touched. Applied assumption + composition + abuse construction.

Findings:

```json
[
  {
    "file": "src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs",
    "line": 393,
    "severity": "Medium",
    "category": "error-handling",
    "issue": "[ADV_ASSUMPTION] GetStream on a blob whose table has no single-integer rowid (literal/expression blob e.g. `SELECT x'01'`, a WITHOUT ROWID table, or a composite-PK table) → scan loop completes with rowIdForOrdinal still null → Debug.Assert(rowIdForOrdinal!=null) fires. The original code seeded _rowidOrdinal=-1 so the equivalent assert (_rowidOrdinal.HasValue) was ALWAYS satisfied and never fired. In debug builds of the assembly (contributor builds, EF Core test runs) this now aborts on a legitimate no-rowid blob read. Release (shipped) builds compile the assert out, so end users are unaffected.",
    "fix": "Remove the Debug.Assert, or make it assert the intended postcondition explicitly (e.g. assert only inside the branch where a rowid column was found), since 'no rowid found' is a legitimate outcome the very next line (rowIdForOrdinal == null) is designed to handle.",
    "confidence": 100,
    "pre_existing": false
  },
  {
    "file": "src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs",
    "line": 329,
    "severity": "Medium",
    "category": "performance",
    "issue": "[ADV_ABUSE] Negative result is never cached: RowIds.Add is called ONLY when a rowid is found (lines 355, 387); when the scan finds none, nothing is stored. The original _rowidOrdinal cached the negative result (-1). Scenario: iterate a large result set reading a blob column from a table with no single-integer rowid (composite INTEGER PK, or WITHOUT ROWID) via GetBytes/GetChars (each internally calls GetStream, lines 276/290). Every row re-runs the full O(FieldCount) column scan AND — for the composite-integer-PK case — re-executes the `SELECT COUNT(*) FROM pragma_table_info(...)` round-trip (lines 375-381) that used to run at most once per column. N rows → N redundant pragma queries + N rescans.",
    "fix": "Cache the negative result too: after the scan, unconditionally store the outcome (e.g. RowIds[rowidkey] = rowIdForOrdinal, allowing a null/sentinel entry) so a no-rowid table is resolved once per record, matching the prior negative-cache behavior.",
    "confidence": 75,
    "pre_existing": false
  },
  {
    "file": "src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs",
    "line": 328,
    "severity": "High",
    "category": "other",
    "issue": "[ADV_COMPOSITION] Cache key `$\"{blobDatabaseName}_{blobTableName}\"` is an ambiguous concatenation: distinct (database, table) pairs can collide on the same string. Concrete: ATTACH a database named `main_foo`; run one query joining `main_foo`.`bar` (blob col) with `main`.`foo_bar` (blob col). Both keys resolve to `main_foo_bar`. The first blob column read caches a RowIdInfo whose Ordinal points at the FIRST table's rowid column within the shared result set; the second column's GetStream then reuses that cached Ordinal, so GetInt64(rowIdForOrdinal.Ordinal) reads the wrong table's rowid and SqliteBlob is opened on the second table at a foreign rowid → wrong blob bytes returned silently, or SqliteException if that rowid is absent.",
    "fix": "Use a composite key that cannot collide — a struct/tuple key (blobDatabaseName, blobTableName) via Dictionary<(string,string),RowIdInfo>, or a delimiter that cannot appear in identifiers combined with length-prefixing. Avoid string concatenation of two free-form identifiers into one key.",
    "confidence": 50,
    "pre_existing": false
  }
]
```

## Considered But Not Flagged

- Two blob columns from the SAME table sharing one key: not a bug. RowIdInfo.Ordinal is the rowid column's position in the result set, identical regardless of which blob column is being read — this is the intended fix. (Backward check: reusing the cached ordinal produces the same correct rowid for both columns.)
- Stale cache across re-executed reader / NextResult: dismissed. SqliteDataReader.NextResult disposes and nulls `_record` (SqliteDataReader.cs:142-145) and constructs a fresh SqliteDataRecord per statement (line 180), so RowIds never outlives the column layout it was built against. The old `int? _rowidOrdinal` had identical lifetime — no regression.
- Concurrency on the non-thread-safe `Dictionary` `RowIds`: fell apart — a DbDataReader/record is single-threaded per ADO.NET contract; no concrete concurrent-caller path exists within this class.
- Null table/database name for expression blobs producing key `"_"`: two such columns collide on the same key, but both take the no-rowid path and (given they never Add) cache nothing, so the collision causes no wrong-data outcome. Not flagged (only the performance point in finding B applies).
