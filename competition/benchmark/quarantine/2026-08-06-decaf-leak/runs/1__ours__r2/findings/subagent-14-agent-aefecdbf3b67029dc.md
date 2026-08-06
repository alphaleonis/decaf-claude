# subagent agent-aefecdbf3b67029dc

## Spec Compliance Review — PR #32770 (fixes issue #32747)

**Spec source**: `linked` (GitHub issue #32747, Bug — description + repro + stack trace). Reviewed at full strength.

**Requirements extracted:**
- R1 (functional): A joined query with blob columns from two different tables must allow `GetBytes`/`GetStream` on both blobs without `SQLite Error 1: 'no such rowid'`.
- R2 (constraint, root cause): The rowid ordinal must be resolved per table, not cached once for the whole record ("The first line caches a rowid that is not usable for the second line").
- R3 (edge, from repro): The null-buffer length-query form `GetBytes(ordinal, 0, null, 0, 0)` must work on both blobs.
- R4 (constraint, implied by generality): Two *different* (database, table) pairs must never share one cached rowid entry.
- R5 (implicit regression constraint of any bug fix): Previously working blob paths — composite-PK fallback to `MemoryStream`, expression-column streams, explicit `rowid` selection — must keep working.
- R6 (edge, from issue title "multiple Blob colums"): Multiple blob columns resolving to different rows of the *same* table (self-join) — same failure class ("caches a rowid that is not usable for the second line").

```json
[
  {
    "file": "src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs",
    "line": 393,
    "severity": "Medium",
    "category": "spec-compliance",
    "issue": "[SPEC_UNCOVERED] Behavioral change beyond the spec: the old `Debug.Assert(_rowidOrdinal.HasValue)` was vacuously true (the field was pre-set to -1), but the re-added `Debug.Assert(rowIdForOrdinal!=null)` now fires on every legitimate no-rowid fallback path — composite-PK tables without rowid in the SELECT (existing test GetStream_works_when_composite_pk, line 516) and expression columns (GetTextReader_works, GetStream_works_with_text/int/float). The bug spec asks only to fix per-table rowid caching; this converts a supported fallback (return MemoryStream) into an assertion failure in DEBUG builds. Release builds are unaffected (Debug.Assert compiles out).",
    "fix": "Restore the assert's original vacuous/no-op semantics or delete it — e.g., only assert when the table actually has a usable rowid, or cache a negative sentinel entry and assert the dictionary lookup completed. Do not assert non-null on a path where null is a designed outcome.",
    "confidence": 75,
    "pre_existing": false
  },
  {
    "file": "src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs",
    "line": 328,
    "severity": "Medium",
    "category": "spec-compliance",
    "issue": "[SPEC_EDGE_CASE] The cache key `$\"{blobDatabaseName}_{blobTableName}\"` concatenates with an ambiguous separator, so distinct (database, table) pairs can collide — e.g., attached database alias \"x\" with table \"y_z\" and attached alias \"x_y\" with table \"z\" both produce key \"x_y_z\". A collision makes the second table reuse the first table's rowid ordinal, reproducing the exact spec failure the PR fixes ('no such rowid') or silently streaming the wrong row's blob. Violates R4 (different tables must never share a cache entry); '_' is legal and common in SQLite database aliases and table names.",
    "fix": "Key the dictionary on the (databaseName, tableName) tuple — e.g., Dictionary<(string?, string?), RowIdInfo> or a composite key with an unambiguous encoding — instead of string concatenation with '_'.",
    "confidence": 75,
    "pre_existing": false
  },
  {
    "file": "src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs",
    "line": 345,
    "severity": "Medium",
    "category": "spec-compliance",
    "issue": "[SPEC_EDGE_CASE] Self-join case of the same bug class remains broken: for `SELECT a1.ID, a1.VALUE, a2.ID, a2.VALUE FROM A a1 JOIN A a2 ...`, sqlite3_column_table_name returns the real table name (aliases are not exposed), so both blob columns share cache key \"main_A\" and both resolve rowid from a1.ID — a2's blob is then read from a1's row (silently wrong data). The issue title says 'multiple Blob colums' and the root cause ('caches a rowid that is not usable for the second line') applies identically, though the issue body's literal wording is 'two different tables', so this reading is a generalization. Behavior is unchanged from before the PR (pre-existing limitation the fix does not extend to).",
    "fix": "If not addressable at this layer (no sqlite3 API for result-column table alias), document the limitation; a partial mitigation is to prefer the nearest same-table INTEGER-PK column by ordinal proximity rather than always the first match.",
    "confidence": 75,
    "pre_existing": true
  }
]
```

## Requirement Coverage Matrix

| Req | Description | Status | Evidence |
|-----|-------------|--------|----------|
| R1 | Blobs from two different tables in one JOIN readable without 'no such rowid' | Covered | `src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs:327-404` — per-table `RowIds` dictionary; verified against the test at `test/Microsoft.Data.Sqlite.Tests/SqliteDataReaderTest.cs:149-181` (A.VALUE resolves ordinal 0 for rowid 1, B.VALUE resolves ordinal 2 for rowid 1000) |
| R2 | Rowid resolved per table, not once per record | Covered | `SqliteDataRecord.cs:329` — lookup keyed by database+table; positive results cached per table |
| R3 | Null-buffer `GetBytes(ord, 0, null, 0, 0)` length query works on both blobs | Covered | `SqliteDataRecord.cs:274-286` — null-buffer path routes through the same fixed `GetStream`; returns `SqliteBlob.Length` (added test exercises the non-null-buffer variant of the same path) |
| R4 | Distinct (database, table) pairs never share a cache entry | Partial | `SqliteDataRecord.cs:328` — string-concat key with `_` separator can collide across attached databases (finding 2) |
| R5 | Previously working blob paths unregressed | Deviated (Debug builds) | `SqliteDataRecord.cs:393` — non-vacuous assert fires on the no-rowid fallback path reachable by pre-existing tests (`SqliteDataReaderTest.cs:516`, `:580`); Release behavior unchanged (finding 1) |
| R6 | Multiple blob columns from same table via self-join | Missing (pre-existing) | `SqliteDataRecord.cs:345` — table-name keying cannot distinguish aliases; same wrong-rowid failure class as the issue (finding 3) |

## Considered But Not Flagged

- **Negative-result caching removed (perf, not compliance)**: old code cached `_rowidOrdinal = -1` so the ordinal scan + `pragma_table_info` COUNT(*) query ran once per reader; new code never caches a "no rowid" result, so every `GetStream`/`GetBytes`/`GetChars`/`GetTextReader` call on a fallback-path column re-runs the full scan including `sqlite3_table_column_metadata` calls and a command execution. Functionally identical output; performance-reviewer scope.
- **`RowIdInfo.TableName` is write-only**: stored at `SqliteDataRecord.cs:354/386`, never read. Dead code, not behavioral scope creep; quick/design-reviewer scope.
- **Test uses non-null buffers while the repro used the null-buffer length form**: same `GetStream` code path, so implementation compliance is unaffected; the coverage nuance (plus the `Console.WriteLine` in the test and single-row read vs. the repro's `while` loop) is test-reviewer scope.
- **Expression columns / null table names sharing key `"_"`**: all expression columns collapse to one cache key, but expressions never resolve a rowid (scan requires matching table columns) and nothing is cached on the null path, so no wrong behavior results beyond the R5 assert already flagged.
- **`WITHOUT ROWID` tables and `sqlite3_table_column_metadata` on null names**: pre-existing loop semantics unchanged by this PR; not part of the spec.
- **Style issues** (stray blank line after `namespace`, `RowIds` field naming/`private` omission, `!=` spacing): consistency-reviewer scope, not spec compliance.

Key file: `/home/decaf/code/decaf-claude/competition/benchmark/repos/1/src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs` (fix), `/home/decaf/code/decaf-claude/competition/benchmark/repos/1/test/Microsoft.Data.Sqlite.Tests/SqliteDataReaderTest.cs` (added test).

[Unverified] Note: no .NET SDK is available this session, so all conclusions are from static reasoning; the Debug.Assert consequence (process fail-fast in Debug test runs) is expected .NET-Core behavior, not verified by execution here.
