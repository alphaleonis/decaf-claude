# subagent agent-a52f01b8029ba9393

All findings verified. The post-merge history is conclusive: this exact commit was reverted upstream because of the assertion failure I traced. Here is the complete report.

---

# Error Handling Audit — dotnet/efcore PR #32770 ("Microsoft.Data.Sqlite.Core issue with multiple Blob colums")

**Scope:** `/home/decaf/code/decaf-claude/competition/benchmark/repos/1/src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs` (GetStream, lines 316–405; RowIdInfo, lines 20–30; RowIds field, line 39) and `/home/decaf/code/decaf-claude/competition/benchmark/repos/1/test/Microsoft.Data.Sqlite.Tests/SqliteDataReaderTest.cs` (lines 148–184), plus blast radius into `/home/decaf/code/decaf-claude/competition/benchmark/repos/1/src/Microsoft.Data.Sqlite.Core/SqliteBlob.cs`. HEAD 9e69b85 is the squash-merge of the PR. All code-path claims below are verified by direct code trace unless labeled otherwise; I could not run the tests (no .NET SDK in this environment).

**Headline result (externally verified):** The central defect predicted by this audit actually happened. Via the GitHub API: the merged commit 9e69b85b9 was **reverted upstream** in commit 101a0bd6a (PR #32945, "Revert Microsoft.Data.Sqlite.Core issue with multiple Blob colums") because of issue #32944, titled *"Assertion failure in SQLite following Blob column PR"* — the exact Debug.Assert defect in Finding 2. The fix was re-landed in commit 57dad6693 (PR #33111) with the assert commented out (`//Debug.Assert(rowIdForOrdinal!=null);` plus the comment `//rowIdForOrdinal == null => matching rowid not found, MemoryStream returned`). Findings 1, 3, 4, and 5 are NOT addressed by the re-land — the same key scheme and uncached negative path persist in upstream `main` today (verified by fetching the current upstream file).

---

## Finding 1 — Negative result no longer cached: full metadata scan silently re-runs on every GetStream call

- **Location:** `SqliteDataRecord.cs:329–394` (scan) and `396–399` (fallback). Compare pre-PR code (git show `9e69b85~1`): old code assigned `_rowidOrdinal = -1` *before* the scan, permanently caching "not found."
- **Severity:** Medium (silent performance failure; no correctness impact)
- **Issue:** When the scan finds no usable rowid ordinal (WITHOUT ROWID table, composite PK, PK not in the SELECT list, single-column SELECT, expression column), `rowIdForOrdinal` stays null and **nothing is written to `RowIds`**. Line 396 then falls back to `new MemoryStream(GetCachedBlob(ordinal), false)`. The next `GetStream` call for any column of that table repeats the entire scan: per-column `sqlite3_column_database_name`/`sqlite3_column_table_name`/`sqlite3_column_origin_name` native calls, `sqlite3_table_column_metadata` native calls (line 359), and — because `pkColumns` is a local reset each call — a fresh `SELECT COUNT(*) FROM pragma_table_info(...)` command execution (lines 375–381). This compounds badly: `GetBytes` (line 276) opens a new stream on **every invocation**, so the standard chunked-read loop (`while (reader.GetBytes(...)) ...`) issues one hidden SQL query plus O(FieldCount) native metadata calls *per chunk, per row*.
- **Is the fallback itself appropriate?** Yes — falling back to a fully materialized `MemoryStream` when no rowid can be resolved is pre-existing, deliberate, and matches the documented Microsoft.Data.Sqlite behavior (blob streaming requires the rowid); the existing tests `GetStream_works_when_composite_pk` (test file line 516, asserts `IsType<MemoryStream>`) and `GetBytes_works` (line 96) codify it as supported. It does not mask a wrong-rowid situation; it degrades streaming to in-memory materialization, which is the documented contract. What the PR broke is only the **negative caching** — a silent regression with zero observable signal: no exception, no log, just repeated hidden queries. Nobody will connect "my blob reads got slower" to this diff.
- **User impact:** Applications reading blobs from composite-PK or WITHOUT ROWID tables via chunked `GetBytes`/`GetChars` silently execute an extra SQL query and a batch of native interop calls per chunk per row. Undetectable except by profiling.
- **Recommendation:** Restore negative caching — store a sentinel entry (e.g., `RowIds.Add(rowidkey, NotFoundSentinel)` or use `Dictionary<string, RowIdInfo?>` and add `null`) after the scan completes without a match, and treat the sentinel as "use MemoryStream." Note this is still missing in upstream `main` (verified).
- **Example:**
  ```csharp
  if (!RowIds.TryGetValue(rowidkey, out rowIdForOrdinal))
  {
      // ... scan ...
      RowIds[rowidkey] = rowIdForOrdinal; // cache the miss too (null == "no rowid; materialize")
  }
  ```

## Finding 2 — `Debug.Assert(rowIdForOrdinal != null)` fires on legitimate, test-covered paths; silent in Release, process-fatal in Debug

- **Location:** `SqliteDataRecord.cs:393`
- **Severity:** Critical (confirmed by upstream revert)
- **Issue:** The old assert (`Debug.Assert(_rowidOrdinal.HasValue)`) was trivially always-true because `-1` was assigned before the scan — a dead assert. The PR "readded" it (third commit message: "assert readded") against the new nullable variable, where it now asserts a condition that the code **three lines later (line 396) deliberately handles as a supported fallback**. The assert and the fallback directly contradict each other, and the test suite proves the fallback is the intended behavior. Reachable null paths, all legitimate:
  - Composite PK, PK columns in SELECT: existing test `GetStream_works_when_composite_pk` (SqliteDataReaderTest.cs:516) — expects `MemoryStream`, i.e., the test asserts the exact state the assert declares impossible.
  - Blob column with no other columns from its table in the SELECT: existing tests `GetBytes_works` (line 96, `SELECT Value FROM Test`), `GetBytes_NullBuffer`, `GetBytes_works_with_overflow`.
  - WITHOUT ROWID tables; non-INTEGER PKs; expression/computed blob columns (null database/table name → key `"_"`, scan matches nothing).
- **Hidden/inverted failure mode:** In Release builds the assert compiles out — the contradiction is silent and harmless. In Debug builds, a failed `Debug.Assert` on .NET Core writes the assertion and terminates the process via FailFast when no debugger is attached [Inference — standard .NET behavior, consistent with the "Assertion failure" issue title]. So the failure is catastrophic exactly where the code path is *correct and supported*, and invisible in production. This is the inverse of useful error signaling.
- **User impact (verified historically):** Applications and test suites consuming Debug builds crashed on ordinary blob reads. Upstream issue #32944 ("Assertion failure in SQLite following Blob column PR") was filed, the entire PR was reverted (#32945), and the re-land (#33111) shipped with the assert commented out. This one line cost the fix a full revert cycle.
- **Recommendation:** Delete the assert (as the re-land effectively did). An assert must never contradict an intentionally supported branch of the same method. If the intent was "assert we found a rowid *when one should exist*," that condition is not expressible here — the null case is a first-class outcome, not a bug state.

## Finding 3 — Ambiguous cache key `$"{db}_{table}"`: colliding (database, table) pairs silently share a rowid ordinal

- **Location:** `SqliteDataRecord.cs:328` (key construction), `329` (lookup), `402` (use), downstream `SqliteBlob.cs:77–85`
- **Severity:** Medium (silent wrong-data failure mode; narrow precondition)
- **Issue:** The key concatenates database and table names with `_`, which both names may legally contain. Distinct pairs collide: database `main_x` + table `y` and database `main` + table `x_y` both produce `"main_x_y"`. This requires an ATTACHed database whose name contains an underscore alongside a main-database table with a matching name split — narrow, but nothing prevents it and nothing detects it. On collision, the second table's lookup returns the first table's `RowIdInfo`; `GetInt64(rowIdForOrdinal.Ordinal)` (line 402) then reads an unrelated column's value as the rowid.
- **Hidden errors (traced through SqliteBlob):** `SqliteBlob`'s constructor passes the wrong rowid to `sqlite3_blob_open` (`SqliteBlob.cs:77–84`) against the *correct* database/table/column. Two outcomes:
  1. The wrong rowid does not exist in that table → `SqliteException` from `ThrowExceptionForRC` (`SqliteBlob.cs:85`) with a generic native message [Inference: SQLite reports "no such rowid" for this rc] — an error with zero indication that a cache-key collision caused it. A developer would stare at a valid query and a valid row and see an impossible failure.
  2. The wrong rowid *does* exist (plausible — join key values are often valid rowids) → the blob opens successfully and **returns another row's data with no error whatsoever**. Silent data corruption.
- **No guard exists:** `RowIdInfo.TableName` is written (lines 354, 386) but **never read anywhere** (verified by grep across the library) — it is dead state that could have validated the cache hit but doesn't. The database name isn't stored at all.
- **Recommendation:** Use a collision-proof key: a `(string dbName, string tableName)` value-tuple key (dictionary of `Dictionary<(string?, string?), RowIdInfo>`), which is also allocation-cheaper than string interpolation. Delete the dead `TableName` property or actually use it (plus a `DatabaseName`) as a hit-validation guard. Still unfixed upstream (verified: `main` uses the same `rowidkey` interpolation).
- **Example:**
  ```csharp
  private readonly Dictionary<(string? Db, string? Table), RowIdInfo> _rowIds = new();
  ...
  var rowidKey = (blobDatabaseName, blobTableName);
  ```

## Finding 4 — Self-join: same table aliased twice shares one cache entry; blob is read from the wrong row with no error at all

- **Location:** `SqliteDataRecord.cs:328–329, 345, 354/386, 402`
- **Severity:** High (completely silent wrong data on a realistic query shape) — pre-existing failure class, not a regression, but the PR claims to fix exactly this bug class and structurally bakes the limitation in.
- **Issue (traced):** For `SELECT a1.ID, a1.VALUE, a2.ID, a2.VALUE FROM A a1 JOIN A a2 ON ...`, `sqlite3_column_table_name` returns the real table name `"A"` for columns of **both** alias instances (the SQLite C API does not expose aliases at column level). Both blob columns therefore map to key `"main_A"`. The first `GetStream` scan matches the first `A` column that is an INTEGER single-column PK — `a1.ID` at ordinal 0 — and caches `Ordinal = 0`. When the caller streams `a2.VALUE`, the cache hit returns ordinal 0, so `rowid = GetInt64(0)` = **a1's row id**, and `SqliteBlob` opens table `A` at a1's row. The caller receives a1's blob content while reading a2's column. If the joined rows differ, this is wrong data; no exception, no log, no assert (the assert at 393 is inside the not-found branch and is bypassed on a cache hit), nothing.
- **Nuance:** Even without the cache, the linear scan itself cannot distinguish alias instances (it matches the first qualifying column of table A, excluding only the blob's own ordinal `i == ordinal` at line 334) — so the old single-`_rowidOrdinal` code had the same wrong-row behavior. The PR fixed cross-*table* joins but leaves the same-*table* case silently broken, and the new per-(db,table) cache makes the limitation structural. The PR's own test covers only `A JOIN B` (distinct tables); no self-join test exists.
- **User impact:** Hierarchies and graph queries (parent/child self-joins — precisely the `FATHER_ID` shape the PR's own test models across two tables) that stream blobs from both sides of a self-join get one side's data for both. This is the worst kind of failure: plausible query, valid-looking results, wrong bytes, zero diagnostics.
- **Recommendation:** At minimum, detect the ambiguity and refuse to stream: during the scan, if more than one qualifying rowid-candidate ordinal exists for the same (db, table) at *different* ordinal groups (i.e., the table appears via multiple instances), fall back to `MemoryStream` (correct data, no streaming) instead of guessing — the existing fallback is the honest degradation path. Detecting instance multiplicity is possible by counting distinct occurrences of the table's PK/rowid column among result columns. Document the limitation either way.

## Finding 5 — `RowIds.Add` duplicate-key throw surface

- **Location:** `SqliteDataRecord.cs:355, 387`
- **Severity:** Low
- **Issue:** Sequentially, `Add` cannot throw: the block is only entered when `TryGetValue` missed (line 329), each scan performs at most one `Add` (both sites `break` immediately), and the only reentrancy inside the guard window — the nested `pragma_table_info` command at lines 375–381 — cannot re-enter this record's `GetStream`. The residual risk is concurrent `GetStream` calls on one reader from multiple threads: between one thread's `TryGetValue` and `Add`, another thread can insert the same key, producing `ArgumentException: An item with the same key has already been added` — or, worse, unsynchronized `Dictionary` mutation can corrupt internal state (historically manifesting as hangs) with no exception at all. `DbDataReader` is not thread-safe by contract, so this is out-of-contract use; but the failure would surface as a baffling collection exception deep in `GetBytes` rather than anything naming the real cause.
- **Recommendation:** Use the indexer (`RowIds[rowidkey] = rowIdForOrdinal;`) for idempotence — last-write-wins is harmless here since both writers compute the same value. This removes the exception surface without pretending the class is thread-safe.

## Finding 6 — Test verifies "non-blob fields should be ok" with Console.WriteLine, not assertions

- **Location:** `SqliteDataReaderTest.cs:170–171` (in `GetBytes_works_streaming_join`, lines 148–184)
- **Severity:** Low
- **Issue:** The comment says "reading fields that does not involve blobs should be ok," but the check is `Console.WriteLine($"A.ID={reader.GetInt32(0)} B.ID={reader.GetInt32(2)}")`. Only a *thrown exception* from `GetInt32` is detectable; wrong values (1 and 1000 are the known-correct expectations) pass silently — which matters here, because a blob-cache/ordinal bookkeeping bug corrupting adjacent column reads is exactly the regression class this PR touches. Additionally, xunit v2+ does not capture `Console.WriteLine` (output requires `ITestOutputHelper`) [Inference — standard xunit behavior], so the string is invisible in test logs: as verification it is dead code. Minor additional note: the `GetBytes` return values at lines 175 and 179 are discarded, but the subsequent content assertions on the zero-initialized buffers would catch a short read, so that is mitigated.
- **Recommendation:**
  ```csharp
  Assert.Equal(1, reader.GetInt32(0));
  Assert.Equal(1000, reader.GetInt32(2));
  ```
  The test also leaves the highest-risk scenarios of the new design uncovered: self-join (Finding 4), a no-rowid table inside a join (Findings 1 and 2 — a test here would have caught the assert before merge, sparing the revert), and repeated chunked `GetBytes` on a no-rowid table (Finding 1).

---

## What is done well

- The native return code from `sqlite3_table_column_metadata` is still checked and thrown (`SqliteException.ThrowExceptionForRC`, line 369) — no swallowed rc on the scan path.
- Cache lifetime is sound: a fresh `SqliteDataRecord` is created per result set (`SqliteDataReader.cs:180`), so cached ordinals can never go stale across statements, and `RowIds` correctly survives row advances (ordinals are per-statement, not per-row).
- The MemoryStream fallback itself preserves correctness (right data, degraded mode) rather than guessing — the honest choice.

## Summary table

| # | Severity | Location | Failure mode | Upstream status |
|---|----------|----------|--------------|-----------------|
| 1 | Medium | SqliteDataRecord.cs:329–399 | Silent per-call re-scan + hidden `pragma_table_info` query for no-rowid tables | Still present in `main` |
| 2 | Critical | SqliteDataRecord.cs:393 | Assert contradicts supported fallback; Debug crash / Release silence | Caused revert #32945; assert commented out in #33111 |
| 3 | Medium | SqliteDataRecord.cs:328 | Key collision → wrong rowid → wrong data or opaque SqliteException; dead `TableName` guard | Still present in `main` |
| 4 | High | SqliteDataRecord.cs:328–402 | Self-join → wrong row's blob, zero diagnostics (pre-existing class) | Still present in `main` |
| 5 | Low | SqliteDataRecord.cs:355, 387 | `Add` ArgumentException / dictionary corruption under out-of-contract concurrency | Still present in `main` |
| 6 | Low | SqliteDataReaderTest.cs:170–171 | Console.WriteLine as a "check"; wrong values undetectable | Still present in `main` |
