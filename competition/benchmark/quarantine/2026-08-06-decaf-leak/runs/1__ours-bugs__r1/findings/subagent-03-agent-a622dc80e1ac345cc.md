# subagent agent-a622dc80e1ac345cc

## Analysis

I'll trace the performance implications of the caching strategy change for blob stream retrieval.

**Hot path identification:**
- `GetStream(int ordinal)` is called on every blob column read, whether streaming large values via `GetFieldValue<Stream>()`, `GetBytes()`, `GetChars()`, or `GetTextReader()`.
- If code iterates over a result set with blob columns (e.g., reading many rows row-by-row), this path executes per row.

**The regression:**

The old code memoized three states in a single `int? _rowidOrdinal`:
1. Never checked: `null`
2. Not found (checked once, then cached cheaply): `-1`
3. Found at ordinal N: `N`

Second and subsequent calls checked `_rowidOrdinal.Value < 0` (line 1 CPU cycle).

The new code uses `Dictionary<string, RowIdInfo>` keyed by `{database}_{table}`, but **only adds entries when a rowid IS found** (lines 355, 387):
- If rowid found: `RowIds.Add(rowidkey, rowIdForOrdinal); break;`
- If rowid NOT found: **no entry is added**; `rowIdForOrdinal` remains `null`

**Per-call cost when no rowid exists:**

1. **First call:** Cache miss → O(FieldCount) loop (lines 332–391) → for each candidate column calls `sqlite3_table_column_metadata()` (line 359) → for INTEGER-PK candidates executes `SELECT COUNT(*) FROM pragma_table_info($table) WHERE pk != 0;` (line 377–380) → returns MemoryStream.

2. **Second call:** `RowIds.TryGetValue(rowidkey, ...)` cache miss (nothing was cached) → **re-runs entire O(FieldCount) scan + SQL query again** (lines 332–391).

3. **Nth call:** Same as call 2, every time.

**Multiplication:** Per blob column read × number of rows iterated = unbounded cost.

**Concrete scenario (user-visible cost):**
- Reading 10,000 rows from a table with a BLOB column and no rowid in the SELECT
- First call: 1× expensive scan + SQL query
- Calls 2–10,000: 9,999× repeated expensive scans + SQL queries
- Old code: 1× expensive scan, then 9,999 cheap checks

**Why it's introduced:** The change restructured caching from a single `int?` (which memoized -1 cheaply) to a dictionary (which does not add a key on negative results). The old behavior that memoized the "not found" signal was lost.

---

```json
[
  {
    "file": "src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs",
    "line": 329,
    "severity": "High",
    "category": "performance",
    "issue": "[PERF_HOT_PATH] When blob column's table has no rowid/INTEGER-PK in result set, negative cache result is not memoized. O(FieldCount) loop + pragma_table_info SQL query re-runs on every GetStream call instead of caching once.",
    "fix": "On negative result (no rowid found, line 391), add a sentinel entry to RowIds before exiting the cache-check block: `RowIds[rowidkey] = new RowIdInfo(-1, tableName);` Then check `if (rowIdForOrdinal?.Ordinal < 0)` after cache retrieval to handle both negative and positive cached results.",
    "confidence": 100,
    "pre_existing": false
  }
]
```

## Considered But Not Flagged

**Thread-safety race on Dictionary initialization** (lines 329–391, 39): The `Dictionary<string, RowIdInfo> RowIds` is now mutable shared state without synchronization. Concurrent `GetStream()` calls on the same blob column could race to populate it, causing redundant scans to execute in parallel. However, this is a **correctness hazard** (data-race), not a performance defect—the final cached result is eventually consistent. Out of scope for this review (belongs to concurrency/correctness reviewers).

**Debug assertion validity** (line 393): `Debug.Assert(rowIdForOrdinal != null)` can fail when no rowid is found; the variable is initialized to `null` and never assigned if the loop doesn't break. This is a correctness bug (assertion violation in Debug mode), not performance. Out of scope.
