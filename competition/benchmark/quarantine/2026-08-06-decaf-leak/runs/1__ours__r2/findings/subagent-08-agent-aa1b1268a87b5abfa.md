# subagent agent-aa1b1268a87b5abfa

## Test Review: `test/Microsoft.Data.Sqlite.Tests/SqliteDataReaderTest.cs`

### Scope note

Reviewed only the new `GetBytes_works_streaming_join` test added in this diff, in the context of the full test file and `src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs` (`GetBytes` → `GetStream` → `GetCachedBlob`).

**Verified: `GetBytes` with a non-null buffer does exercise the streaming path.** `SqliteDataRecord.GetBytes(int, long, byte[]?, int, int)` calls `GetStream(ordinal)` unconditionally — the `buffer == null` check only short-circuits *after* `GetStream` has already run (it changes what's returned, not whether `GetStream` is called). So the new test's two `reader.GetBytes(1, …)` / `reader.GetBytes(3, …)` calls do reach the exact `RowIds` dictionary logic this PR touches.

**Verified: the test does exercise the metadata-lookup branch, not the `columnName == "rowid"` shortcut.** Because the query aliases `A.ID`/`B.ID` (not a literal `SELECT rowid`), `sqlite3_column_origin_name` returns `"ID"`, not `"rowid"`, so `GetStream` falls through to the `sqlite3_table_column_metadata` + `pragma_table_info` path for both tables. Sibling tests (`GetStream_Blob_works` with `SELECT Id, Data FROM DataTable …`) already prove that nested command execution via `_connection.CreateCommand()` while a reader is mid-iteration works, so this isn't a novel risk introduced by the new test.

**Verified: this test would fail (throw) without the fix, and passes with it.** Tracing the pre-fix code: the first `GetStream(1)` call (table `A`) sets the single shared `_rowidOrdinal = 0` (ordinal of `AID`). The second `GetStream(3)` call (table `B`) skips recomputation (`_rowidOrdinal.HasValue == true`) and reuses ordinal `0`'s value (`AID = 1`) as the rowid for table `B`, constructing `SqliteBlob(connection, "main", "B", "VALUE", rowid: 1, …)`. Table `B`'s only row has rowid `1000`, not `1`, so `sqlite3_blob_open` throws `SqliteException` ("no such rowid: 1") — matching the reported bug exactly. This is a genuine, non-tautological regression guard.

No CRITICAL, HIGH, or MEDIUM anti-patterns found. Two minor LOW-severity hygiene issues.

### Summary
| Severity | Count |
|----------|-------|
| CRITICAL | 0     |
| HIGH     | 0     |
| MEDIUM   | 0     |
| LOW      | 2     |

### LOW Issues

#### 1. Debug `Console.WriteLine` used in place of an assertion in `SqliteDataReaderTest.cs:170-171`

**Problem:** The test reads `AID` and `BID` via `reader.GetInt32(0)`/`GetInt32(2)` and only interpolates them into a `Console.WriteLine`. The comment claims this verifies "reading fields that does not involve blobs should be ok," but nothing is actually asserted — a returned wrong value (e.g. `0` instead of `1`/`1000`) would be silently printed and the test would still pass. The only real coverage this line provides is "does not throw," which is true but weaker than what the comment implies, and the printed output adds noise to test/CI logs without adding verification value.

**Confidence:** 100

**Pre-existing:** no — new in this diff

**Current Code:**
```csharp
//reading fields that does not involve blobs should be ok
Console.WriteLine($"A.ID={reader.GetInt32(0)} B.ID={reader.GetInt32(2)}");
```

**Suggested Fix:**
```csharp
// Reading fields that don't involve blobs should still work.
Assert.Equal(1, reader.GetInt32(0));
Assert.Equal(1000, reader.GetInt32(2));
```

---

#### 2. Comment narrates bug-fix history instead of describing behavior in `SqliteDataReaderTest.cs:179`

**Problem:** `//this was failing. now should be fixed` documents the *history* of the bug rather than the behavior under test. This isn't a functional issue, but it degrades as documentation once the fix is old news, and doesn't tell a future reader *why* this specific call matters (rowid ordinal must be looked up per-table, not cached globally).

**Confidence:** 100

**Pre-existing:** no — new in this diff

**Current Code:**
```csharp
reader.GetBytes(3, 1, bbuff, 0, bbuff.Length);  //this was failing. now should be fixed
```

**Suggested Fix:**
```csharp
// Table B's rowid ordinal must be resolved independently of table A's,
// even though both blobs are read from the same SqliteDataRecord.
reader.GetBytes(3, 1, bbuff, 0, bbuff.Length);
```

---

### Probe Requests

#### 1. `GetBytes_works_streaming_join` in `test/Microsoft.Data.Sqlite.Tests/SqliteDataReaderTest.cs`
**Remove:** `src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs` — the line `string rowidkey = $"{blobDatabaseName}_{blobTableName}";` — replace with `string rowidkey = blobDatabaseName;` (drops the table-name component, restoring the pre-fix behavior of one cache entry per database regardless of table, without touching the surrounding dictionary refactor).
**Expect:** `GetBytes_works_streaming_join` throws `SqliteException` ("no such rowid: 1") on the second `reader.GetBytes(3, 1, bbuff, 0, bbuff.Length)` call, since the cached rowid ordinal from table `A` (value `1`) gets reused against table `B` (whose row has rowid `1000`).
**Relates to:** confidence check on this new guard (already reasoned CONFIRMED via static trace above; this probe would raise it from static reasoning to executed evidence).

### Recommendations

1. Replace the `Console.WriteLine` in `GetBytes_works_streaming_join` with actual `Assert.Equal` calls on `AID`/`BID` — currently free to drift silently wrong.
2. Reword the historical comment to describe *why* the assertion matters rather than *when* it used to fail.
3. Optional coverage extension (not a defect, just a gap): the new test only covers a single row and a two-table join. A three-way join or a loop over multiple `Read()` calls would more directly demonstrate that the `RowIds` dictionary correctly holds independent entries per table across the lifetime of one `SqliteDataRecord`, beyond the two-call scenario already covered.
