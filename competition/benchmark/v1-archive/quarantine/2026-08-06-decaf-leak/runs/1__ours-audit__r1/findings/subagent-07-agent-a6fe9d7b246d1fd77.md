# subagent agent-a6fe9d7b246d1fd77

Code confirms the concern precisely. Findings below.

## Findings

```json
[
  {
    "file": "src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs",
    "line": 396,
    "severity": "High",
    "category": "performance",
    "issue": "[PERF_QUERY] Negative rowid-resolution outcome is no longer memoized. When the scan finds no backing rowid ordinal, nothing is inserted into RowIds (lines 355/387 only run on a hit), so line 329 TryGetValue misses on every subsequent GetStream call for that blob column. For a blob column whose table has a composite/multi-column PK (or a WITHOUT ROWID table), the scan reaches an INTEGER primaryKey!=0 column and re-runs `SELECT COUNT(*) FROM pragma_table_info($table)` (line 377) — pkColumns is a per-call local so the pkColumns<0 guard resets every call — returns >1, and still caches nothing. GetStream is on the per-row streaming path (GetBytes/GetChars/GetTextReader; GetBytes with null buffer calls it twice per row). Result: one COUNT(*) SQL query + one native metadata call per row. Across a large result set this is a per-row N+1 the OLD design avoided by memoizing the -1 outcome once per reader.",
    "fix": "Insert a sentinel/negative entry into RowIds for rowidkey when the scan completes without a hit (mirror the old _rowidOrdinal = -1 memoization), so the null outcome is cached and the scan/metadata/COUNT work runs at most once per (db,table) per reader. E.g. after the loop, `RowIds[rowidkey] = rowIdForOrdinal;` (allowing a null/sentinel value) so TryGetValue hits thereafter.",
    "confidence": 75,
    "pre_existing": false
  },
  {
    "file": "src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs",
    "line": 332,
    "severity": "Medium",
    "category": "performance",
    "issue": "[PERF_HOT_PATH] Same missing negative-memoization: for a blob column with no backing table at all (computed/literal/aggregate/expression blob, e.g. SELECT zeroblob(n)), the null outcome is never cached, so the full O(FieldCount) column scan at line 332 — each iteration allocating strings via sqlite3_column_database_name/table_name/origin_name utf8_to_string plus native interop — re-executes on every GetStream call, i.e. per row read. The COUNT query may not fire in this case, but the repeated per-row scan + allocation is still work the OLD single-memo design avoided.",
    "fix": "Same fix as above — cache the negative outcome once so the per-row scan does not repeat. A single sentinel insert covers both this and the query-re-execution case.",
    "confidence": 75,
    "pre_existing": false
  }
]
```

## Considered But Not Flagged

- **`RowIds` dictionary unbounded growth**: keyed by db+table string; the set of (database, table) pairs in a single reader's result set is bounded and tiny (typically 1). Not an unbounded-cache concern. Dismissed.
- **`$"{blobDatabaseName}_{blobTableName}"` string interpolation per call**: one small allocation per GetStream call; real but negligible next to the scan/query cost, and it is the key-lookup cost that exists even on the cache-hit path. Not a standalone finding (micro-allocation, no felt impact).
- **Positive-path per-row cost (cache hit)**: on the hit path, GetStream still calls sqlite3_column_database_name/table_name/origin_name per call, but no scan or query — this is inherent to the API and unchanged in character by the diff. Not a regression.
- **The COUNT(*) pragma query design itself**: pre-existing shape; on the fixed (memoized) path it runs at most once, which is acceptable. Not flagged — the defect is the missing memoization, not the query's existence.

Both findings share one root cause (the null branch at line 396 caches nothing); a single sentinel-insert fix resolves both. The regression is genuine: the OLD `_rowidOrdinal = -1` explicitly memoized the "no rowid" outcome so the scan+metadata+COUNT ran at most once per reader; the NEW code drops that, converting a once-per-reader cost into once-per-row on the no-rowid path.

Relevant file: `/home/decaf/code/decaf-claude/competition/benchmark/repos/1/src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs` (lines 316-405).

### Probe Requests
None — findings verified from source directly; no build or execution required.
