Here is the reviewer subagent's full report, verbatim:

---

# Code Review: Multiple BLOB columns fix in SqliteDataRecord (#32770)

**Scope reviewed:** commit `9e69b85b90e0d490fa46dbf25ffac0c3f7747455` (2 files: `src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs`, `test/Microsoft.Data.Sqlite.Tests/SqliteDataReaderTest.cs`). I read both the before and after versions of `GetStream` in full, plus the surrounding record/reader lifetime code and the existing blob test suite.

**Verification limits:** No dotnet SDK is installed in this environment, so I could not build the project or run the test suite. All findings below are from static reading of the code; items depending on runtime behavior are marked [Inference].

### Strengths

- **The root cause is correctly identified and addressed.** The old code cached a single `_rowidOrdinal` per record; the first blob read pinned it to the first table's rowid column, and blob reads from any *other* table then constructed `SqliteBlob(db, tableB, col, rowidFromTableA)` — wrong row or "no such rowid". Replacing the single cached ordinal with a per-`(database, table)` lookup is the right general shape of the fix, not a symptom patch (SqliteDataRecord.cs:327–404).
- **Well-designed regression test.** `GetBytes_works_streaming_join` (SqliteDataReaderTest.cs:148–181) deliberately gives table B a rowid (1000) different from A's (1), so under the old code the second `GetBytes` fails loudly instead of silently passing on coincidentally-matching data. It reads A's blob first to poison the old cache — exactly the failure sequence from issue #32770.
- **Cache lifetime is sound for the positive case.** `RowIds` lives on `SqliteDataRecord`, which `SqliteDataReader` creates once per result set (SqliteDataReader.cs:180) and reuses across `Read()` calls. Rowid *ordinals* are statement-level metadata, so caching them across rows is correct.
- **Release-build fallback preserved.** The `rowIdForOrdinal == null` → `MemoryStream(GetCachedBlob(...))` path keeps the pre-existing non-streaming fallback intact (SqliteDataRecord.cs:396–399).

### Issues

#### Critical (Must Fix)

**1. `Debug.Assert(rowIdForOrdinal != null)` fires on legitimate, previously-supported paths — Debug builds of the existing test suite will trip it.**
- **File:** `src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs:393`
- **What's wrong:** The old assert `Debug.Assert(_rowidOrdinal.HasValue)` was trivially true (the code assigned `_rowidOrdinal = -1` before the scan), so it never fired. The rewritten assert (`rowIdForOrdinal != null`) asserts a condition that is *false* in fully supported scenarios: no other column of the blob's table in the result set, expression columns, composite-PK tables — the very cases the `MemoryStream` fallback on line 396–399 exists to serve.
- **Why it matters:** At least these existing tests reach the scan with no rowid found: `GetBytes_works` (`SELECT Value FROM Test`, line 97), `GetStream_works` / `_with_text` / `_with_int` / `_with_float` (pure expressions, lines 373–456), `GetStream_works_when_composite_pk` (line 516), plus the `GetChars`/`GetTextReader` tests that route through `GetStream`. [Inference — could not run tests here, no SDK] In a Debug-configuration run these assert failures fail hard (on .NET Core a failed `Debug.Assert` without a debugger terminates the process); either way, Debug CI runs break. The commit message says "assert readded," which suggests a reviewer asked for the assert back and it was re-added asserting a different, incorrect invariant.
- **Fix:** Remove the assert, or restore the negative sentinel (see issue 2) so the asserted invariant is "lookup was resolved," not "a rowid exists."

#### Important (Should Fix)

**2. Negative caching was lost — the full metadata scan reruns on every `GetStream`/`GetBytes`/`GetChars` call when no rowid is found.**
- **File:** `src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs:329–394`
- **What's wrong:** The old code cached the "not found" outcome (`_rowidOrdinal = -1`), so the scan ran at most once per record. The new code only populates `RowIds` on success; when the scan fails (composite PK, expression, lone blob column), nothing is cached and the entire loop reruns on every call — including per-column `sqlite3_table_column_metadata` calls and, for integer-PK candidates, the `SELECT COUNT(*) FROM pragma_table_info(...)` command (line 375–381, since `pkColumns` is a local reset to `-1` each call).
- **Why it matters:** `GetBytes` calls `GetStream` per invocation (line 276), and chunked blob reading is a loop of `GetBytes` calls over many rows. For a composite-PK table this turns one metadata query per result set into one *per chunk per row* — a real performance regression relative to the pre-fix code.
- **Fix:** Cache the miss too, e.g. store a sentinel entry (nullable value in the dictionary, or `RowIdInfo` with `Ordinal = -1`) under the same key so the second lookup short-circuits, mirroring the old `-1` behavior per table. This also gives issue 1's assert a correct invariant to check.

