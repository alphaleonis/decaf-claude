# subagent agent-a272a7de4e1c0c5ce

## Test Coverage Analysis — PR fixing #32747 (`SqliteDataRecord.GetStream` multi-table blob caching)

### Summary

The new test `GetBytes_works_streaming_join` (test/Microsoft.Data.Sqlite.Tests/SqliteDataReaderTest.cs:148-184) validates the headline scenario from the bug report — two distinctly-named tables joined together, each with a blob column, both resolved correctly. That's a real regression test for the reported symptom. However, the fix introduces a new caching key scheme (`$"{db}_{table}"`) and a behavioral change to the not-found path (no more negative caching, and a `Debug.Assert` that can now fire on a legitimate outcome), and the test suite does not exercise either of those changes. Most concerning: an **existing, unmodified test already in the suite appears to now violate the new `Debug.Assert`** in Debug builds — this wasn't caught because there's no indication the PR was validated in a Debug configuration test run.

I could not execute the test suite in this environment (no `dotnet` installed), so the `Debug.Assert` finding below is a **static-analysis inference**, not an observed failure — flagging it as `[Inference]` per verification requirements, and recommending it be confirmed by actually running the suite in Debug config.

---

### Critical Gaps

**1. Gap score: 9/10 — Self-join reintroduces the exact bug class this PR fixes, completely untested**
File: `src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs:325,328` (`blobTableName` / `rowidkey` construction)
`sqlite3_column_table_name` returns the *un-aliased* origin table name, not the query alias. In a self-join (`SELECT a.blob, b.blob FROM T a JOIN T b ON ...`), both blob columns resolve to the same `blobTableName` ("T") and, typically, the same `blobDatabaseName` ("main") — so both compute the identical `RowIds` key (`"main_T"`). The first blob column's cache-miss scan will find *a* `rowid`/PK column matching table name "T" (whichever alias's column appears first that matches the origin-name checks) and cache it under that shared key; the second blob column then gets a cache **hit** and reuses the wrong ordinal — the same cross-table contamination bug the PR is fixing, just now scoped to same-table self-joins instead of different-table joins.
[Inference]: I traced this from the documented semantics of `sqlite3_column_table_name`/`sqlite3_column_origin_name` (no alias information exposed), not from an executed test — worth confirming empirically.
**Test suggestion:** Two-row self-join, e.g. `SELECT p.ID, p.VALUE, c.ID, c.VALUE FROM T p JOIN T c ON c.PARENT_ID = p.ID` where `T` has distinct blob values per row; assert `GetBytes` on both aliases' blob columns returns each alias's own (different) blob content.

**2. Gap score: 9/10 — `Debug.Assert(rowIdForOrdinal!=null)` now fires on a legitimate not-found path, and an existing test already exercises it**
File: `src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs:393` (assert) and `:396-398` (the legitimate not-found fallback)
The OLD code set `_rowidOrdinal = -1` as a sentinel before scanning, so `Debug.Assert(_rowidOrdinal.HasValue)` always passed even when no rowid/PK-alias column was found (composite PK case). The NEW code leaves `rowIdForOrdinal` as `null` in that same case, so `Debug.Assert(rowIdForOrdinal!=null)` at line 393 now fails whenever the not-found path is legitimately taken.
Critically, `test/Microsoft.Data.Sqlite.Tests/SqliteDataReaderTest.cs:515-541` (`GetStream_works_when_composite_pk`, **pre-existing, unmodified by this PR**) is exactly this scenario: a composite two-column PK table with no `rowid` alias selected. Under the new code this should hit the failing assert in a Debug build. `.NET`'s default trace listener behavior for a failed `Debug.Assert` (no debugger attached) is to call `Environment.FailFast`, which can abort the whole test process, not just fail one test.
[Inference]: I was not able to execute the test suite in this sandbox (no `dotnet` binary) to observe this directly — this is derived from reading the code paths and default `Debug.Assert`/`DefaultTraceListener` semantics, and should be verified by running `dotnet test` in Debug configuration before merge.
**Test/verification suggestion:** Run the existing `GetStream_works_when_composite_pk` test in a Debug build and confirm it doesn't crash/fail; if it does, either restore an explicit sentinel value (distinct from "not yet scanned") for the not-found case, or remove/relax the assert.

**3. Gap score: 7/10 — Dictionary key collision from naive string concatenation (`db + "_" + table`)**
File: `src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs:328` (`string rowidkey = $"{blobDatabaseName}_{blobTableName}";`)
Because both segments are freeform SQLite identifiers that can themselves contain underscores, two different `(database, table)` pairs can collide: e.g. database `"a_b"` + table `"c"` produces the same key as database `"a"` + table `"b_c"`. A `Dictionary<(string Database, string Table), RowIdInfo>` (tuple key) would eliminate this class of bug entirely and is a trivial fix.
**Test suggestion:** `ATTACH DATABASE ':memory:' AS "db_x";` create table `y` in it with a blob column; in `main`, create table `x_y` with a blob column; join them and assert each blob resolves to its own table's rowid rather than colliding.

**4. Gap score: 7/10 — ATTACH'ed database with a same-named table (the other half of the fix's own key design) is unexercised**
File: `src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs:324-328`
The new key format is `database_table` specifically to disambiguate by database as well as table — but the new test only varies the table half (`A` vs `B` in the default `main` database); it never proves the database half works. This is the scenario explicitly implied by the fix's own design and is untested.
**Test suggestion:** `ATTACH DATABASE ':memory:' AS ext;` create a table named identically in both `main` and `ext` (e.g. both called `Data`, each with its own blob column and distinct content), join across schemas, and assert each side's `GetBytes` returns its own schema's blob.

### Important Improvements

