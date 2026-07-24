# subagent agent-ae8fc424011b38a03

## Test Review: `test/Microsoft.Data.Sqlite.Tests/SqliteDataReaderTest.cs`

### Summary
| Severity | Count |
|----------|-------|
| CRITICAL | 0     |
| HIGH     | 0     |
| MEDIUM   | 2     |
| LOW      | 1     |

The new test `GetBytes_works_streaming_join` (lines 148-184) is a well-targeted regression test for the reported bug: it joins two tables, each with its own BLOB column, and reads both blobs from a single row — exactly the scenario that broke under the old single-field `_rowidOrdinal` cache. The core assertions (`Assert.Equal([0x02, 0x03], abuff)` / `Assert.Equal([0x06, 0x07], bbuff)`) correctly compare against the real inserted data, and the test also happens to exercise the PK-metadata-lookup branch of `GetStream` (both tables use `INTEGER PRIMARY KEY` rather than a literal `rowid` column), which the pre-existing sibling test `GetBytes_works_streaming` does not cover. No CRITICAL/HIGH anti-patterns (silent failures, false positives, missing/incorrect await, tautologies) were found. Two MEDIUM gaps and one LOW documentation nit remain.

### MEDIUM Issues

#### 1. Non-blob column reads verified only via `Console.WriteLine`, no assertion in `SqliteDataReaderTest.cs:171`

**Problem:** The comment states "reading fields that does not involve blobs should be ok," but the actual values returned by `GetInt32(0)` and `GetInt32(2)` are never checked with an `Assert`. They are only piped to `Console.WriteLine`. The test would still pass even if `GetInt32` returned the wrong value for either column (e.g., if joined-column ordinal resolution were subtly broken), as long as no exception was thrown. The only real verification here is "did not throw" — a much weaker guarantee than what the comment implies.

**Confidence:** 100

**Pre-existing:** no — this is new code added by this changeset (this is the only `Console.WriteLine` call in the entire file).

**Current Code:**
```csharp
//reading fields that does not involve blobs should be ok
Console.WriteLine($"A.ID={reader.GetInt32(0)} B.ID={reader.GetInt32(2)}");
```

**Suggested Fix:**
```csharp
// Reading non-blob fields from a joined result set should return correct values.
Assert.Equal(1, reader.GetInt32(0));
Assert.Equal(1000, reader.GetInt32(2));
```

---

#### 2. Missing edge case: same table joined to itself (aliasing collision in the new cache key)

