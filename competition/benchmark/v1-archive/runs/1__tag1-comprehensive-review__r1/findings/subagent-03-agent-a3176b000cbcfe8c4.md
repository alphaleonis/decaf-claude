# subagent agent-a3176b000cbcfe8c4

## Test Coverage Analysis — PR #32770 (Microsoft.Data.Sqlite.Core, multi-blob-column join fix)

### Summary

The new test (`GetBytes_works_streaming_join`, `SqliteDataReaderTest.cs:148-183`) validates the headline bug (#32747): a query joining two distinct tables, each with a single-column INTEGER PK and a blob column, now resolves the correct rowid per table instead of the old single `_rowidOrdinal` field being clobbered by the second table's lookup. That specific regression is well covered. However, the refactor introduced a new per-`(database,table)` dictionary cache with several behavior changes the diff's test does not exercise, including one outright logic contradiction that the *existing* test suite would already expose if run under a Debug build — but does not, because CI builds Release.

### Critical Gaps

**Gap 1 — importance 95 — `src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs:393` contradicts `:396`**
```csharp
393:                Debug.Assert(rowIdForOrdinal!=null);
394:            }
395:
396:            if (rowIdForOrdinal == null)
397:            {
398:                return new MemoryStream(GetCachedBlob(ordinal), false);
399:            }
```
[Verified from source] In the old code, `_rowidOrdinal` was pre-seeded to the sentinel `-1` before the scan, so `Debug.Assert(_rowidOrdinal.HasValue)` was tautologically true regardless of whether a rowid/PK column was found — a no-op assertion. In the new code `rowIdForOrdinal` starts as `null` and is *only* ever assigned inside the scan loop when a rowid or single-column INTEGER PK is found (`:354`, `:386`). If the loop completes without finding one (composite PK, WITHOUT ROWID table, or a blob-producing expression with no origin table), `rowIdForOrdinal` is still `null` at `:393` — the assert now genuinely fails, one line before the code that explicitly handles that same case as a legitimate fallback (`:396-399`).

This is not a hypothetical: `GetStream_works_when_composite_pk` (`test/Microsoft.Data.Sqlite.Tests/SqliteDataReaderTest.cs:516-541`), an *existing, unmodified* test, already exercises exactly this path (composite PK ⇒ `pkColumns==2` ⇒ loop exits with `rowIdForOrdinal==null`). Under a Debug build this test would now trip the false assertion. [Verified] CI does not catch this: `azure-pipelines.yml:24` sets `_BuildConfig: Release`, and `Debug.Assert` is `[Conditional("DEBUG")]`, so the call is compiled out entirely in the pipeline's Release build — this defect is invisible to CI and would only surface for a contributor running `dotnet test` locally without specifying configuration (which defaults to Debug).
- Suggested fix: remove the assert or correct it to match the fallback (e.g. drop it — the very next `if` already handles the `null` case correctly).
- Suggested test: none is even needed if the assert is fixed/removed — the existing `GetStream_works_when_composite_pk` already proves correctness once the assert stops contradicting the fallback. Until fixed, flag this as a release-blocking defect, not a "missing test."

**Gap 2 — importance 85 — self-join / repeated-alias reference to the same table**
`src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs:328` (`rowidkey = $"{blobDatabaseName}_{blobTableName}"`) uses `sqlite3_column_database_name`/`sqlite3_column_table_name`, which return the **origin table name, not the query alias**. In a self-join (`SELECT T1.Data, T2.Data FROM Foo T1 JOIN Foo T2 ON ...`), both blob columns produce the identical cache key `"main_Foo"`. The first `GetStream` call caches `RowIdInfo(ordinal=<T1's rowid column>, "Foo")`; the second call, for `T2.Data`, reuses that same cached entry and reads `T1`'s rowid ordinal instead of resolving `T2`'s own rowid column — silently returning **the wrong row's blob data** for one side of the join. This is the exact multi-table scenario this PR claims to fix, in its most natural degenerate form, and it is untested.
- Note: `RowIdInfo.TableName` (`SqliteDataRecord.cs:15`) is set (`:354`, `:386`) but never read anywhere in the class (`grep` for `.TableName` returns nothing) — it looks like a per-occurrence disambiguation field was intended but never wired into the lookup, which is exactly what would be needed to make self-joins safe.
- Suggested test (matches `GetBytes_works_streaming_join` style, `SqliteDataReaderTest.cs:148`):
```csharp
[Fact]
public void GetBytes_works_streaming_self_join()
{
    using (var connection = new SqliteConnection("Data Source=:memory:"))
    {
        connection.Open();

        connection.ExecuteNonQuery(
            "CREATE TABLE Node (ID INTEGER PRIMARY KEY, ParentId INTEGER, Value BLOB);" +
            "INSERT INTO Node (ID, ParentId, Value) VALUES (1, NULL, x'01020304');" +
            "INSERT INTO Node (ID, ParentId, Value) VALUES (2, 1, x'05060708');");

        using (var reader = connection.ExecuteReader(
            "SELECT Parent.Value AS PValue, Child.Value AS CValue " +
            "FROM Node Parent JOIN Node Child ON Child.ParentId = Parent.ID"))
        {
            Assert.True(reader.Read());

            var pbuff = new byte[4];
            reader.GetBytes(0, 0, pbuff, 0, pbuff.Length);
            Assert.Equal([0x01, 0x02, 0x03, 0x04], pbuff);

            var cbuff = new byte[4];
            reader.GetBytes(1, 0, cbuff, 0, cbuff.Length);
            Assert.Equal([0x05, 0x06, 0x07, 0x08], cbuff);
        }
    }
}
```

### Important Improvements

**Gap 3 — importance 55 — cache-key collision via string concatenation**
`SqliteDataRecord.cs:328`: `$"{blobDatabaseName}_{blobTableName}"` is not a collision-free encoding when either component can itself contain `_`. An attached database named e.g. `"main_Foo"` with table `"Bar"` collides with database `"main"` + table `"Foo_Bar"` (both produce `"main_Foo_Bar"`), causing the same cross-table rowid mix-up as Gap 2 but via `ATTACH DATABASE` naming rather than aliasing. Narrower trigger conditions than Gap 2, but a real correctness bug in the cache-key design.
- Suggested fix: key the dictionary on `(string blobDatabaseName, string blobTableName)` (a value tuple) instead of a concatenated string.
- Suggested test: `ATTACH DATABASE ':memory:' AS "main_Foo"; CREATE TABLE "main_Foo"."Bar" (...)` alongside a main-db table literally named `"Foo_Bar"`, asserting both blob columns resolve independently.

**Gap 4 — importance 40 — loss of negative-result caching (perf regression, not correctness)**
Old code cached the "no rowid found" outcome via the `-1` sentinel so a table with no usable rowid/PK (composite PK, WITHOUT ROWID, or expression-derived blob column) only paid the O(FieldCount) scan plus the `pragma_table_info` query (`SqliteDataRecord.cs:375-381`) once. In the new code, nothing is added to `RowIds` on the "not found" path (`Add` only happens at `:355`/`:387`), so every repeated `GetStream` call on such a column re-runs the full scan and re-executes the `pragma_table_info` command against the connection — a per-row performance regression for exactly the streaming-blob-per-row use case this API exists for.
- Suggested test: extend `GetStream_works_when_composite_pk` (or add a variant) to call `reader.GetStream(2)` twice and assert both return equivalent, correct data — this won't directly prove the perf regression but guards against a naive fix (e.g. reintroducing a sentinel) breaking correctness. For the perf concern itself, recommend re-adding a "no-rowid-found" marker to the dictionary (e.g. a nullable `RowIdInfo` cached negatively, or a companion `HashSet<string>`) so the memoization guarantee from before the refactor is restored.

### Minor / Out-of-Scope Observations

- **WITHOUT ROWID tables** (importance 20): the `pkColumns==1` branch (`:384`) doesn't distinguish rowid tables from WITHOUT ROWID tables, so a WITHOUT ROWID table's single INTEGER PK would still be treated as a rowid and handed to `SqliteBlob` (`:405`), which is expected to fail at `sqlite3_blob_open` time since blob I/O isn't supported on WITHOUT ROWID tables. This logic is unchanged by this diff (pre-existing behavior), so it's not a regression introduced by this PR — flagging only because it's an adjacent, currently-untested edge case in the same function.
- **Multi-result-set batches** — verified **not** a gap: `SqliteDataReader.NextResult()` (`src/Microsoft.Data.Sqlite.Core/SqliteDataReader.cs:142-145,180`) disposes the old `SqliteDataRecord` and constructs a brand-new one per statement in a batch, so `RowIds` never persists across result sets. No test needed here.

### New Test Quality Issues (`GetBytes_works_streaming_join`, `SqliteDataReaderTest.cs:148-183`)

1. **Dead assertion intent / Console.WriteLine noise** (`:159-160`):
```csharp
//reading fields that does not involve blobs should be ok
Console.WriteLine($"A.ID={reader.GetInt32(0)} B.ID={reader.GetInt32(2)}");
```
The comment states an intent to verify non-blob column reads are unaffected, but the line only prints to console — it asserts nothing and would pass even if `GetInt32` returned garbage or the values were swapped. This should be `Assert.Equal(1, reader.GetInt32(0)); Assert.Equal(1000, reader.GetInt32(2));` and the `Console.WriteLine` removed (test-output noise, no diagnostic value in an assertion-based suite).
2. **Stray/misleading comment** (`:163`, `"//get len of abuff"`) — describes nothing the following line does (it declares a buffer, not "getting a length"); leftover from editing, should be removed or corrected.
3. **Trailing whitespace in the raw SQL string** (`:154-158`) — cosmetic, inconsistent with the tight formatting of sibling tests, but harmless.
4. Test doesn't assert on the underlying stream type (`Assert.IsType<SqliteBlob>(...)`) the way `GetStream_Blob_works` (`:462-486`) does; it mirrors its direct sibling `GetBytes_works_streaming` (`:132-146`) in that respect, so this is stylistically consistent with its baseline rather than a real defect — low priority.

### Positive Observations

- The core regression from #32747 (single global `_rowidOrdinal` overwritten across tables in a join) is directly and correctly reproduced and fixed, and the new test's join shape (two INTEGER-PK tables, blob column from each, interleaved reads within one row) is exactly the minimal repro for that bug.
- Test style (using-block connection/reader lifecycle, `Assert.Equal([...], buffer)` collection-literal comparisons) matches the rest of the file.
- Existing sibling tests (`GetStream_Blob_works` theory cases, `GetStream_Blob_works_when_long_pk`, `GetStream_works_when_composite_pk`, `GetStream_works_when_composite_pk_and_rowid`, `SqliteDataReaderTest.cs:458-569`) already gave good single-table baseline coverage of the rowid/PK-resolution branches; the gaps above are specifically about the *new* per-key dictionary/caching semantics this PR adds on top of that baseline.

**Files referenced:**
- `/home/decaf/code/decaf-claude/competition/benchmark/repos/1/src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs` (lines 15-22, 39, 316-406)
- `/home/decaf/code/decaf-claude/competition/benchmark/repos/1/test/Microsoft.Data.Sqlite.Tests/SqliteDataReaderTest.cs` (lines 132-146, 148-183, 458-569)
- `/home/decaf/code/decaf-claude/competition/benchmark/repos/1/src/Microsoft.Data.Sqlite.Core/SqliteDataReader.cs` (lines 135-193, `NextResult`)
- `/home/decaf/code/decaf-claude/competition/benchmark/repos/1/azure-pipelines.yml` (line 24, `_BuildConfig: Release`)
