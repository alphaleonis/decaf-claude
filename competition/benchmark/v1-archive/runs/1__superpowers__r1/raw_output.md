The reviewer subagent's full report, verbatim:

---

I have everything needed for the review. All findings below are from direct inspection of the code at commit 9e69b85; I could not build or run the tests in this environment (no .NET SDK installed), so runtime claims are labeled accordingly.

### Strengths

- **The core fix is correct for the reported scenario.** Replacing the single cached `_rowidOrdinal` with a per-`(database, table)` lookup (`src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs:329-391`) directly addresses the #32770 bug: previously, the first blob read cached one rowid ordinal for the whole record, so a second blob column from a different table used the wrong table's rowid. I traced the new logic against the test's join (A blob at ordinal 1, B blob at ordinal 3): each table now resolves its own rowid ordinal. The single-table positive paths (`GetStream_Blob_works`, `_when_long_pk`, `_when_composite_pk_and_rowid`) are unchanged in behavior.
- **The regression test is well-constructed for catching the original bug.** Using distinct rowids (A.ID=1, B.ID=1000, `test/Microsoft.Data.Sqlite.Tests/SqliteDataReaderTest.cs:155-156`) means the old code path — opening a blob on table B with A's rowid 1 — cannot silently succeed, since B has no row with rowid 1. It also reads A's blob first, reproducing the failing order.
- **Scoped change.** The fix touches only `GetStream` and its cache state; no public API changes, no behavioral change for Release-mode consumers on previously working paths.

### Issues

#### Critical (Must Fix)

**1. The re-added `Debug.Assert` fires on legitimate, explicitly supported code paths — including several existing tests.**
`src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs:393`

```csharp
Debug.Assert(rowIdForOrdinal!=null);
```
followed three lines later (line 396) by code that handles `rowIdForOrdinal == null` as a valid fallback (`MemoryStream` over the cached blob).

In the old code the assert was vacuous: `_rowidOrdinal = -1` was assigned at the start of the scan, so `Debug.Assert(_rowidOrdinal.HasValue)` was always true. The commit message says "assert readded", but the re-added assert has *different semantics* — it now asserts a condition that is false whenever no usable rowid exists, which is a normal, supported situation. Existing tests that hit this path in a Debug build of the product assembly:

- `GetStream_works` (line 373) — `SELECT x'427E5743'`, expression column, no table
- `GetStream_works_with_text` / `_int` / `_float` (lines 395/416/437) — expression columns (any `GetTextReader`/`GetChars` on a computed column also routes through here)
- `GetStream_works_when_composite_pk` (line 516) — composite PK, no rowid selected
- `GetBytes_works` (line 97) — `SELECT Value FROM Test` with no key column in the select list

[Inference, expected framework behavior — not run here] In .NET Core, a failed `Debug.Assert` with no debugger attached terminates the process ("Process terminated. Assertion failed."), which would kill the test host for the whole suite. Even if termination behavior differed, an assert that contradicts the handled case immediately below it is wrong on its face.

Why CI didn't catch it: `azure-pipelines.yml:23-24` pins `_BuildConfig: Release` (asserts compiled out), while local `eng/common/build.sh:182` defaults to `Debug` — so this lands squarely on every local developer test run and any Debug-configuration validation.

**Fix:** delete the assert, or restore its vacuous intent by caching negative results (see Issue 2, which makes the null-after-scan state cacheable and the assert meaningful to remove).

#### Important (Should Fix)

**2. Negative results are no longer cached — the expensive rowid scan reruns on every read for no-rowid columns.**
`src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs:329-394`

The old code cached "no rowid found" as `_rowidOrdinal = -1`, so the scan ran at most once per record. The new code only populates `RowIds` when a rowid *is* found. When it isn't (expression columns, composite PK, key not in the select list), every `GetStream` call — and therefore every `GetBytes`/`GetChars`/`GetTextReader` call, since they call `GetStream` per invocation — re-runs the full scan: `sqlite3_column_database_name`/`table_name`/`origin_name` per column, `sqlite3_table_column_metadata` per candidate, plus executing a `SELECT COUNT(*) FROM pragma_table_info($table)` command (line 375-381). The common pattern of reading a blob in chunks via repeated `GetBytes` calls, per row, multiplies this. This is a performance regression relative to the code being fixed.

