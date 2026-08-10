# subagent agent-a437cb76b69caba96

Verification complete — three findings were confirmed empirically by compiling the post-merge `Microsoft.Data.Sqlite.Core` sources and running repros. Here is the full report.

---

# Silent-failure audit: PR #32770 (dotnet/efcore) — SqliteDataRecord.GetStream rowid caching

Reviewed: `/tmp/pr32770.diff` against the merged checkout at `/home/decaf/code/decaf-claude/competition/benchmark/repos/1` (`src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs`, `test/Microsoft.Data.Sqlite.Tests/SqliteDataReaderTest.cs`). Findings 1–3 were verified by building the actual merged source into a scratch project and executing repros; outputs are quoted verbatim.

## Finding 1 — CRITICAL: `Debug.Assert(rowIdForOrdinal != null)` fires on every legitimate fallback path and terminates the process in Debug builds

**Location:** `src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs:393`

**What fails:** The old assert, `Debug.Assert(_rowidOrdinal.HasValue)`, was a tautology — the code assigned `_rowidOrdinal = -1` immediately before the scan, so `HasValue` was always true and the assert never fired. The PR translated it into `Debug.Assert(rowIdForOrdinal != null)`, which is *not* a tautology: `rowIdForOrdinal` legitimately remains null whenever the rowid cannot be resolved. That is not an "impossible" state — it is the documented, test-asserted trigger for the MemoryStream fallback at lines 396–399 (the pre-existing test `GetStream_works_when_composite_pk` explicitly does `Assert.IsType<MemoryStream>(sourceStream)`).

**Concrete trigger (verified):** I compiled the merged sources in Debug and ran the exact query from the repo's own existing test `GetStream_works_when_composite_pk` (composite PK, no `rowid` in the SELECT):

```
about to call GetStream on composite-pk blob (fallback path)...
Process terminated.
Assertion failed.
rowIdForOrdinal!=null
   at Microsoft.Data.Sqlite.SqliteDataRecord.GetStream(Int32 ordinal) in .../SqliteDataRecord.cs:line 393
EXIT CODE: 134
```

On modern .NET a failed `Debug.Assert` without a debugger calls `Environment.FailFast` — the process dies with SIGABRT (I verified this separately with a minimal program; same exit 134). The reachable triggers are all *ordinary* queries:
- `SELECT Value FROM Test` — blob selected without its PK column (FieldCount=1, the `i == ordinal` continue at line 334 skips everything → null). Hit by existing test `GetBytes_works` (test file line 97).
- Any expression column: `SELECT 'têst'`, `SELECT x'...'`, `SELECT 12`, `SELECT 1.2`. Hit by existing tests `GetChars_works` (261), `GetChars_works_when_buffer_null` (280), `GetChars_works_with_overflow` (299), `GetChars_throws_when_dataOffset_out_of_range` (324), `GetStream_works` (373), `GetStream_works_with_text` (395), `GetStream_works_with_int` (416), `GetStream_works_with_float` (437), and the GetTextReader tests.
- Composite PK without rowid in select — existing test `GetStream_works_when_composite_pk` (516).

**User impact:** Any application referencing a Debug build of Microsoft.Data.Sqlite dies instantly on `GetBytes`/`GetChars`/`GetStream`/`GetTextReader` over these extremely common query shapes. The repo's own test suite hits this assert in at least ~11 pre-existing tests, so a Debug-configuration test run would crash the xunit host. [Inference] dotnet/efcore CI validates PRs in Debug configuration by default, so this would fail CI — I did not run the repo's full CI pipeline to confirm. In Release the assert is stripped and the null is routed into the fallback at line 396 — so Debug and Release now have divergent behavior: crash vs. silent degradation. That is the worst combination: loud where it shouldn't be, silent where the assert author apparently believed the state was impossible.

**Recommendation:** Delete the assert (the null case is an expected, handled state), or scope it to states that are genuinely impossible. Do not keep an assert whose failure condition is the designed input of the very next `if`.

## Finding 2 — CRITICAL: `_`-separator cache key collision returns wrong-row BLOB data silently, or throws a spurious SqliteException

**Location:** `src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs:328` (key construction), `:329` (collided lookup), `:355`/`:387` (Add under ambiguous key)

**What fails:** `$"{blobDatabaseName}_{blobTableName}"` is not an injective encoding: database `main` + table `b_c` and attached database `main_b` + table `c` both produce key `main_b_c`. The scan itself (lines 339–349) correctly compares both database and table name per column — so within a single scan the resolved rowid genuinely belongs to the blob's table — but the *cache lookup* at line 329 has no such protection. A `RowIdInfo` cached for one (database, table) pair is served for a different pair, and the code then reads a rowid value from the wrong table's PK column and opens a `SqliteBlob` with it. The stored `RowIdInfo.TableName` (line 23) could have detected the mismatch but is never read anywhere — it is dead data.

