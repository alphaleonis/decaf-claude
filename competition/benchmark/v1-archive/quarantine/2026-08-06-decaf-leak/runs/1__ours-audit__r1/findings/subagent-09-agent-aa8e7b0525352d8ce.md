# subagent agent-aa8e7b0525352d8ce

```json
[
  {
    "file": "src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs",
    "line": 393,
    "severity": "High",
    "category": "other",
    "issue": "[BUG_LOGIC] `Debug.Assert(rowIdForOrdinal!=null)` now asserts a condition that is legitimately false and is immediately handled by the code three lines later (`if (rowIdForOrdinal == null) { return new MemoryStream(...) }`). In the old code `_rowidOrdinal` was always assigned (defaulted to -1), so the equivalent assert was a tautology. In the new code, when a blob's table has no single-column integer rowid alias (WITHOUT ROWID table, composite PK, view, etc.) the loop legitimately exits without ever assigning `rowIdForOrdinal`, and the assert fires for a case the surrounding code explicitly supports.",
    "fix": "Remove the assert, or move/rewrite it so it only checks internal consistency and does not contradict the following null-check — e.g. delete it entirely since `rowIdForOrdinal == null` is now a valid, handled outcome.",
    "confidence": 100,
    "pre_existing": false
  },
  {
    "file": "src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs",
    "line": 328,
    "severity": "Medium",
    "category": "other",
    "issue": "[BUG_LOGIC] The cache key `$\"{blobDatabaseName}_{blobTableName}\"` is built by naive string concatenation with `_` as separator. Database or table names containing underscores can collide: `(db=\"a\", table=\"b_c\")` and `(db=\"a_b\", table=\"c\")` both produce key `\"a_b_c\"`. A collision causes `GetStream` to reuse a cached `RowIdInfo` (ordinal + rowid) computed for the wrong table, so `GetInt64(rowIdForOrdinal.Ordinal)` reads the wrong column as the rowid and `SqliteBlob` is opened against the wrong row/table — silently returning wrong blob data or throwing 'no such rowid', the exact class of bug this PR is fixing, just via a different collision path.",
    "fix": "Use a collision-safe composite key, e.g. a `(string Database, string Table)` tuple or `ValueTuple<string,string>` as the dictionary key instead of string concatenation, or key with an unambiguous separator plus explicit lengths.",
    "confidence": 75,
    "pre_existing": false
  },
  {
    "file": "src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs",
    "line": 329,
    "severity": "Medium",
    "category": "performance",
    "issue": "[QUALITY_ERROR_HANDLING] The old code cached the negative result (`_rowidOrdinal = -1`) so a table with no discoverable rowid was scanned only once per reader lifetime. The new code adds to `RowIds` only inside the two `break` branches, so when no rowid ordinal is found (views, WITHOUT ROWID tables, composite-PK tables), nothing is cached and the full `FieldCount` scan — including the `sqlite3_table_column_metadata` call and, on the first PK column, an actual `SELECT COUNT(*) FROM pragma_table_info(...)` query — re-runs on every single `GetStream` call for that table, for every row.",
    "fix": "Cache the negative outcome too, e.g. store a sentinel/null-valued entry (or a `RowIdInfo` with `Ordinal = -1`) in `RowIds` when the loop completes without finding a rowid, mirroring the old `_rowidOrdinal = -1` short-circuit.",
    "confidence": 75,
    "pre_existing": false
  },
  {
    "file": "src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs",
    "line": 23,
    "severity": "Low",
    "category": "unused-code",
    "issue": "[QUALITY_DUPLICATION] `RowIdInfo.TableName` is populated on every construction (line 28) but never read anywhere in the file — `GetStream` uses the local `blobTableName` variable instead when building the `SqliteBlob` (line 404). The property is dead state carried on every cached entry.",
    "fix": "Drop the `TableName` property/constructor parameter from `RowIdInfo` (keep just `Ordinal`), or use `rowIdForOrdinal.TableName` at line 404 if it was meant to replace `blobTableName`.",
    "confidence": 100,
    "pre_existing": false
  },
  {
    "file": "test/Microsoft.Data.Sqlite.Tests/SqliteDataReaderTest.cs",
    "line": 148,
    "severity": "Low",
    "category": "other",
    "issue": "[test-coverage] The new `GetBytes_works_streaming_join` test only exercises the \"happy path\" (two tables, both with a simple integer-PK rowid). It doesn't cover the case this diff's caching change most affects: a joined table with no discoverable rowid (WITHOUT ROWID table, view, or composite PK) hit across multiple `GetStream`/`Read()` calls, nor a database/table-name pair that would probe the `_`-concatenation key-collision scenario above.",
    "fix": "Add a regression test with a WITHOUT ROWID or composite-PK table joined to a normal table, reading its blob column across multiple rows, and (if the key-collision fix is applied) a test with underscore-containing table/db names from two different logical tables.",
    "confidence": 50,
    "pre_existing": false
  }
]
```

## Considered But Not Flagged

- **`RowIds` field naming (`RowIds` vs. `_rowIds`) and missing explicit `private` modifier**: every other field in this class uses the `_camelCase` convention with explicit `private readonly`. This is a real drift from sibling code, but the repo's `.editorconfig` has no enforced naming rule for private instance fields (only public fields and const fields have naming rules), so this is unwritten sibling-convention drift — routed to `consistency-reviewer`, not flagged here.
- **`RowIdInfo` as a public-set mutable class vs. a `readonly record struct`**: stylistic; the class is only ever constructed once and never mutated post-construction, so no correctness impact. Left to a design/refactor pass rather than flagged as a defect.
- **Blank line inserted after `namespace Microsoft.Data.Sqlite\n{`**: purely cosmetic whitespace, no functional or convention impact worth a finding.
- **Thread-safety of `RowIds` dictionary**: not annotated/protected, but `SqliteDataRecord`/`SqliteDataReader` were never documented or implemented as thread-safe before this change either (`_blobCache`, `_typeCache`, etc. have the same exposure) — pre-existing design assumption, not introduced by this diff.
- **`Console.WriteLine` left in the new test**: test-file style issue, in `test-reviewer`'s domain, not flagged here.