**Problem:** The production fix keys its `RowIds` cache by `$"{blobDatabaseName}_{blobTableName}"`, where `blobTableName` comes from `sqlite3_column_table_name`, which returns the underlying real table name — not the query alias. In a self-join (`SELECT A.ID, A.VALUE, B.ID, B.VALUE FROM T A JOIN T B ON ...` where both sides reference the same physical table `T`), both blob columns would produce the identical cache key `main_T`, even though they logically refer to two distinct instances of the table in the result set with potentially different rowid ordinals. The new test only covers two *distinct* tables (`A` and `B`), so it cannot detect whether the fix correctly generalizes to same-table self-joins — a scenario that plausibly still reproduces a variant of the original "no such rowid" bug (silently reusing the wrong table-instance's rowid ordinal, or returning bytes from the wrong physical row/table instance).

**Confidence:** 75 — the collision is verifiable directly from the cache-key logic in `SqliteDataRecord.cs:328` (`sqlite3_column_database_name`/`sqlite3_column_table_name` return the real table identity, not the alias), but whether it manifests as a wrong-value bug vs. a coincidentally-correct-because-same-schema result depends on exact column layout, which I have not executed.

**Pre-existing:** no — this is a coverage gap in the newly added test relative to the newly added caching mechanism it is meant to validate.

**Suggested Fix:** Add a companion test, e.g.:
```csharp
[Fact]
public void GetBytes_works_streaming_self_join()
{
    using (var connection = new SqliteConnection("Data Source=:memory:"))
    {
        connection.Open();

        connection.ExecuteNonQuery(
            "CREATE TABLE T (ID INTEGER PRIMARY KEY, PARENT_ID INTEGER, VALUE BLOB); " +
            "INSERT INTO T (ID, PARENT_ID, VALUE) VALUES (1, NULL, x'01020304'); " +
            "INSERT INTO T (ID, PARENT_ID, VALUE) VALUES (2, 1, x'05060708');");

        using (var reader = connection.ExecuteReader(
            "SELECT Child.VALUE, Parent.VALUE FROM T Child JOIN T Parent ON Child.PARENT_ID = Parent.ID"))
        {
            Assert.True(reader.Read());

            var childBuf = new byte[2];
            reader.GetBytes(0, 1, childBuf, 0, childBuf.Length);
            Assert.Equal(new byte[] { 0x06, 0x07 }, childBuf);

            var parentBuf = new byte[2];
            reader.GetBytes(1, 1, parentBuf, 0, parentBuf.Length);
            Assert.Equal(new byte[] { 0x02, 0x03 }, parentBuf);
        }
    }
}
```

---

### LOW Issues

#### 1. Comment narrates change history instead of describing behavior in `SqliteDataReaderTest.cs:179`

**Problem:** `//this was failing. now should be fixed` documents the historical bug-fix state rather than the intended behavior being verified, and will read as stale/confusing once the fix has been in place for a while. Similarly, `//get len of abuff` at line 173 doesn't describe what the following two lines actually do (declare a 2-byte buffer and read blob bytes into it — not "get length").

**Confidence:** 100

**Pre-existing:** no

**Current Code:**
```csharp
//get len of abuff
var abuff = new byte[2];
reader.GetBytes(1, 1, abuff, 0, abuff.Length);
Assert.Equal([0x02, 0x03], abuff);

var bbuff = new byte[2];
reader.GetBytes(3, 1, bbuff, 0, bbuff.Length);  //this was failing. now should be fixed
Assert.Equal([0x06, 0x07], bbuff);
```

**Suggested Fix:**
```csharp
// Read a BLOB column from table A.
var abuff = new byte[2];
reader.GetBytes(1, 1, abuff, 0, abuff.Length);
Assert.Equal([0x02, 0x03], abuff);

// Read a BLOB column from table B in the same joined row — regression test for #32747
// (previously reused table A's cached rowid ordinal and threw "no such rowid").
var bbuff = new byte[2];
reader.GetBytes(3, 1, bbuff, 0, bbuff.Length);
Assert.Equal([0x06, 0x07], bbuff);
```

---

### Probe Requests

#### 1. `GetBytes_works_streaming_join` in `test/Microsoft.Data.Sqlite.Tests/SqliteDataReaderTest.cs`
**Remove:** Revert `src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs` to the pre-fix behavior — i.e., replace the `RowIds` dictionary lookup/caching (lines 327-329, 354-355, 386-387) with the old single `_rowidOrdinal` field semantics (compute the rowid ordinal once and reuse it unconditionally for every later `GetStream` call, regardless of `blobDatabaseName`/`blobTableName`).
**Expect:** The second `reader.GetBytes(3, 1, bbuff, 0, bbuff.Length)` call (table B's blob) would incorrectly reuse table A's cached rowid ordinal, either throwing a `SqliteException: no such rowid` (if the reused ordinal/rowid doesn't exist in table B) or returning table A's byte content instead of `{0x06, 0x07}` — causing the test to fail via exception or via `Assert.Equal([0x06, 0x07], bbuff)`.
**Relates to:** confidence check on the new guard test's validity (not a listed finding above — the test itself appears sound).

### Recommendations

1. Replace the unverified `Console.WriteLine` diagnostic (finding #1) with real `Assert.Equal` checks on the joined non-blob columns — this is a one-line fix that closes a real blind spot in an otherwise solid regression test.
2. Add a self-join test case (finding #2) to confirm the new `(database, table)`-keyed cache doesn't collide when the same physical table appears twice in one result set under different aliases — this is the one scenario the fix's design leaves most exposed.
3. Tidy up the two stale/mismatched comments (finding #3) so the test documents intended behavior rather than referencing the historical failure it fixed.