**Concrete trigger (verified):** Attached in-memory DB as `main_b` containing table `c`; main DB contains table `b_c`. Query joins both, `c.Id = 2`:

```
bc.Data = AAAAAAAA (expect AAAAAAAA)
c.Data  = 11111111 (expect 22222222)          <- SILENT WRONG DATA
```
Reading `bc.Data` first caches key `main_b_c` → ordinal 0 (bc.Id = 1). Reading `c.Data` then collides on the same key, uses rowid 1 instead of 2, and returns row 1's blob from `main_b.c`. No exception, no log — the caller receives the wrong row's bytes.

Reversed read order produces the other failure mode:
```
c.Data  = 22222222 (expect 22222222)
bc.Data threw: SqliteException: SQLite Error 1: 'no such rowid: 2'.
```
A hard error on a perfectly valid query, with a message that mentions neither the collision nor the actual cause — a debugging dead end.

**User impact:** Silent data corruption is the worst possible failure class: an application using ATTACHed databases whose names compose ambiguously with table names (underscores are ubiquitous in both) reads the wrong row's BLOB with zero indication anything is wrong. The alternate mode is an unexplainable `no such rowid` exception that depends on *column read order*. This hits Release builds identically (no assert involved — both scans resolve successfully).

**Regarding the "can Add throw" question (Q3):** In single-threaded use, `RowIds.Add` cannot throw `ArgumentException` — each `Add` is reachable only when `TryGetValue` returned false in the same invocation, and each is followed by `break`. The collision manifests as a wrong cache *hit*, not a duplicate-key *add*. Under multithreaded misuse (out of the `DbDataReader` thread-safety contract), the old code raced benignly on an `int?`; the new code can throw `ArgumentException` from `Dictionary.Add` or corrupt the dictionary's internal state — a new failure mode, but Low severity since it is out of contract.

**Recommendation:** Key the cache on the pair, not a string concatenation — `Dictionary<(string? db, string? table), RowIdInfo>` — or use a non-occurring separator plus null handling. Either delete `RowIdInfo.TableName` or actually use it to validate cache hits.

## Finding 3 — HIGH: Negative results are no longer cached — the O(FieldCount) scan plus a full SQL pragma query re-executes on every GetStream call (silent performance failure)

**Location:** `src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs:329-394` (scan only caches on success at 355/387), `:274-286` (`GetBytes` calls `GetStream` per invocation)

**What fails:** The old code cached `-1` ("not found") so the scan ran at most once per record. The new code stores into `RowIds` only on success; when no rowid resolves, `TryGetValue` misses on *every* call and the full scan repeats: per non-matching column a `sqlite3_column_database_name`/`table_name` call, per candidate column a `sqlite3_table_column_metadata` call, and — for tables with a composite INTEGER PK — a full `SqliteCommand` creation, prepare, and `ExecuteScalar` of `SELECT COUNT(*) FROM pragma_table_info($table)` per scan. `GetBytes` (line 276) opens a fresh stream on every call, so a standard chunked-read loop pays this entire cost per chunk.

**Concrete trigger (verified):** Release build, 64 KB blob read in 4 KB chunks (16,000 `GetBytes` calls), 3-column select:

```
resolvable rowid (positive cache hit):  44 ms for 16000 GetBytes calls
unresolvable rowid (no negative cache): 136 ms for 16000 GetBytes calls
```
A 3x slowdown on a trivially narrow select; the gap grows with column count, and the composite-PK case adds one SQL statement execution per `GetBytes` call. Under the old code both cases behaved like the fast row after the first call.

**User impact:** Completely invisible. No error, no log — the application just gets slower, proportional to how often it reads BLOBs from composite-PK/WITHOUT-rowid-resolvable tables. Nobody will trace a "SQLite reads got slow after upgrading" report to this line. This is a textbook silent performance regression.

**Recommendation:** Cache the negative result too — e.g., store a sentinel `RowIdInfo` (or use `Dictionary<key, RowIdInfo?>` with a null value) so `TryGetValue` returning true with null means "known unresolvable."

**Fallback classification (Q1 direct answer):** The fully-buffered `MemoryStream(GetCachedBlob(ordinal))` fallback itself (line 396–398) is *pre-existing behavior preserved* — the old `_rowidOrdinal < 0` branch did exactly the same, and `GetCachedBlob` (lines 480–498) buffers the entire blob via `sqlite3_column_blob(...).ToArray()` once per row (cache cleared on each `Read()` at lines 439–442). The PR actually *reduces* fallback frequency in one respect: the old single global `_rowidOrdinal = -1` poisoned all tables in the record once the first blob's table failed to resolve, whereas the new per-table cache lets other tables stream properly. What is new and degraded is (a) the repeated scan above and (b) the Debug-build crash of Finding 1 sitting in front of this fallback. The fallback remains silent — undocumented and unlogged — but that silence predates this PR.

## Finding 4 — MEDIUM: The new test cannot distinguish true streaming from the buffered fallback — it would silently pass if the fix regressed