**Fix:** cache the negative result per key too, e.g. store a sentinel (`Ordinal = -1`) in `RowIds`, or use `Dictionary<string, int>` with `-1` meaning "no rowid".

**3. The cache key `$"{blobDatabaseName}_{blobTableName}"` can collide.**
`src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs:328`

Database names (attach aliases) and table names may contain underscores, so database `a_b` + table `c` and database `a` + table `b_c` both produce key `"a_b_c"`. On collision, a blob column would reuse the rowid ordinal cached for a different table, and the resulting `SqliteBlob` would be opened with the wrong rowid — wrong data or an exception. Obscure in practice (requires `ATTACH` with colliding names), but this is a correctness fix PR and the failure would be silent wrong data. **Fix:** key by a tuple (`(string?, string?)`) or a `ValueTuple` dictionary instead of string concatenation. (Also note both names are null for expression columns, giving the shared key `"_"` — harmless today only because negative results are never cached.)

**4. Test does not pin the streaming path.**
`test/Microsoft.Data.Sqlite.Tests/SqliteDataReaderTest.cs:149-181`

The new test verifies bytes via `GetBytes`, but a regression that made *both* columns silently fall back to the `MemoryStream` path (e.g., the rowid lookup failing entirely) would still pass, because the cached-blob fallback returns the same bytes. Sibling tests (`GetStream_Blob_works`, line 478) assert `Assert.IsType<SqliteBlob>(...)`. **Fix:** add `GetStream` calls asserting `SqliteBlob` for both columns, matching the established pattern.

#### Minor (Nice to Have)

- `src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs:20-30` — `RowIdInfo.TableName` is assigned but never read anywhere; the entire nested class reduces to an `int` ordinal. A `Dictionary<string, int>` (with `-1` sentinel per Issue 2) removes the class, the mutable settable properties, and the nullable-flow gymnastics.
- `src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs:39` — `readonly Dictionary<string, RowIdInfo> RowIds` breaks the file's conventions: missing explicit `private`, PascalCase where every other private field is `_camelCase` (should be `private readonly ... _rowIds`).
- `src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs:393` — `rowIdForOrdinal!=null` missing spaces around the operator; line 17 adds a stray blank line after the namespace brace; the diff also drops a blank line after `var pkColumns = -1L;`. Style noise in an otherwise clean file.
- `src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs:327` — `RowIdInfo? rowIdForOrdinal = null;` is redundant; `TryGetValue(..., out var rowIdForOrdinal)` suffices. Local `rowidkey` should be `rowIdKey`.
- `test/Microsoft.Data.Sqlite.Tests/SqliteDataReaderTest.cs:168` — `Console.WriteLine` debug output left in the test; line 171 comment "//get len of abuff" is inaccurate (nothing gets a length), and line 179 "//this was failing. now should be fixed" is change-history narration rather than a description of what the test verifies.
- [Unverified — pre-existing limitation, not a regression] A self-join of the same table (`A a1 JOIN A a2`, both blobs selected) still resolves both blob columns to one shared rowid ordinal, because `sqlite3_column_table_name` reports the real table name, not the alias — both instances share the cache key. The old code had the same flaw, and the SQLite metadata API arguably cannot distinguish aliases; worth a code comment at minimum.

### Recommendations

- Combine the fixes for Issues 1-3 into one small change: `Dictionary<(string?, string?), int>` keyed by tuple, store `-1` for "not found", drop the assert (or keep it asserting the dictionary now contains the key). That restores the old code's exactly-once scan guarantee per table, removes the collision, and removes the false assert — with less code than the current patch.
- Run the Microsoft.Data.Sqlite test suite in **Debug** configuration before merge; the CI Release matrix compiles the failing assert away, so Release CI green is not evidence this commit is healthy.

### Assessment

**Ready to merge?** No

**Reasoning:** The core multi-blob fix is sound and correctly tested for the reported scenario, but the re-added `Debug.Assert` now fires on multiple pre-existing supported paths (expression columns, composite PKs) — a Debug-build breakage that Release-only CI masks — and the loss of negative-result caching is a per-call performance regression on the fallback path. Both are small, contained fixes; with them (and ideally the tuple key), this is mergeable.
