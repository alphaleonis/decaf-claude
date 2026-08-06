# subagent agent-ae92d92f926edd0a6

I have the production fix, both tests, and the bug mechanics. Let me confirm my understanding of whether the ordering reproduces the bug before writing up.

The old code cached a single `_rowidOrdinal` for the whole record. Reading `AVALUE` (ordinal 1) first scans and sets `_rowidOrdinal = 0` (A.ID, the single-column integer PK / rowid alias), then opens A's blob at rowid `GetInt64(0)=1` → correct. Reading `BVALUE` (ordinal 3) next skips the scan because `_rowidOrdinal.HasValue` is now true, reuses ordinal 0, computes `rowid = GetInt64(0) = 1`, and opens a `SqliteBlob` on table **B** with rowid **1** — but B's only row has rowid 1000, so the blob open/read errors. So reading A's blob first then B's is exactly what triggers the bug, and the test would throw before the fix. The ordering is correct and the test is a genuine regression guard.

## Test Review: `SqliteDataReaderTest.cs` — PR #32770 (`GetBytes_works_streaming_join`)

### Summary
| Severity | Count |
|----------|-------|
| CRITICAL | 0     |
| HIGH     | 0     |
| MEDIUM   | 2     |
| LOW      | 1     |

Assessment of the two questions raised:

- **Does it reproduce the bug / would it have failed before the fix?** Yes. Reading `AVALUE` (ordinal 1) first populates the old single-slot `_rowidOrdinal` cache with ordinal 0 (A's rowid), then reading `BVALUE` (ordinal 3) reuses that cached ordinal and opens a blob on table B with A's rowid (1 instead of 1000), which errors. The ordering deliberately caches table A's rowid before touching table B, which is precisely the failing sequence from #32747. This is a valid guard, not a false positive. (See Probe Request to confirm mechanically.)
- **Is `Console.WriteLine` for A.ID/B.ID appropriate?** No — see finding 1.

---

### MEDIUM Issues

#### 1. Coverage gap: negative-cache path (view / WITHOUT ROWID / expression blob) untested in `SqliteDataReaderTest.cs:149`

**Problem:** The fix changed the "no rowid column found" branch from a cached `_rowidOrdinal.Value < 0` sentinel to `rowIdForOrdinal == null`, and — unlike the positive case — the null result is **not** inserted into the `RowIds` dictionary, so that path is re-scanned on every `GetStream`. No test exercises a blob column that has no backing rowid (a `VIEW`, a `WITHOUT ROWID` table, or an expression like `SELECT x'...'`), which is the branch that returns `new MemoryStream(GetCachedBlob(ordinal), false)`. A regression that broke the fallback-to-materialized-blob path would pass every existing streaming test. Note the sibling `GetBytes_NullBuffer` at line 187 uses `SELECT x'427E5743'` (an expression column) but does not stream via a rowid-bearing join, so the mixed case is uncovered.

**Confidence:** 75
**Pre-existing:** no (the change reworks this branch; wide reach makes the touched-surface gap in scope)

**Suggested Fix:** Add a test joining a rowid table's blob with a `VIEW`'s (or `WITHOUT ROWID` table's) blob column, reading the rowid-less blob after the rowid-bearing one, asserting the materialized bytes are still correct.

---

#### 2. Coverage gap: cache-hit path and same-table second blob untested in `SqliteDataReaderTest.cs:149`

**Problem:** The new keyed cache (`{blobDatabaseName}_{blobTableName}`) has two branches the single test does not distinguish: (a) a **second blob column from the same table**, which must hit the cached `RowIdInfo` and reuse the correct ordinal, and (b) **multiple rows** (`while (reader.Read())`) where the per-table ordinal is stable but the rowid value changes each row. The current test reads exactly one blob per table on a single row, so a cache that returned a stale/wrong ordinal on the second same-table lookup, or that mis-handled row advancement, would not be caught. The underscore-joined cache key is also collision-prone (db `a`/table `b_c` vs db `a_b`/table `c`) with no guarding test, though that is a lower-likelihood edge.

**Confidence:** 50
**Pre-existing:** no (new caching structure introduced by this change)

**Suggested Fix:** Add (a) a table with two blob columns, reading both and asserting each; and (b) a multi-row join iterated with `while (reader.Read())`, asserting each row's blobs stream correctly.

---

### LOW Issues

#### 1. Non-blob columns read but never asserted (dead `Console.WriteLine`) in `SqliteDataReaderTest.cs:171`

**Problem:** The comment `//reading fields that does not involve blobs should be ok` signals intent to verify the non-blob reads, but the values are only sent to `Console.WriteLine` — never asserted. If `GetInt32(0)`/`GetInt32(2)` returned wrong values the test would still pass. `Console.WriteLine` is also the wrong output mechanism for xUnit (the idiom is `ITestOutputHelper`); as written it is committed diagnostic noise, not a check. Asserting the IDs additionally strengthens the regression guard: `B.ID` must be `1000` (proving B's true rowid, distinct from A's `1`, is what makes the bug observable).

**Confidence:** 100
**Pre-existing:** no

**Current Code:**
```csharp
Console.WriteLine($"A.ID={reader.GetInt32(0)} B.ID={reader.GetInt32(2)}");
```

**Suggested Fix:**
```csharp
Assert.Equal(1, reader.GetInt32(0));      // A.ID
Assert.Equal(1000, reader.GetInt32(2));   // B.ID (distinct rowid — the crux of the bug)
```

---

### Probe Requests

Never run these here (read-only tree; dotnet not installed). For the orchestrator to run when it is the sole actor:

#### 1. `GetBytes_works_streaming_join` in `test/Microsoft.Data.Sqlite.Tests/SqliteDataReaderTest.cs`
**Change:** In `src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs` (`GetStream`), neutralize the per-table key so the cache collapses back to a single global slot — e.g. replace `string rowidkey = $"{blobDatabaseName}_{blobTableName}";` with a constant `string rowidkey = "";`. This reproduces the pre-fix single-`_rowidOrdinal` behavior without touching test code.
**Expect:** The second `GetBytes(3, ...)` on `BVALUE` reuses table A's rowid ordinal, computes rowid `1` for table B (whose row is rowid `1000`), and the `SqliteBlob` open/read throws a `SqliteException` — the test fails. A test that still passes would indicate it does not actually guard the fix.
**Relates to:** confidence check that the new guard is genuine (the central question in the task).

### Recommendations

1. Keep the test — it is a valid regression guard for #32747 with the correct read ordering. Add the two ID assertions (Low 1) to remove the dead `Console.WriteLine` and harden it.
2. Close the two coverage gaps (Medium 1 & 2): a rowid-less blob column (view / WITHOUT ROWID) to cover the null-cache fallback, and a same-table-two-blobs + multi-row case to cover the cache-hit and row-advance branches.