**Location:** `test/Microsoft.Data.Sqlite.Tests/SqliteDataReaderTest.cs:148-184` (`GetBytes_works_streaming_join`)

**What fails:** The test's only assertions are byte-content checks via `GetBytes` (lines 174–180). If `GetStream(3)` for `B.VALUE` took the fallback path — `new MemoryStream(GetCachedBlob(3))` — the returned bytes would be identical (`sqlite3_column_blob` yields `x'05060708'`; offset 1, length 2 → `[0x06, 0x07]`), and the test passes. So the test verifies "no exception and right bytes," which does catch the *original* bug (old code paired B's table name with A's rowid → `no such rowid`), but it cannot detect a future regression where per-table resolution silently stops working and everything degrades to buffered mode. The sibling tests in the same file show the established pattern the author skipped: `GetStream_Blob_works` and `GetStream_works_when_composite_pk_and_rowid` assert `Assert.IsType<SqliteBlob>(sourceStream)`, and `GetStream_works_when_composite_pk` asserts `Assert.IsType<MemoryStream>`.

Also despite its name ("works_streaming"), the test never obtains a stream — it only calls `GetBytes`.

**User impact:** The regression-detection value of the test is much lower than intended; the exact class of silent degradation this PR is about would sail through green.

**Recommendation:** Add `using var streamA = reader.GetStream(1); Assert.IsType<SqliteBlob>(streamA);` and the same for ordinal 3. Also missing coverage: the reversed read order (B first, then A), a second blob column in the *same* table, and any case where one of the joined tables is unresolvable (which would immediately have exposed Finding 1, since that combination trips the assert).

## Finding 5 — LOW: Test and code hygiene — Console.WriteLine noise, change-history comments, dead code, formatting

**Locations:**
- `test/Microsoft.Data.Sqlite.Tests/SqliteDataReaderTest.cs:171` — `Console.WriteLine($"A.ID=... B.ID=...")` — debug noise in a committed test; if the intent was to verify non-blob fields read correctly, it should be `Assert.Equal(1, reader.GetInt32(0))` / `Assert.Equal(1000, reader.GetInt32(2))`. As written, a wrong integer read passes silently.
- `test/Microsoft.Data.Sqlite.Tests/SqliteDataReaderTest.cs:179` — comment `//this was failing. now should be fixed` narrates change history instead of stating behavior; line 173's `//get len of abuff` describes nothing the code does.
- `src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs:23` — `RowIdInfo.TableName` is written but never read anywhere (dead data; see Finding 2 for the validation it could have provided). `Ordinal`/`TableName` are also mutable (`get; set;`) with no reason to be.
- `src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs:39` — `readonly Dictionary<string, RowIdInfo> RowIds` breaks the file's conventions: missing `private` modifier, PascalCase name for a private field (everything around it is `_camelCase`).
- `src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs:17` — stray whitespace-only line added above the class; `:393` — `rowIdForOrdinal!=null` missing spaces around the operator.

## Clean categories (checked explicitly)

**Q5 — swallowed/converted exceptions:** Clean. The PR adds no catch blocks. In the touched path, `sqlite3_table_column_metadata`'s return code is checked and thrown via `SqliteException.ThrowExceptionForRC` (line 369), and `command.ExecuteScalar()` (line 380) propagates freely. The only catch block in the file (lines 427–437, in `Read()`) is untouched by this PR, rethrows immediately, and sets `_alreadyThrown` solely so `Dispose()` (lines 455–461) does not throw a second, masking exception for the same failure — that is correct error-preservation, not suppression. `GetInt64(rowIdForOrdinal.Ordinal)` on a NULL rowid (e.g., outer-join null row) throws a loud `InvalidOperationException` rather than failing silently — acceptable, and pre-existing in kind.

**Q4 — wrong-table rowid within a single scan:** Clean at scan level. The loop compares the per-column database name (lines 339–343) *and* table name (lines 345–349) against the blob's before considering a column, so a rowid resolved during a scan genuinely belongs to the blob's (database, table). The cross-table contamination exists only via the cache-key collision (Finding 2), not the scan.

**Q3 — duplicate-key `Add` in single-threaded use:** Clean; cannot throw (analysis under Finding 2).

## Verification notes

Repro method: compiled `src/Microsoft.Data.Sqlite.Core/**/*.cs` from the merged checkout into a scratch net10.0 project (`/tmp/sqliterepro`) with `SQLitePCLRaw.bundle_e_sqlite3` 2.1.7 and the embedded `Resources.resx`, then ran the scenarios above in Debug (Findings 1, 2) and Release (Finding 3). The `Debug.Assert`-terminates-process behavior was additionally confirmed with a standalone minimal program (exit code 134, "Process terminated. Assertion failed."). The one claim I did not verify end-to-end is the CI build configuration of dotnet/efcore ([Inference] that PR validation runs Debug and would therefore crash on the ~11 affected pre-existing tests); the assert firing itself on those tests' query shapes is verified.
