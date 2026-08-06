# subagent agent-ad662a3204f052886

Confirmed the regression against the code. The negative result (no discoverable rowid) is never inserted into `RowIds`, so `TryGetValue` misses on every call for such tables.

## Findings

```json
[
  {
    "file": "src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs",
    "line": 329,
    "severity": "High",
    "category": "performance",
    "issue": "[PERF_CACHING] Lost negative-result caching regression. The old code cached the not-found result in `_rowidOrdinal = -1`, so the column scan ran at most once per reader. The new `RowIds` dictionary is only populated via `.Add` inside the two positive branches (L355, L387); when the loop completes without finding a rowid (`rowIdForOrdinal == null` — WITHOUT ROWID table, view, or expression/computed column), nothing is cached. Every subsequent GetStream call on that blob column re-runs the full O(FieldCount) column scan — each iteration doing native interop (sqlite3_column_database_name/table_name/origin_name + utf8 string allocations) and sqlite3_table_column_metadata — and, for any INTEGER-PK-flagged candidate, re-executes `SELECT COUNT(*) FROM pragma_table_info($table)` (L377). GetStream is the per-row blob-streaming API; streaming N rows of a blob from a rowid-less table now costs N full scans + up to N COUNT queries against the same connection, versus exactly one in the original. At a million rows this is ~1M redundant metadata scans and COUNT queries serialized on the reader's connection.",
    "fix": "Cache the negative result too: after the scan loop, always insert the key even when no rowid was found — e.g. store a nullable/sentinel per key (RowIds[rowidkey] = rowIdForOrdinal; allowing null) and switch the guard to a presence check, or keep a separate HashSet<string> of keys known to have no rowid. Restore the original invariant that the scan/COUNT runs once per (database,table) per reader.",
    "confidence": 100,
    "pre_existing": false
  }
]
```

## Considered But Not Flagged

- **`rowidkey` string interpolation allocated on every GetStream call (L328).** `$"{blobDatabaseName}_{blobTableName}"` plus the two `utf8_to_string()` calls at L324-325 allocate transient strings on every call, including cache hits — the original `int?` check allocated nothing. Real per-row GC pressure at a million rows, but negligible next to the `SqliteBlob`/`MemoryStream` allocation and native calls that dominate each GetStream. Below the persona's 75 bar (anchor ~50). Would largely disappear anyway once the primary caching fix lands, since the dominant cost is the repeated scan, not the key build.

- **`RowIds` Dictionary allocated per SqliteDataRecord even when GetStream is never called (L39).** One dictionary allocation per reader/record instance, not per row (the record is reused across rows within a reader). Cold-path, bounded, negligible — not a finding.

- **`RowIdInfo` per-key allocation (L354, L386).** Allocated only on the found path and then cached; at most one per distinct (database,table) key per reader. Bounded and negligible.

- **The COUNT query itself (L377).** Correct and appropriately memoized *within* a single scan via `pkColumns`; it is not a defect in isolation. Its cost only becomes a scale problem because of the lost caching above — captured there, not double-reported.

Note: the `{db}_{table}` key-construction ambiguity (`"a_b" + "c"` vs `"a" + "b_c"`) is a correctness concern, out of my scope — defer to quick-reviewer/dotnet-reviewer.
