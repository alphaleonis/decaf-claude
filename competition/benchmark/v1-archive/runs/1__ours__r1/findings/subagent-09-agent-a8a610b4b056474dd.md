# subagent agent-a8a610b4b056474dd

## Spec Compliance Review — PR #32770 (fixes #32747)

**Spec source**: `linked` (GitHub issue #32747, sole closing reference) — reviewed at full strength.

The core requirement — per-table rowid resolution so blobs from two different joined tables both stream correctly — is implemented and covered by the new test. The scenario from the issue repro now resolves each blob's rowid against its own table's key/rowid column. Three compliance gaps remain.

```json
[
  {
    "file": "src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs",
    "line": 393,
    "severity": "High",
    "category": "spec-compliance",
    "issue": "[SPEC_DEVIATION] The rewritten assertion `Debug.Assert(rowIdForOrdinal!=null)` changes semantics from the original trivially-true `Debug.Assert(_rowidOrdinal.HasValue)` (which held because `_rowidOrdinal` was set to -1 up front). The null result is a legitimate, spec-preserved outcome — it is exactly the condition that routes to the MemoryStream fallback on line 396-399, exercised by existing tests (GetStream_works with `SELECT x'...'` expression blobs, GetStream_works_when_composite_pk, GetBytes_works with a no-PK table, GetStream_works_with_text/int/float). The fix for #32747 was not authorized to change behavior on these paths, but in Debug builds of Microsoft.Data.Sqlite.Core every such read now trips a failed assertion (which on .NET Core fail-fasts the process by default when no debugger is attached).",
    "fix": "Delete the assertion (a null rowIdForOrdinal is an expected state handled by the fallback branch), or restore the original always-true intent by asserting only conditions that indicate a genuine bug.",
    "confidence": 75,
    "pre_existing": false
  },
  {
    "file": "src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs",
    "line": 328,
    "severity": "Medium",
    "category": "spec-compliance",
    "issue": "[SPEC_EDGE_CASE] The cache key `$\"{blobDatabaseName}_{blobTableName}\"` does not uniquely identify a (database, table) pair: with attached databases whose names contain underscores, distinct pairs collide (e.g. database \"main_A\" + table \"T\" vs. database \"main\" + table \"A_T\" both yield \"main_A_T\"). On collision the second table's blob reuses the first table's cached rowid ordinal — reintroducing the exact defect the spec requires fixed (rowid from one table applied to another table's blob), producing 'no such rowid' or silently wrong blob data. The requirement is per-(database, table) rowid tracking; the string-concatenation key only approximates it.",
    "fix": "Key the dictionary on a value tuple: `Dictionary<(string Database, string Table), RowIdInfo>` with key `(blobDatabaseName, blobTableName)` — no string encoding needed.",
    "confidence": 75,
    "pre_existing": false
  },
  {
    "file": "src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs",
    "line": 23,
    "severity": "Low",
    "category": "spec-compliance",
    "issue": "[SPEC_UNCOVERED] `RowIdInfo.TableName` is assigned in the constructor but never read anywhere in the codebase — the fix only needs the ordinal. No spec requirement accounts for carrying the table name; the RowIdInfo class (with mutable public setters) is broader than the change requires.",
    "fix": "Drop the TableName property; the dictionary value can be a plain `int` ordinal (the table identity is already the key), eliminating the RowIdInfo class entirely.",
    "confidence": 100,
    "pre_existing": false
  }
]
```

## Requirement Coverage Matrix

| Req | Description | Status | Evidence |
|-----|-------------|--------|----------|
| R1 | Joined query with blob columns from two different tables: reading both via GetBytes/GetStream must succeed with each blob's own row data (issue repro) | Covered | src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs:327-404 (per-table lookup); test/Microsoft.Data.Sqlite.Tests/SqliteDataReaderTest.cs:149-184 |
| R2 | Rowid resolution must be tracked per (database, table), not cached once per reader — "the first line caches a rowid that is not usable for the second line" | Partial | SqliteDataRecord.cs:328 — string key `{db}_{table}` collides for underscore-containing attached-database names (finding 2) |
| R3 | Existing blob-streaming behavior must be preserved for scenarios the issue does not touch (rowid alias, single INTEGER PK, composite PK / expression blobs → MemoryStream fallback) | Deviated | Release-build behavior preserved (SqliteDataRecord.cs:352-357, 384-389, 396-399, confirmed against pre-change source via `git show HEAD~1`); Debug-build behavior deviates — assert at line 393 fires on the fallback path (finding 1) |
| R4 | Repro pattern `GetBytes(ordinal, ..., null, 0, 0)` (length query) and repeated per-row reads must work for both tables' blobs | Covered | SqliteDataRecord.cs:274-286 routes through the same GetStream; cached ordinals remain valid across rows and rowid is re-fetched per call (line 402) |
| R5 | Fix must respect database identity (same table name in different attached databases must not share a rowid ordinal) | Covered (modulo R2 collision) | Key includes `blobDatabaseName` (line 328); scan filters on database name (lines 339-343) |

## Considered But Not Flagged

- **Negative-result caching removed (performance, not compliance)**: the old code cached `_rowidOrdinal = -1`, so the column scan ran once per reader; the new code never records a "no rowid found" outcome, so every GetStream/GetBytes/GetChars call on a no-rowid table re-runs the full scan, including `sqlite3_table_column_metadata` calls and the `pragma_table_info` COUNT command (SqliteDataRecord.cs:375-381) per call, per row. Same results are produced, so this is efficiency, not spec deviation — performance-reviewer scope.
- **Self-join limitation (pre-existing, outside literal spec)**: `SELECT a1.VALUE, a2.VALUE FROM A a1 JOIN A a2 ...` — `sqlite3_column_table_name` returns the real table name for both aliases, so both blobs share one cache entry and the second read uses the first alias's rowid (silently wrong row's blob). The spec's requirement is explicitly "two blob fields belong from two different tables"; a self-join is the same table, the pre-change code failed identically, and [Inference] the sqlite3 column-metadata API exposes no alias identity to distinguish the instances — so this is a reasonable interpretation boundary, not a finding.
- **Expression-column blobs (`SELECT x'...'`)**: null database/table names collapse to the shared key `"_"`, but since no rowid is ever found for expressions, no entry is added and all such reads correctly hit the MemoryStream fallback — no wrong-data path (the Debug.Assert on that path is finding 1).
- **Two blob columns from the same table**: share one cache entry with the same rowid ordinal — correct by construction.
- **Test fidelity vs. repro**: the added test drops the DESCRIPTION columns and the null-buffer length calls from the issue repro and reads a single row; the essential failure mode (second table's blob after first table's blob) is faithfully reproduced with distinguishable rowids (1 vs 1000). Remaining test-shape concerns (Console.WriteLine, multi-row loop) are test-reviewer scope.
- **Naming/formatting deviations** (`RowIds` field naming, stray blank line after the namespace, `!=null` spacing): consistency-reviewer scope.

Relevant files: /home/decaf/code/decaf-claude/competition/benchmark/repos/1/src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs, /home/decaf/code/decaf-claude/competition/benchmark/repos/1/test/Microsoft.Data.Sqlite.Tests/SqliteDataReaderTest.cs