**5. Gap score: 6/10 — No test proves the fix works "in reverse" (second table doesn't clobber the first one's cached entry)**
File: `test/Microsoft.Data.Sqlite.Tests/SqliteDataReaderTest.cs:149-184`
The new test reads table A's blob once, then table B's blob once — each hitting a cache-miss populate exactly once. It never re-reads table A's blob *after* B's entry has been cached, which is the more direct inverse of the original bug ("a single cached ordinal was reused across tables" — i.e., does populating B's entry disturb A's?). With a `Dictionary` keyed per table this is low-risk, but it's the most literal regression check for the reported symptom and costs one extra `GetBytes` call.
**Test suggestion:** After asserting B's blob, re-call `reader.GetBytes(1, 1, abuff, 0, 2)` on A's column again and assert it still returns `[0x02, 0x03]`.

**6. Gap score: 5/10 — No multi-row loop through the joined/cached path**
File: `test/Microsoft.Data.Sqlite.Tests/SqliteDataReaderTest.cs:149-184`
Every `GetStream`/blob test in the file (new and pre-existing) reads a single row. The dictionary is populated once and then presumably reused across `reader.Read()` iterations in real usage, but nothing in the suite proves the cached entries stay valid/correct across multiple rows of a joined query.
**Test suggestion:** Insert 2-3 parent/child rows with distinct blob values, loop `while (reader.Read())`, and assert each row's A/B blobs match that row's own data (not a value from a previous row).

**7. Gap score: 4/10 — WITHOR ROWID table with a single-column INTEGER-typed PK, in a join**
File: `src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs:370-390` (the `pkColumns == 1L` branch)
A single-column PK on a `WITHOUT ROWID` table can satisfy `dataType=="INTEGER" && primaryKey!=0 && pkColumns==1`, causing the code to treat it as a rowid-alias and construct a `SqliteBlob` using that value as a rowid — but `WITHOUT ROWID` tables have no rowid, so `sqlite3_blob_open` would fail at runtime. This looks pre-existing (not introduced by this PR) but the PR touches this exact branch without adding a regression test for it, and it's more likely to surface now that multi-table joins are a supported/tested configuration.
**Test suggestion:** `CREATE TABLE Data (Id INTEGER PRIMARY KEY, Value BLOB) WITHOUT ROWID;` joined with a normal rowid table; assert either correct fallback behavior or a clear, actionable exception rather than a raw SQLite error.

**8. Gap score: 3/10 — Expression/computed blob column (empty table name) alongside a join**
File: `src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs:324-325,328`
An expression column has empty `blobDatabaseName`/`blobTableName`, producing key `"_"`. Not-found is the correct outcome (fall back to `GetCachedBlob`), but this exercises the same `Debug.Assert` problem as gap #2, and if a query had two independent expression-derived blob columns they'd share key `"_"` (though the impact there is benign since both fall through to the null branch regardless).
**Test suggestion:** low priority given overlap with gap #2's fix; if that's addressed, a quick case (`SELECT hex(Value), Value FROM ...` or similar) would round it out.

### Test Quality Issues (in `GetBytes_works_streaming_join` itself)

- **Debug output left in production test code** — `Console.WriteLine($"A.ID={reader.GetInt32(0)} B.ID={reader.GetInt32(2)}");` at line 171. This is the only `Console.WriteLine` in the entire `SqliteDataReaderTest.cs` file (confirmed via grep across the file) — it's inconsistent with repo conventions and adds no verification value since nothing asserts on the output.
- **Unused/unasserted values** — the comment above the `Console.WriteLine` claims "reading fields that does not involve blobs should be ok," but the returned `GetInt32` values are never checked with `Assert.Equal`. As written, the test only proves those calls don't throw; it silently accepts a wrong value (e.g., `0` instead of `1`) since nothing compares it. Should be `Assert.Equal(1, reader.GetInt32(0)); Assert.Equal(1000, reader.GetInt32(2));`.
- **Stale/misleading comment** — `//get len of abuff` above `var abuff = new byte[2];` doesn't describe what the code does (it allocates a fixed 2-byte buffer, not "get a length").
- **Vague regression-test annotation** — `//this was failing. now should be fixed` narrates change history without pointing at the issue (repo convention elsewhere favors linking a specific bug, or at minimum the comment should say what the regression *is* rather than "now should be fixed").
- **Assertion style is otherwise consistent** — `Assert.Equal([0x02, 0x03], abuff)` collection-literal style matches `GetBytes_works_streaming` (line 143) and other tests in the file; no issue there.

### Positive Observations

- The new test directly reproduces the reported bug's primary symptom (two joined tables, each with a blob column, wrong-table rowid reuse) and would have failed against the pre-fix code.
- It reuses the file's established `using (var connection = ...)` / `ExecuteNonQuery` / `ExecuteReader` scaffolding, keeping it consistent with neighboring tests rather than introducing new test infrastructure.
- The surrounding `GetStream_*` test family (`test/Microsoft.Data.Sqlite.Tests/SqliteDataReaderTest.cs:458-569`) already gives solid single-table coverage of the rowid-resolution branches (plain PK, composite PK, composite PK + explicit rowid, long PK values) — the gaps above are specifically about the *new* multi-table dictionary behavior, not a wholesale coverage hole in the method.

### Files referenced
- `/home/decaf/code/decaf-claude/competition/benchmark/repos/1/src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs` (lines 316-405, plus the new `RowIdInfo` class at 20-30 and `RowIds` field at 39)
- `/home/decaf/code/decaf-claude/competition/benchmark/repos/1/test/Microsoft.Data.Sqlite.Tests/SqliteDataReaderTest.cs` (new test at 148-184; related existing tests at 96-146, 373-577)
