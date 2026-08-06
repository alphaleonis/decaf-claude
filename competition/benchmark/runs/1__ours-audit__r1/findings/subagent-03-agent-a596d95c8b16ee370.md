# subagent agent-a596d95c8b16ee370

I now have a full picture of the bug, the fix, and the test. Let me verify my understanding of the poisoning order and the self-join concern by checking what `sqlite3_column_table_name` returns for aliases (conceptually) — but I can reason about this statically from the fix's keying logic. I have enough to report.

## Test Review: `GetBytes_works_streaming_join` (SqliteDataReaderTest.cs)

### Summary
| Severity | Count |
|----------|-------|
| CRITICAL | 0     |
| HIGH     | 0     |
| MEDIUM   | 3 (absent coverage) |
| LOW      | 2     |

**Verdict on the regression guard:** The test is a *genuine* guard for the exact reported bug. The bug is that `_rowidOrdinal` was cached once globally; reading `A.VALUE` (ordinal 1) first poisons the cache with A's rowid ordinal (0, value `A.ID=1`), then reading `B.VALUE` (ordinal 3) reuses ordinal 0 and builds a `SqliteBlob` for table `B` with `rowid=1`. Table B's only row has `ID=1000`, so `sqlite3_blob_open` fails and the second `GetBytes` throws — the test fails before the fix. The read order (A-blob then B-blob) is exactly the poisoning order the bug requires, and the distinct primary-key values (`1` vs `1000`) make a false pass impossible (there is no `rowid=1` in B for the wrong path to silently succeed against). Data offsets and expected bytes are correct and deterministic (single joined row, in-memory db). This is a well-constructed guard.

Findings below are quality nits and coverage gaps, not defects that neutralize the guard. All are in newly-added test code.

---

### MEDIUM Issues (absent coverage — reach: wide)

#### 1. Self-join / same-table alias not covered; the fix likely does not handle it

**Problem:** The production fix keys its rowid cache by `$"{blobDatabaseName}_{blobTableName}"` (SqliteDataRecord.cs:328). `sqlite3_column_table_name` returns the *underlying* table name, not the query alias. In a self-join (`A x JOIN A y ...` selecting `x.VALUE` and `y.VALUE`), both blob columns resolve to the same key `"main_A"`, so the second blob reuses the first alias's rowid ordinal — the same class of poisoning the PR set out to fix. No test exercises this, so the fix's boundary is unverified and a plausible残 residual bug is unguarded. [Inference — I cannot run the code to confirm the failure.]

**Confidence:** 75
**Pre-existing:** no

**Suggested coverage:** a self-join of one table with two aliases, each carrying a distinct blob and distinct primary key, reading both blobs in sequence.

---

#### 2. Negative-caching regression (blob column with no rowid table) not covered

**Problem:** The other half of the original global-cache bug was the `-1` sentinel: a blob column that has no backing rowid table (e.g., a computed expression such as `SELECT x'0102' AS V, A.VALUE FROM A`) cached `_rowidOrdinal = -1` globally and forced *every* subsequent real-table blob down the `GetCachedBlob` path. The new code stores a per-key `RowIdInfo` and returns the cached-blob path only when `rowIdForOrdinal == null` (SqliteDataRecord.cs:396), but nothing tests the mixed expression-blob + table-blob case. This is a distinct failure mode from the one the added test covers.

**Confidence:** 75
**Pre-existing:** no

**Suggested coverage:** select a literal blob expression and a real table blob in the same result set, in both orders, asserting both read correctly.

---

#### 3. Reverse read order and 3+ table joins not covered

**Problem:** The test only reads blobs in ordinal-ascending order (A then B). The symmetric case — reading `B.VALUE` before `A.VALUE` — exercises the cache-population path in the opposite direction and is a cheap addition that guards against an asymmetric fix. Likewise a three-table join would catch cache-key collisions the two-table case cannot. Single-scenario coverage of a caching bug leaves adjacent cache states unverified.

**Confidence:** 50
**Pre-existing:** no

---

### LOW Issues

#### 4. `Console.WriteLine` is a leftover debug artifact `SqliteDataReaderTest.cs:171`

**Problem:** Debug print left in a committed test. It produces no assertion and pollutes test output.

**Confidence:** 100
**Pre-existing:** no

**Current Code:**
```csharp
//reading fields that does not involve blobs should be ok
Console.WriteLine($"A.ID={reader.GetInt32(0)} B.ID={reader.GetInt32(2)}");
```

**Suggested Fix:** Replace with real assertions (see #5) or delete.

---

#### 5. Non-blob columns are read but never asserted `SqliteDataReaderTest.cs:171`

**Problem:** The comment claims "reading fields that does not involve blobs should be ok," but `GetInt32(0)` / `GetInt32(2)` are consumed only by the `WriteLine` — nothing verifies they return `1` and `1000`. The stated intent is unverified; if projection ordering regressed, this test would not notice.

**Confidence:** 100
**Pre-existing:** no

**Suggested Fix:**
```csharp
Assert.Equal(1, reader.GetInt32(0));    // AID
Assert.Equal(1000, reader.GetInt32(2)); // BID
```

---

### Probe Requests

#### 1. `GetBytes_works_streaming_join` in `SqliteDataReaderTest.cs`
**Neutralize:** `src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs:328` — make the cache key constant, e.g. change `string rowidkey = $"{blobDatabaseName}_{blobTableName}";` to a fixed literal like `"k"`. This restores the original single-global-cache behavior without touching multiple lines or the `RowIdInfo` type.
**Expect:** the second `reader.GetBytes(3, ...)` throws (SqliteException from `sqlite3_blob_open` on non-existent `rowid=1` in table B), failing the test. Confirms the test genuinely guards the per-table rowid caching.
**Relates to:** confidence check on the new guard.

*(Do not run — nominated for the orchestrator to execute when it is the sole actor on the tree. No dotnet SDK is available here regardless.)*

---

### Recommendations
1. Keep the test — it is a valid, deterministic regression guard for the reported bug.
2. Delete the `Console.WriteLine` and convert the non-blob reads into assertions (#4, #5) — trivial, purely additive.
3. Add the self-join case (#1): it is the highest-value gap because it probes a boundary the fix's table-name keying probably does not cover, and would either confirm the fix or surface a residual bug.
4. Add the mixed expression-blob + table-blob case (#2) to cover the negative-caching half of the original defect.