**3. String cache key `$"{blobDatabaseName}_{blobTableName}"` is ambiguous — underscore names can collide and resurrect the original bug.**
- **File:** `src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs:328`
- **What's wrong:** `("main_foo", "bar")` and `("main", "foo_bar")` both produce key `"main_foo_bar"`. Database aliases (via `ATTACH`) and table names routinely contain underscores.
- **Why it matters:** On collision, the second table's blob lookup reuses the first table's rowid ordinal — precisely the wrong-rowid defect this PR is meant to resolve, now confined to an edge case, and it can *silently return the wrong row's blob* if the rowid happens to exist. Low likelihood, but silent-wrong-data severity.
- **Fix:** Key by tuple: `Dictionary<(string DbName, string TableName), ...>`. No separator, no ambiguity.

**4. Test gap: no coverage for the mixed join case (one table streams, the other falls back), which is exactly where issues 1 and 2 bite.**
- **File:** `test/Microsoft.Data.Sqlite.Tests/SqliteDataReaderTest.cs:148–181`
- **What's wrong:** The new test covers two rowid-capable tables. There is no test joining a rowid table with a composite-PK (or otherwise rowid-less) table, and no test reading the blobs in reverse order (B then A).
- **Why it matters:** The mixed case would have caught the Debug.Assert regression immediately and exercises both cache outcomes coexisting in one dictionary. The new test also never asserts stream types (`Assert.IsType<SqliteBlob>`), so it verifies data but not that streaming (vs. whole-blob caching) is actually happening for both columns.
- **Fix:** Add a variant with `PRIMARY KEY (Id1, Id2)` on one side; assert `IsType<SqliteBlob>` / `IsType<MemoryStream>` per column as the existing `GetStream_Blob_works` tests do.

#### Minor (Nice to Have)

**5. `RowIdInfo.TableName` is dead weight; the class is unnecessary.**
- **File:** `src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs:20–30`
- `TableName` is written but never read anywhere; only `Ordinal` is consumed (line 402). A `Dictionary<(string, string), int>` (or `int?` for negative caching per issue 2) replaces the whole nested class. If kept, the properties should be get-only — mutable setters on a cache entry invite accidental mutation.

**6. Style violations against repo conventions.**
- `SqliteDataRecord.cs:39` — `readonly Dictionary<string, RowIdInfo> RowIds` lacks the `private` modifier and uses PascalCase; every sibling field is `private` `_camelCase`, and the repo `.editorconfig` (lines 193–195) defines the `_camelCase`-with-underscore-prefix style for private fields. Should be `private readonly Dictionary<...> _rowIds`.
- `SqliteDataRecord.cs:17` — stray blank line added inside the namespace.
- `SqliteDataRecord.cs:328` — `string rowidkey` → `var rowIdKey` (repo uses `var`; compound-word casing).
- `SqliteDataRecord.cs:393` — `rowIdForOrdinal!=null` missing spaces around `!=`.
- `SqliteDataRecord.cs:327` — `RowIdInfo? rowIdForOrdinal = null;` is redundant; `TryGetValue(..., out var rowIdForOrdinal)` assigns it.
- Line 331: the blank line after `var pkColumns = -1L;` was dropped — pointless formatting churn in the diff.

**7. Test hygiene.**
- `SqliteDataReaderTest.cs:171` — `Console.WriteLine(...)` is the only console write in the entire sqlite test suite; it should be assertions (`Assert.Equal(1, reader.GetInt32(0)); Assert.Equal(1000, reader.GetInt32(2));`), which would also strengthen the test.
- `SqliteDataReaderTest.cs:179` — comment "`//this was failing. now should be fixed`" narrates change history; the test name and issue reference in the commit carry that context. Same for "`//get len of abuff`" (inaccurate — it reads bytes, not length) and the grammar in line 168.
- Lines 152–181: the verbatim SQL string has trailing whitespace and an indentation style unlike neighboring tests; single-line SQL as in `GetBytes_works_streaming` would match the file.

### Recommendations

1. Combine the fixes for issues 1–3: `private readonly Dictionary<(string, string), int> _rowIdOrdinals` storing `-1` for "no rowid available" restores the old negative caching, makes the null-check unnecessary, resolves the key ambiguity, and deletes the `RowIdInfo` class — a strictly smaller diff than the current one.
2. Before merge, run the full `Microsoft.Data.Sqlite.Tests` suite in **Debug** configuration specifically — that is where the assert regression manifests; a Release-only run would pass and mask it.
3. Consider a self-join test (`A a JOIN A b`) to document that same-table aliases share one cache entry by design (sqlite3 metadata reports the origin table for both aliases).

### Assessment

**Ready to merge?** No

**Reasoning:** The core per-table caching approach is correct and the regression test reproduces the issue well, but the rewritten `Debug.Assert` asserts a false invariant that numerous existing tests reach (Debug-build breakage), the loss of negative caching is a per-call performance regression for rowid-less tables, and the underscore-joined cache key can silently reproduce the original wrong-rowid bug for colliding names — all three are addressable with one small restructuring (tuple key + `-1` sentinel). [Note: findings are from static analysis; I could not compile or execute the tests in this environment because no dotnet SDK is installed.]

---

That is the complete report as returned by the reviewer. Note the reviewer's own caveat: it could not build or run the tests (no dotnet SDK in this environment), so its findings are static-analysis based, with runtime-dependent claims marked [Inference].
