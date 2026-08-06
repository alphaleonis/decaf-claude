# subagent agent-a24e53640a1f955d9

Analysis complete. Provenance is `linked` (GitHub #32747 closed by this PR via "Fixes"), so I review at full strength with no severity cap.

## Requirement Extraction

- **R1** (functional / bug-fix): Reading BLOBs from two *different* tables in a single joined query must work — after `GetBytes`/`GetStream` on table A's blob, the same call on table B's blob must not throw `SQLite Error 1: 'no such rowid'`. — Type: functional
- **R2** (root-cause constraint): The cached rowid ordinal must be scoped per-table, not global, so table A's rowid ordinal is never reused for table B. — Type: constraint
- **R3** (verification): A regression test demonstrating the joined multi-blob read succeeds. — Type: test/repro

## Findings

```json
[
  {
    "file": "src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs",
    "line": 328,
    "severity": "Medium",
    "category": "spec-compliance",
    "issue": "[SPEC_EDGE_CASE] The per-table rowid cache key is \"{db}_{table}\" built from sqlite3_column_database_name/table_name, which return the underlying table's real name, not the query alias. A self-join of one table (SELECT a.VALUE, b.VALUE FROM T a JOIN T b ...) produces two blob columns that both map to the identical key. The first GetStream caches ONE rowid ordinal under that key and the second reuses it — the same 'wrong rowid reused across the join' failure class the bug reports, now surfacing for self-joins instead of distinct tables. The spec's expected behavior ('reading BLOBs ... in one joined query should work') is not met for this joined-query shape.",
    "fix": "Distinguish aliases when the same underlying table appears more than once — e.g. include the discovered rowid ordinal / a per-blob-ordinal disambiguator in the key, or key the cache by the blob column's own ordinal rather than by db+table name. At minimum, document the self-join limitation.",
    "confidence": 75,
    "pre_existing": true
  },
  {
    "file": "src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs",
    "line": 23,
    "severity": "Low",
    "category": "spec-compliance",
    "issue": "[SPEC_UNCOVERED] RowIdInfo.TableName is written in both constructors (lines 354, 386) but never read anywhere; only RowIdInfo.Ordinal is consumed (line 402). The fix requires only the ordinal per key, so this field is dead data introduced beyond what the spec needs.",
    "fix": "Drop TableName from RowIdInfo and store just the int ordinal (or a plain Dictionary<string,int>), since the table identity is already the dictionary key.",
    "confidence": 75,
    "pre_existing": false
  }
]
```

## Requirement Coverage Matrix

| Req | Description | Status | Evidence |
|-----|-------------|--------|----------|
| R1 | Multi-table joined BLOB reads must not throw "no such rowid" | Covered | `GetStream` now resolves rowid per blob table via `RowIds` dict keyed `{db}_{table}` (SqliteDataRecord.cs:324-404); regression test reads A.VALUE then B.VALUE slices successfully |
| R2 | Rowid ordinal cached per-table, not globally | Covered | Global `int? _rowidOrdinal` replaced by `Dictionary<string,RowIdInfo> RowIds`; lookup/scan/insert keyed per table (lines 39, 327-394) |
| R3 | Regression test for the joined multi-blob scenario | Covered (with deviations) | `GetBytes_works_streaming_join` (SqliteDataReaderTest.cs) — see Considered notes on repro fidelity |

## Assessment of the four requested points

1. **Does `{db}_{table}` keying address the root cause?** Yes for the reported scenario. The root cause was a single global rowid ordinal cached from the first blob's table and reused for the second. Keying the cache by database+table name gives each distinct table its own rowid ordinal, and on a miss the code scans only columns whose db+table match the current blob (lines 339-349) before caching. This directly satisfies R1/R2 and the added test exercises it. It breaks only when db+table name is *not* unique per join participant (self-join — Finding 1).

2. **Uncovered spec scenario (DESCRIPTION columns / null-buffer length call).** Low concern for compliance. The issue repro calls `GetBytes(ordinal, 0, null, 0, 0)` (null buffer → length) and selects TEXT DESCRIPTION columns; the test uses a non-null 2-byte buffer and omits DESCRIPTION. Both `GetBytes` forms route through the same `GetStream(ordinal)` → `SqliteBlob` construction that carried the bug (GetBytes at line 274-286), so the fixed path is genuinely exercised; DESCRIPTION columns are inert to the rowid scan (B.ID is still the discovered pk). Exact-repro fidelity of the test is test-reviewer scope, not a compliance gap — hence not flagged.

3. **Attached-db vs self-join edge cases.** The db-name component correctly disambiguates same-named tables in different attached databases (good — supported). The self-join-under-two-aliases case is *not* handled and is Finding 1.

4. **Scope creep.** The unused `RowIdInfo.TableName` field is minor creep (Finding 2). The added blank line after `namespace {` (line 17) is cosmetic noise. Field naming (`readonly Dictionary<...> RowIds` — non-private, non-`_`-prefixed, unlike every sibling field) is a convention deviation but belongs to consistency-reviewer, not compliance.

## Considered But Not Flagged

- **`Debug.Assert(rowIdForOrdinal != null)` at line 393 can now fire falsely.** The original set `_rowidOrdinal = -1` up front so its assert (`HasValue`) never tripped; the new code leaves `rowIdForOrdinal` null when no rowid column is discoverable (WITHOUT ROWID tables, views, expression/aggregate blob columns). In Debug builds a blob read from such a source now hits the assert, where release builds correctly fall through to `GetCachedBlob` (line 396-399). This is an introduced correctness regression but it is a line-level logic bug → **quick-reviewer scope**. Worth a probe.
- **Negative results no longer cached.** When no rowid is found, the old code cached `-1`; the new code adds nothing to `RowIds`, so every subsequent `GetStream` on a rowid-less blob column re-scans all columns (and re-runs the `pragma_table_info` count). Behavior stays correct; this is a repeated-work cost → **performance-reviewer scope**.
- **Test repro fidelity (null-buffer length call, DESCRIPTION columns)** — **test-reviewer scope**, mechanism-equivalent as noted above.

### Probe Requests
- Confirm the Debug-build assertion behavior: run `GetBytes_works_streaming` / any blob read against a `WITHOUT ROWID` table or a view under a Debug build to see whether `Debug.Assert(rowIdForOrdinal != null)` (line 393) now trips where the pre-change code returned a cached blob.
- Optional: a self-join test (`SELECT a.VALUE, b.VALUE FROM A a JOIN A b ON ...` with distinct rows) to confirm/deny the Finding 1 wrong-rowid behavior.

Relevant files: `/home/decaf/code/decaf-claude/competition/benchmark/repos/1/src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs` (lines 20-39, 316-405) and `/home/decaf/code/decaf-claude/competition/benchmark/repos/1/test/Microsoft.Data.Sqlite.Tests/SqliteDataReaderTest.cs` (`GetBytes_works_streaming_join`).
