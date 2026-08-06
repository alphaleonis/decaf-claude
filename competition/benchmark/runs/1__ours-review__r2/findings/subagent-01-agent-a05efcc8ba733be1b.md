# subagent agent-a05efcc8ba733be1b

## Test Review: `GetBytes_works_streaming_join` (test/Microsoft.Data.Sqlite.Tests/SqliteDataReaderTest.cs)

### Summary
| Severity | Count |
|----------|-------|
| CRITICAL | 0     |
| HIGH     | 0     |
| MEDIUM   | 1     |
| LOW      | 2     |

### Does it actually catch the regression? — Yes, verified by trace

I traced the pre-fix production code (`git show 9e69b85 -- src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs`) against the test's call order:

- Columns: `AID=0, AVALUE=1, BID=2, BVALUE=3`. `GetBytes` routes through `SqliteDataRecord.GetStream(ordinal)`.
- Pre-fix, `_rowidOrdinal` was a single nullable field shared across all tables. `reader.GetBytes(1, …)` (table A's `VALUE`) computes and caches `_rowidOrdinal = 0` (A's `ID`), correctly returns `{0x02,0x03}` — first assert passes even on the buggy build.
- `reader.GetBytes(3, …)` (table B's `VALUE`) then sees `_rowidOrdinal.HasValue == true` and reuses ordinal `0` (A's `ID` = 1) as the rowid for table B's blob lookup instead of computing B's actual rowid ordinal (2, value 1000). Because table B has no row with rowid `1`, `SqliteBlob` construction throws "no such rowid" — reproducing issue #32747 exactly, and failing the test pre-fix.
- Post-fix, the per-table `RowIds` dictionary (keyed by `db_table`) caches A's and B's rowid ordinals independently, so the second call correctly resolves ordinal 2 and reads the right blob — both asserts pass.
- The choice of distinct primary-key values (`A.ID=1`, `B.ID=1000`) is load-bearing: if they coincided, the buggy code could accidentally read the right byte values by chance instead of throwing, weakening the guard. As written, they don't coincide, so the test reliably fails pre-fix and passes post-fix.
- The A-then-B read order is also load-bearing — B-then-A would not trigger the cross-table ordinal leak with the same asserted values, but the test correctly matches the original issue repro order.

This is a legitimate, non-trivially-constructed regression guard — no false-positive/false-negative risk found in the core mechanism.

### MEDIUM Issues

#### 1. No coverage for the fallback branch also touched by the fix in `SqliteDataReaderTest.cs:149`

**Problem:** The production fix (`src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs`) replaces a single nullable `_rowidOrdinal` cache with a per-table `Dictionary<string, RowIdInfo>`, and in doing so silently drops the old negative-result caching: previously, if no rowid alias was found, `_rowidOrdinal = -1` was cached and reused via `if (_rowidOrdinal.Value < 0) return new MemoryStream(...)`. In the new code, a miss is never added to `RowIds`, so that lookup loop re-runs on every call for a table without a rowid alias. The added test only exercises the "rowid found, two different tables" path; it never joins a rowid-bearing table with a `WITHOUT ROWID` table (or a view) to exercise the `MemoryStream` fallback branch that the same diff also restructured.

**Confidence:** 50

**Pre-existing:** no — this coverage gap is a direct consequence of the caching restructuring introduced by this diff.

**Suggested addition:** A follow-up test joining a rowid-bearing table with a `WITHOUT ROWID` (or computed/view) table, reading blobs from both, to confirm the `MemoryStream` fallback path behaves correctly under the new per-table cache and isn't affected by cross-table leakage in the other direction.

---

### LOW Issues

#### 1. Non-blob column reads are printed, never asserted, in `SqliteDataReaderTest.cs:154-160`

**Problem:** The comment `//reading fields that does not involve blobs should be ok` implies verification, but the only check is `Console.WriteLine($"A.ID={reader.GetInt32(0)} B.ID={reader.GetInt32(2)}")` — no `Assert` backs the claim that these values are `1` and `1000`.

**Confidence:** 75

**Pre-existing:** no

**Current Code:**
```csharp
//reading fields that does not involve blobs should be ok
Console.WriteLine($"A.ID={reader.GetInt32(0)} B.ID={reader.GetInt32(2)}");
```

**Suggested Fix:**
```csharp
Assert.Equal(1, reader.GetInt32(0));
Assert.Equal(1000, reader.GetInt32(2));
```

---

#### 2. Debug `Console.WriteLine` left in committed test in `SqliteDataReaderTest.cs:154`

**Problem:** Leftover diagnostic output from development; adds noise to test run output and isn't a substitute for an assertion (see finding above).

**Confidence:** 100

**Pre-existing:** no

**Suggested Fix:** Remove the `Console.WriteLine` call, replacing it with the assertions above (or delete it entirely if the non-blob-read check is considered out of scope for this regression test).

---

### Recommendations

1. Add explicit assertions on `reader.GetInt32(0)`/`reader.GetInt32(2)` and drop the `Console.WriteLine`.
2. Consider a follow-up test (separate PR/commit is fine) covering the `MemoryStream` fallback branch under the new per-table cache, since that branch's caching behavior changed in this same diff but isn't exercised here.
3. No changes needed to the core regression-guard logic — the A-before-B read order and the distinct `A.ID=1` / `B.ID=1000` values are correct and necessary for the test to reliably fail pre-fix / pass post-fix.

### Probe Requests

#### 1. `GetBytes_works_streaming_join` in `test/Microsoft.Data.Sqlite.Tests/SqliteDataReaderTest.cs`
**Remove:** In `src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs`, revert the `GetStream` method's rowid-ordinal caching from the per-table `Dictionary<string, RowIdInfo> RowIds` back to the single nullable `_rowidOrdinal` field (i.e., checkout the pre-fix version of just that method region, lines ~324-405 per the `git show 9e69b85` diff above) — do this via an isolated worktree/copy, not on the shared tree.
**Expect:** The test should fail with a `SqliteException` ("no such rowid") on the second `reader.GetBytes(3, 1, bbuff, 0, bbuff.Length)` call, confirming the static trace above.
**Relates to:** confidence check on the primary regression guard (independent of the findings above, which concern secondary coverage/assertion quality, not the core guard).
