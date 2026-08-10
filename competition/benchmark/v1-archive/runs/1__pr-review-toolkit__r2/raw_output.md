All five agents have completed. Nothing was posted anywhere — everything below is session-local output. Cross-agent note before the reports: two agents independently verified via upstream git/GitHub history that this PR's central defect was real — the merged commit was later **reverted upstream** (commit `101a0bd6a`, PR #32945) due to issue #32944 *"Assertion failure in SQLite following Blob column PR"*, then re-landed (commit `57dad6693`, PR #33111) with the assert commented out.

All line numbers are post-merge working-tree lines at HEAD `9e69b85`.

---

# 1. code-reviewer — Complete Findings

## Critical

**C1. `Debug.Assert(rowIdForOrdinal!=null)` is reachable-false on legitimate, already-tested fallback paths** — confidence 95 — `src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs:393`
The old code assigned `_rowidOrdinal = -1` *before* the scan loop, so `Debug.Assert(_rowidOrdinal.HasValue)` was vacuously true; `-1` was a deliberate "searched, not found" sentinel and `if (_rowidOrdinal.Value < 0)` was the supported fallback to `MemoryStream`. The new code deleted the sentinel but kept the assert, converting it into an assertion that a rowid is *always* found — false on paths the very next statement (`if (rowIdForOrdinal == null)`, line 396) explicitly handles:
- Expression/literal columns — `GetStream_works` (`SELECT x'427E5743';`, test line 373), `GetStream_works_with_text`/`_int`/`_float` (test lines 395/416/437): `blobTableName` is null, the scan skips `i == ordinal`, finds nothing → assert fires on the first existing GetStream test.
- Composite PK without rowid selected — `GetStream_works_when_composite_pk` (test line 516) expects the `MemoryStream` fallback; the assert fires first.
- WITHOUT ROWID tables; queries not selecting the table's INTEGER PK.

[Inference] On modern .NET a failed `Debug.Assert` with no debugger attached writes the failure and terminates the process — expected behavior, not executed in this environment. **Fix:** delete the assert (the null case is a designed fallback, not an invariant), or restore a negative-caching sentinel and assert only what actually holds.

## Important

**I1. Negative results no longer cached — repeated full scans and repeated SQL execution per `GetBytes` call** — confidence 90 — `SqliteDataRecord.cs:329–394`
Old: `_rowidOrdinal = -1` cached "no rowid found" for the record's lifetime. New: when the scan finds nothing, *nothing* is added to `RowIds`, so the entire scan re-runs on every call — one `sqlite3_table_column_metadata` P/Invoke per candidate column and, for composite-PK tables, a full `SELECT COUNT(*) FROM pragma_table_info($table)` command execution (`pkColumns` is a method-local reset to `-1L` each call, line 331). `GetBytes`/`GetChars` (lines 274, 288) call `GetStream` on every invocation, and chunked blob reading loops over `GetBytes` — so streaming a blob from a composite-PK table now executes an extra SQL query per chunk. **Fix:** cache the negative result per key (sentinel entry with `Ordinal = -1`, or value type `int` with `-1`).

**I2. String key `$"{blobDatabaseName}_{blobTableName}"` can collide — wrong rowid ordinal → wrong blob data** — confidence 85 — `SqliteDataRecord.cs:328`
`_` is legal in SQLite database and table names: database `db_a` + table `b` and database `db` + table `a_b` both key as `"db_a_b"`. On collision, line 402 reads the rowid from an unrelated column — `SqliteBlob` opens the correct table at the wrong row (silent wrong data) or a nonexistent row (exception). Attached databases (`ATTACH ... AS db_a`) make this realistic. **Fix:** `Dictionary<(string?, string?), ...>` keyed on the tuple — also removes a per-call string allocation.

**I3. Field `RowIds` violates the project's explicit field conventions** — confidence 92 — `SqliteDataRecord.cs:39`
Violates two `.editorconfig` rules plus the file's own style: no accessibility modifier (`dotnet_style_require_accessibility_modifiers = always`; every sibling field is explicitly `private`), and PascalCase where private fields require `_camelCase` with `_` prefix (`.editorconfig:194–195`; siblings: `_blobCache`, `_typeCache`, `_columnNameOrdinalCache`, and the replaced `_rowidOrdinal`). **Fix:** `private readonly Dictionary<...> _rowIds = ...;` and drop the stray blank line 40 splitting the field block.

**I4. Eager `Dictionary` allocation per record breaks the class's lazy-cache pattern** — confidence 80 — `SqliteDataRecord.cs:39`
Every other cache (`_blobCache`, `_typeCache`, `_columnNameOrdinalCache`, `_columnNameCache`) is nullable and allocated on first use. `RowIds` allocates for every `SqliteDataRecord` — every result set of every query — though only `GetStream` touches it. The replaced field was an allocation-free `int?`. **Fix:** `private Dictionary<...>? _rowIds;` with `_rowIds ??= new();` inside `GetStream`.

## Minor

- **M1.** Stray blank line with trailing whitespace after the namespace declaration — `SqliteDataRecord.cs:17` (diff adds a line of four spaces, confirmed via `cat -A`); violates `trim_trailing_whitespace = true`. — confidence 90
- **M2.** `Debug.Assert(rowIdForOrdinal!=null)` missing spaces around `!=` — `SqliteDataRecord.cs:393` (moot if C1 removes the assert). — confidence 90
- **M3.** Local `rowidkey` should be `rowIdKey` (camelCase per `.editorconfig`) and `string` should be `var` per the file's uniform usage — `SqliteDataRecord.cs:328`. — confidence 85
- **M4.** Redundant `RowIdInfo? rowIdForOrdinal = null;` before the `out` parameter — `SqliteDataRecord.cs:327–329`; collapse to `if (!RowIds.TryGetValue(rowIdKey, out var rowIdForOrdinal))`. — confidence 85
- **M5.** `RowIdInfo` is over-built: mutable, `internal`, and `TableName` is dead (assigned, never read anywhere; only `.Ordinal` is used at line 402) — `SqliteDataRecord.cs:20–30`. The whole class can be deleted and the cache typed `Dictionary<(string?, string?), int>` — which also solves I2 and I1's sentinel. — confidence 88
- **M6.** Style churn: removed blank line after `var pkColumns = -1L;` — `SqliteDataRecord.cs:331` (diff line 48) — unrelated whitespace-only change. — confidence 80
- **M7.** Test hygiene in `GetBytes_works_streaming_join` — `test/Microsoft.Data.Sqlite.Tests/SqliteDataReaderTest.cs:148–184`:
  - Line 171: `Console.WriteLine(...)` — the only one in the entire test project; output goes nowhere under xunit. Assert the values instead (`Assert.Equal(1, reader.GetInt32(0))`).
  - Line 179: `//this was failing. now should be fixed` narrates change history; line 173 `//get len of abuff` doesn't describe the code (it reads bytes, not length); line 170 grammar issues.
  - Lines 158, 163, 165: trailing spaces inside the verbatim SQL string; line 181: stray blank line.
  - `GetBytes` return values unchecked — `Assert.Equal(2, ...)` would strengthen the test. — confidence 85

## Pre-existing limitation (not a regression)

**Self-joins are still broken, and this keying scheme cannot fix them.** `sqlite3_column_table_name` returns the underlying table name, not the alias, so in `SELECT a1.Value, a2.Value FROM A a1 JOIN A a2 ...` both blob columns share key `main_A`; the other alias's blob is streamed with the wrong rowid — bytes from the wrong row. Old code had the same defect. [Inference] The SQLite column-metadata API exposes no alias information, so the practical options are documenting the limitation or a heuristic `GetCachedBlob` fallback.

## Good things
- The core fix is correct for the reported scenario (#32747): per-(database, table) keying is the right shape; the found-rowid path preserves the original scan logic and `SqliteBlob` construction.
- A regression test mirroring the issue repro was added, following the existing naming pattern.
- The scan-loop internals were left intact, keeping the diff reviewable.

---

# 2. silent-failure-hunter — Complete Findings

**Headline (externally verified):** the central defect predicted here actually happened upstream — commit `9e69b85b9` was reverted in `101a0bd6a` (PR #32945) because of issue #32944 ("Assertion failure in SQLite following Blob column PR"), and re-landed in `57dad6693` (PR #33111) with the assert commented out. Findings 1, 3, 4, 5 are NOT addressed by the re-land and persist in upstream `main` (verified by fetching the current upstream file).

**Finding 1 — Negative result no longer cached: full metadata scan silently re-runs on every `GetStream` call** — Medium — `SqliteDataRecord.cs:329–394` (scan), `396–399` (fallback)
When the scan finds no usable rowid (WITHOUT ROWID table, composite PK, PK not selected, single-column SELECT, expression column), nothing is written to `RowIds`. Every subsequent `GetStream` repeats the entire scan: per-column native name lookups, `sqlite3_table_column_metadata` calls (line 359), and a fresh `SELECT COUNT(*) FROM pragma_table_info(...)` execution (lines 375–381, since `pkColumns` is a per-call local). `GetBytes` (line 276) opens a new stream per invocation, so a chunked-read loop issues one hidden SQL query plus O(FieldCount) native calls *per chunk, per row*. The MemoryStream fallback itself is appropriate and pre-existing (codified by `GetStream_works_when_composite_pk`, test line 516, and `GetBytes_works`, line 96) — what broke is only the negative caching, with zero observable signal. **Fix:** cache the miss too (`RowIds[rowidkey] = rowIdForOrdinal;` after the scan, treating null/sentinel as "materialize").

**Finding 2 — `Debug.Assert(rowIdForOrdinal != null)` fires on legitimate, test-covered paths; silent in Release, process-fatal in Debug** — **Critical** (confirmed by upstream revert) — `SqliteDataRecord.cs:393`
The old assert was trivially always-true (dead); the PR "readded" it (commit message: "assert readded") against the nullable variable, where it asserts a condition the code three lines later (line 396) deliberately handles as a supported fallback. Reachable null paths, all legitimate: composite PK (`GetStream_works_when_composite_pk`, test :516 — a test that asserts the exact state the assert declares impossible), blob column with no other columns of its table selected (`GetBytes_works` :96, `GetBytes_NullBuffer`, `GetBytes_works_with_overflow`), WITHOUT ROWID tables, non-INTEGER PKs, expression columns (null db/table name → key `"_"`). In Release the assert compiles out (silent); in Debug a failed assert terminates the process [Inference — standard .NET behavior, consistent with the upstream issue title]. Historically verified impact: issue #32944 filed, full revert (#32945), re-land with assert commented out (#33111). **Fix:** delete the assert — it must never contradict an intentionally supported branch of the same method.

**Finding 3 — Ambiguous cache key `$"{db}_{table}"`: colliding pairs silently share a rowid ordinal** — Medium — `SqliteDataRecord.cs:328, 329, 402`; downstream `src/Microsoft.Data.Sqlite.Core/SqliteBlob.cs:77–85`
Database `main_x` + table `y` collides with database `main` + table `x_y` → `"main_x_y"`. On collision, `GetInt64(rowIdForOrdinal.Ordinal)` reads an unrelated column as the rowid; `SqliteBlob` passes it to `sqlite3_blob_open` (`SqliteBlob.cs:77–84`). Outcomes: (1) rowid absent → opaque `SqliteException` from `ThrowExceptionForRC` (`SqliteBlob.cs:85`) with no hint of the cause; (2) rowid present (plausible — join keys are often valid rowids) → blob opens and **returns another row's data with no error**. No guard exists: `RowIdInfo.TableName` is written (lines 354, 386) but never read (verified by grep) — dead state that could have validated the hit but doesn't; the database name isn't stored at all. **Fix:** tuple key `(string? Db, string? Table)`; delete or actually use the dead property.

**Finding 4 — Self-join: same table aliased twice shares one cache entry; blob read from the wrong row with no error at all** — High (pre-existing failure class, not a regression, but the PR structurally bakes the limitation in) — `SqliteDataRecord.cs:328–329, 345, 354/386, 402`
For `SELECT a1.ID, a1.VALUE, a2.ID, a2.VALUE FROM A a1 JOIN A a2 ON ...`, `sqlite3_column_table_name` returns `"A"` for both alias instances (the SQLite C API exposes no aliases). Both blob columns map to `"main_A"`; the first scan caches `a1.ID`'s ordinal 0; streaming `a2.VALUE` then hits the cache, `rowid = GetInt64(0)` = a1's row id, and the caller receives a1's blob while reading a2's column — no exception, no log, no assert (line 393 is bypassed on cache hit). The linear scan itself can't distinguish alias instances either, so the old code was equally broken — but the PR's own test covers only `A JOIN B`. **Recommendation:** detect the ambiguity and fall back to `MemoryStream` (correct data, no streaming) rather than guessing; document the limitation either way.

**Finding 5 — `RowIds.Add` duplicate-key throw surface** — Low — `SqliteDataRecord.cs:355, 387`
Sequentially, `Add` cannot throw (guarded by the `TryGetValue` miss, one `Add` per scan, both sites `break`; the nested `pragma_table_info` command cannot re-enter). Residual risk is out-of-contract concurrent `GetStream` calls: `ArgumentException` on double-add, or unsynchronized `Dictionary` corruption with no exception. `DbDataReader` isn't thread-safe by contract, but the failure would surface as a baffling collection exception deep in `GetBytes`. **Fix:** use the indexer (`RowIds[rowidkey] = rowIdForOrdinal;`) for idempotence.

**Finding 6 — Test "verifies" non-blob fields with `Console.WriteLine`, not assertions** — Low — `SqliteDataReaderTest.cs:170–171`
Only a thrown exception from `GetInt32` is detectable; wrong values (expected 1 and 1000) pass silently — and adjacent-column corruption is exactly the regression class this PR touches. xunit v2+ doesn't capture `Console.WriteLine` [Inference — standard xunit behavior], so as verification it's dead code. `GetBytes` return values at lines 175/179 are discarded (mitigated by the content asserts on zero-initialized buffers). The test also leaves the highest-risk scenarios uncovered: self-join (F4), a no-rowid table inside a join (F1/F2 — a test here would have caught the assert before merge, sparing the revert), chunked `GetBytes` on a no-rowid table (F1).

**Done well:** the native rc from `sqlite3_table_column_metadata` is still checked and thrown (line 369); cache lifetime is sound (fresh `SqliteDataRecord` per result set — `SqliteDataReader.cs:180` — so ordinals can't go stale, and surviving row advances is correct); the MemoryStream fallback degrades honestly rather than guessing.

| # | Severity | Location | Failure mode | Upstream status |
|---|----------|----------|--------------|-----------------|
| 1 | Medium | SqliteDataRecord.cs:329–399 | Silent per-call re-scan + hidden pragma query | Still in `main` |
| 2 | Critical | SqliteDataRecord.cs:393 | Assert contradicts supported fallback; Debug crash / Release silence | Caused revert #32945; commented out in #33111 |
| 3 | Medium | SqliteDataRecord.cs:328 | Key collision → wrong rowid → wrong data or opaque exception | Still in `main` |
| 4 | High | SqliteDataRecord.cs:328–402 | Self-join → wrong row's blob, zero diagnostics (pre-existing) | Still in `main` |
| 5 | Low | SqliteDataRecord.cs:355, 387 | `Add` throw / dictionary corruption under out-of-contract concurrency | Still in `main` |
| 6 | Low | SqliteDataReaderTest.cs:170–171 | Console.WriteLine as a "check" | Still in `main` |

---

# 3. pr-test-analyzer — Complete Findings

*(Could not build/run — no .NET SDK in this environment; runtime claims are code-derived and labeled [Inference]. Pre-PR code verified via `git show 9e69b85^`.)*

**Does the new test exercise the bug? Yes [Inference].** Pre-PR, the scan filtered by (db, table) correctly but cached its result in a single shared `int? _rowidOrdinal`. In the test, reading A.VALUE resolves A's rowid at ordinal 0; pre-PR, reading B.VALUE (test :179) would reuse ordinal 0 → rowid = A.ID = 1 → `SqliteBlob(conn, "main", "B", "VALUE", rowid: 1)`; B's only row is rowid 1000 → `sqlite3_blob_open` fails → test fails pre-PR for the right reason. Key strength: the deliberate asymmetry `A.ID = 1` vs `B.ID = 1000` (test :155–156) makes the test discriminating — had both been rowid 1, the stale ordinal would have silently opened the correct row. Distinct blob contents additionally catch a wrong-row-silent-read variant.

## Critical gaps (rated 8–10)

**3.1 — The now-fireable `Debug.Assert` breaks Debug-configuration test runs; CI runs Release so this is invisible** — 9 — `SqliteDataRecord.cs:393`
Existing tests that reach the scan-finds-nothing path and would trip the assert in a DEBUG build [Inference]: `GetStream_works` (:373 — even asserts `IsType<MemoryStream>` at :385), `GetStream_works_with_text`/`_int`/`_float` (:395/:416/:437), `GetStream_works_when_composite_pk` (:516, asserts MemoryStream at :533), `GetBytes_works` (:97), `GetBytes_NullBuffer` (:187), `GetBytes_works_with_overflow` (:206), `GetChars_works` (:261) and siblings. A failed `Debug.Assert` without a debugger terminates the process via FailFast [Unverified — documented .NET Core 3.0+ behavior, not executed here], killing the whole xunit run. Why CI passed: the pipeline builds **Release** (`azure-pipelines.yml:23–24`, `_BuildConfig: Release`) where the assert strips; the local default is **Debug** (`eng/common/build.sh:182`). No new test is needed — the existing suite already covers this, but only in a configuration CI never runs. Green CI on this PR does not demonstrate Debug-build safety.

**3.2 — The cache-hit branch is never executed by any test** — 8 — `SqliteDataRecord.cs:329`
`TryGetValue` returning `true` is the entire point of the new mechanism and no test reaches it. Checked every test that gets to the `SqliteBlob` path: `GetBytes_works_streaming` (:128), `GetStream_Blob_works` (:462, all InlineData rows), `GetStream_Blob_works_when_long_pk` (:489), `GetStream_works_when_composite_pk_and_rowid` (:544), `GetTextReader_works_streaming` (:622) — each performs exactly one call per (db, table) key. The new join test performs two calls against two *different* keys (`main_A`, `main_B`) — both misses. Tests calling `GetStream` twice on the same ordinal (:384–387) or iterating rows (:111–117) are on the uncached fallback path. A regression storing a wrong ordinal or returning a stale entry would pass the full suite. Multiple-rows/cache-reuse-across-`Read()` is also untested. **Suggested test:** 2+ rows per table, `while (reader.Read())` reading both blobs each row, plus within-row A→B→A reads — covers hit, hit-after-other-key, and cross-row ordinal reuse.

**3.3 — Self-join: the fix does not work for two instances of the same table, and no test documents it** — 8
Same key `main_A` for both aliases; reading a1.VALUE caches ordinal 0, a2.VALUE then opens the blob with a1's rowid → silently wrong bytes or a throw [Inference]. Equally broken pre-PR, but a test here would *fail today*, revealing the fix is incomplete. Deserves at minimum a skipped/quarantined test or a filed issue; rated 8 because it's silent wrong data.

## Important improvements (5–7)

**4.1 — Fallback in a join + fallback-result no longer cached** — 7 — `SqliteDataRecord.cs:329–394`
No test pins scan-once behavior, and no test combines a rowid-resolvable table with a fallback table in one join (e.g., A joined to the composite-PK table of :516, reading both blobs). Such a test would verify fallback correctness in join context, verify one table's null result doesn't pollute the other's cache, and — in a Debug run — surface gap 3.1 deterministically. `GetBytes_works` (:97) iterating 3 rows now runs the scan 3 times [Inference].

**4.2 — The test named "streaming" never asserts streaming** — 6
If rowid resolution silently broke, the `MemoryStream` fallback (:396–399) would still return correct data and the join test would pass in Release — the regression would manifest only as lost streaming plus the Debug assert. Siblings assert the type: `GetStream_Blob_works` asserts `IsType<SqliteBlob>` (:478), `GetTextReader_works_streaming` via `BaseStream` (:637). Add `Assert.IsType<SqliteBlob>(reader.GetStream(1))` / `(reader.GetStream(3))` — which also covers direct `GetStream` calls, currently exercised only through the `GetBytes` wrapper.

**4.3 — Attached databases / underscore-collision in the cache key** — 5 — `SqliteDataRecord.cs:328`
No test in the file uses `ATTACH` at all, so the database-name dimension of both the key and the scan filter (:339–343) is entirely untested. A realistic collision needs contrived names (hence 5), but the fix is trivial and testless: tuple key. A `main.T` vs `att.T` ATTACH test with different rows would cover the dimension regardless.

## Nice-to-have (1–4)
- Reverse/interleaved read order (B before A) — 3 — post-PR code is symmetric; adds little beyond 3.2's interleaving.
- `Assert.False(reader.Read())` at the end — 2 — pins the single-row expectation the byte assertions depend on.
- `RowIdInfo.TableName` (`SqliteDataRecord.cs:23`) written but never read — untestable dead code; removal is a code-review item, not coverage.
- Non-gap recorded: `NextResult` creates a fresh record (`SqliteDataReader.cs:180`), so the cache can't go stale across result sets — no test needed.

## Test-quality issues (`SqliteDataReaderTest.cs:148–184`)
1. :170–171 — `Console.WriteLine` where an assertion belongs; xunit doesn't surface Console output [Inference]; replace with `Assert.Equal(1, ...)` / `Assert.Equal(1000, ...)`. Grammar: "fields that does".
2. :173 — stale comment `//get len of abuff` — the code reads 2 bytes at offset 1, not a length.
3. :179 — `//this was failing. now should be fixed` — narrates PR history; no sibling test does this.
4. :158–165 — verbatim SQL with ~48-space indentation and trailing whitespace after `SELECT ` (:158) and `ON B.FATHER_ID=A.ID ` (:165); diverges from file conventions (:136, :523–524).
5. :181 — stray blank line; `abuff`/`bbuff` vs sibling convention `buffer` — trivial.
6. Naming/attribute pattern (`[Fact]`, `GetBytes_works_streaming_join`) matches siblings — acceptable.

## Compile/run sanity
`Assert.Equal([0x02, 0x03], abuff)` — C# 12 collection expression; `LangVersion` 12.0 (`Directory.Build.props:40`), identical usage at :120–122, :143, :482, :509 → compiles for both TFMs [Inference — not built]. Post-PR pass reasoning [Inference]: A → ordinal 0; B → ordinal 2 (`pragma_table_info('B')` → 1 PK column); rowid 1000 exists → asserted bytes match.

## Positive observations
Faithful minimal repro of #32747 that fails pre-PR for the right reason; deliberate rowid asymmetry prevents a false pass; content asserted at non-zero offset (exercising `stream.Position` through :283); self-contained in-memory DB with correct `using` discipline; the existing single-table matrix (:458–569) is strong — the gap is specifically the multi-table/caching dimension the PR introduced.

| # | Gap | Rating |
|---|-----|--------|
| 3.1 | Debug.Assert fireable by many existing tests in Debug; CI is Release-only | 9 |
| 3.2 | Cache-hit branch never executed by any test | 8 |
| 3.3 | Self-join silently reads wrong row; unfixed and untested | 8 |
| 4.1 | Fallback-in-join untested; fallback no longer cached | 7 |
| 4.2 | Join test never asserts SqliteBlob streaming type | 6 |
| 4.3 | Key-format collision; ATTACH dimension untested | 5 |
| 5 | Reverse order, end-of-rows assert | 2–3 |

---

# 4. comment-analyzer — Complete Findings

*(All usage claims verified by grep/`git show`; the rest labeled.)*

## Critical (comment is wrong or misleading)

**C1. `//get len of abuff` describes code that does something else entirely** — `SqliteDataReaderTest.cs:173`
The code below (:174–176) reads 2 bytes at offset 1 from column 1 and asserts content — it does not get a length. The "get length" form of this API is the null-buffer call (`GetBytes(1, 0, null, 0, 0)`, see `SqliteDataRecord.GetBytes` at `SqliteDataRecord.cs:278–281`), a different, untested path. **Fix:** replace with an intent comment or delete; the assertion is self-explanatory.

**C2. `Debug.Assert(rowIdForOrdinal!=null)` directly contradicts the null fallback three lines later, with no comment — and the null path is statically reachable** — `SqliteDataRecord.cs:393` vs `:396–399`
Executable-documentation contradiction: the assert claims discovery always succeeds; the next statement handles failure. The old assert was vacuously true (sentinel assigned first, verified via `git show HEAD~1`); the mechanical translation to `!= null` turned a tautology into a false claim — for an expression column (`SELECT x'427E5743';`, exercised by `GetBytes_NullBuffer` :186–203 and `GetBytes_works_with_overflow` :205+), `FieldCount == 1`, the loop skips `i == ordinal`, and the condition is false by static reading. [Inference] A DEBUG run of those existing tests would trip it (not executed here). **Fix:** remove or narrow the assert, and comment whichever survives in the file's `// NB:` idiom, explaining when the MemoryStream fallback (expression columns, WITHOUT ROWID, composite PKs) is taken. The commit message "assert readded" shows it was re-added during review without reconciling the new null semantics.

**C3. `//reading fields that does not involve blobs should be ok` — the annotated line verifies nothing** — `SqliteDataReaderTest.cs:170–171`
(a) Grammar: "fields that does" → "fields that do". (b) The line is `Console.WriteLine(...)` — asserts nothing, output discarded in xunit (not routed through `ITestOutputHelper`); reads as leftover debug scaffolding. (c) No other test in this 2,300+-line file uses `Console.WriteLine`. **Fix:** real assertions (`Assert.Equal(1, reader.GetInt32(0)); Assert.Equal(1000, reader.GetInt32(2));`) or delete both lines.

## Important (missing documentation where genuinely needed)

**I1. `RowIdInfo` has no doc comment; `TableName` is stored but never read** — `SqliteDataRecord.cs:20–30`
Nothing explains what the class represents. Verified by grep across `src/` and `test/`: `TableName` (:23) is assigned in the constructor and never read — a maintainer can't tell if it's load-bearing, future-proofing, or dead. **Fix:** brief doc comment stating purpose; document why `TableName` exists or flag for removal — an honest comment cannot currently justify it.

**I2. `RowIds` field: undocumented key format with a collision-prone underscore join** — `SqliteDataRecord.cs:39` (field), `:328` (key)
No comment states: (a) keys are per (db, table) pair; (b) the key format lives 289 lines away in `GetStream`; (c) the `_` join is ambiguous (db `"a_b"` + table `"c"` vs db `"a"` + table `"b_c"` → both `"a_b_c"`); (d) expression columns have null names → silent sentinel key `"_"`. Adjacent style: `RowIds` breaks the `private` + `_camelCase` convention (`_blobCache`, `_typeCache`, `_columnNameOrdinalCache`). **Fix:** comment key semantics and lifetime (per `SqliteDataRecord` = per executed statement); a tuple key would remove half the needed comment.

**I3. The rowid-discovery loop and the silent removal of negative-result caching** — `SqliteDataRecord.cs:329–394`
The old code cached the negative result once per reader; the new code re-runs the full O(FieldCount) scan on every miss — including per-column `sqlite3_table_column_metadata` and the `pragma_table_info` COUNT subquery (:377; `pkColumns` resets each call). Nothing indicates whether the behavior change was deliberate. The 40-line discovery algorithm (explicit `rowid` alias, else single-INTEGER-PK detection) has no explanatory comment, despite the file's `// NB:` idiom (lines 111, 129, 177, 294, 308, 485). **Fix:** header comment above :329 describing algorithm + caching contract; if the loss is intentional, say why — if not, fix it.

**I4. New test has no link to the issue it regression-tests, contrary to file convention** — `SqliteDataReaderTest.cs:148–149`
The file's idiom is `[Fact] // Issue #29744` (:2264), `[Fact] // Issue #30765` (:2321). The new test encodes provenance in a change-history comment (:179) and doesn't state the scenario it guards. **Fix:** `[Fact] // Issue #32747`, and optionally one sentence: reading a BLOB from the second joined table must resolve that table's own rowid.

## Recommended removals

**R1. `//this was failing. now should be fixed`** — `SqliteDataReaderTest.cs:179` — pure change-history narration; meaningless post-merge; hedges ("should be") about the very thing the `Assert.Equal` on :180 proves. Replace with the `[Fact] // Issue #32747` idiom.

**R2. Whitespace-only line inside the namespace** — `SqliteDataRecord.cs:17` — four spaces of trailing whitespace (verified with `cat -A`), plus the added blank line :40 splitting the field block. Both diff noise; remove.

## Positive findings
- Pre-existing `// NB:` comments (`SqliteDataRecord.cs:111, 129, 177, 308, 485`) remain accurate and model the terse "why" idiom the new code should have followed.
- Stale-comment sweep clean: no comment anywhere still references `_rowidOrdinal` or a singular "rowid ordinal" — the staleness problem is entirely *missing* documentation for changed semantics, not leftover text.

**Priority:** C2 → C1 → I3 → C3+R1+I4 → I1+I2 → R2.

---

# 5. type-design-analyzer — Complete Findings

**Headline (verified against upstream history):** the central type-design flaw — losing the old `-1` sentinel's "scanned but not found" state while relocating a `Debug.Assert` that now asserts the state the next statement handles — is not theoretical: upstream reverted this PR in `101a0bd6a` (PR #32945, issue #32944) and re-landed in `57dad6693` (PR #33111) with the assert commented out but every other issue below intact.

## Type: `RowIdInfo` (`SqliteDataRecord.cs:20–30`)

**Invariants identified:** (1) `Ordinal` must be a valid column index (`0 <= Ordinal < FieldCount`) of the keyed table's rowid/single-INTEGER-PK column; (2) entries are meaningful only for one `SqliteDataRecord`/prepared statement; (3) conceptually immutable once computed; (4) unrepresented third state — *scanned, nothing found* — which the old code encoded as `-1` and this design cannot express.

**Ratings:**
- **Encapsulation: 3/10** — public `get; set;` on both properties lets any holder mutate `Ordinal` after caching, silently corrupting the cache; `internal` exposes it assembly-wide (plus `InternalsVisibleTo` test assemblies) though consumed by exactly one method. Redeeming: nested inside an internal class; backing dictionary is (implicitly) private.
- **Invariant Expression: 2/10** — conceptually immutable value expressed as a mutable POCO; nothing says `Ordinal` is a column index or ties it to its statement; absence is smuggled through `RowIdInfo?` null at :396, conflating "cache miss" with "known not to exist".
- **Invariant Usefulness: 3/10** — the per-(db, table) caching invariant is the right fix for #32747 (new test passes), but the carrier adds nothing over an `int`: **`TableName` is write-only dead code** (verified: the only member read anywhere is `.Ordinal` at :402; a repo-wide `.TableName` search finds only unrelated `DataTable.TableName` asserts in `SqliteConnectionTest.cs`), duplicating the dictionary key. And the design **lost negative caching** — every `GetStream`/`GetBytes`/`GetChars` (:274–286, :288–314 route through GetStream) on a no-rowid column re-runs the O(FieldCount) scan including re-executing the `pragma_table_info` COUNT (:377; `pkColumns` reset per call at :331). Reachable via existing test shapes (`GetStream_works_when_composite_pk` :516, `GetStream_works` :373).
- **Invariant Enforcement: 2/10** — no construction-time validation (negative `Ordinal` accepted); full mutability; the one runtime check, `Debug.Assert(rowIdForOrdinal!=null)` (:393), asserts a condition :396 immediately handles as legitimate. In the old representation the equivalent assert was trivially true; relocating it without the sentinel made it fire on any no-rowid blob read in Debug — the exact failure reported as #32944. A textbook case of a type change breaking an invariant check whose truth depended on the old representation.

**Nullability of `TableName`:** the file has no `#nullable` directive (:1–13); `src/Directory.Build.props:8` sets `<Nullable>enable</Nullable>` and `Directory.Build.props:39` sets `TreatWarningsAsErrors`. `TableName` is non-nullable `string` but assigned from `sqlite3_column_table_name(...).utf8_to_string()`, which this same file treats as nullable elsewhere (`typeName != null` :183–184, `dataTypeName == null` :502) — SQLite returns NULL table names for expression columns. [Inference] It compiles clean because SQLitePCLRaw 2.1.7 is nullable-oblivious; could not build to confirm (no SDK). Either way the `string` annotation is a claim the type doesn't enforce and the underlying API doesn't honor.

**Repo precedent:** the codebase strongly prefers immutable value carriers for exactly this shape — including the exact analog, a private nested `record struct` dictionary-adjacent carrier: `src/EFCore.Relational/Update/ModificationCommand.cs:246` (`private record struct JsonPartialUpdatePathEntry(string PropertyName, int? Ordinal, ...)`); same project: `src/Microsoft.Data.Sqlite.Core/Utilities/SharedStopwatch.cs:10` (`internal readonly struct`); plus `readonly struct CacheKey` (ValueGeneratorCache.cs:46), `readonly record struct ColumnValueSetter` (ColumnValueSetter.cs:18), `readonly struct CommandCacheKey` (RelationalCommandCache.cs:106), etc. A mutable class with settable auto-properties has no precedent for this role.

## Stringly-typed composite key `$"{blobDatabaseName}_{blobTableName}"` (:328) — Invariant Expression: 2/10
Must be injective over (database, table); underscore concatenation is not: `ATTACH 'x.db' AS db_one` + table `x` vs database `db` + table `one_x` → both `"db_one_x"`. On collision the second lookup silently reuses the first entry's `Ordinal` (:402) — right table, wrong rowid → wrong row's blob or a "no such rowid" `SqliteException`. Expression columns (both names NULL) all map to key `"_"` — currently harmless only because the not-found result is never cached, i.e., **one bug is masked by another**. `Dictionary<(string?, string?), ...>` gets injectivity, structural equality, and hashing free, zero key allocation.

## Naming and access — field `RowIds` (:39) — consistency/encapsulation-signaling: 2/10
Every sibling private field follows `private _camelCase` (:32–42: `_connection`, `_addChanges`, `_blobCache`, `_typeCache`, `_columnNameOrdinalCache`, `_columnNameCache`, `_stepped`, `_alreadyThrown`, `_alreadyAddedChanges`). `RowIds` deviates threefold: PascalCase (reads as a public property at call sites :329, :355, :387), no explicit access modifier, no underscore prefix. Conventional name: `_rowIdOrdinals` (mirroring `_columnNameOrdinalCache`). Related nits: stray blank line :17, assert spacing :393, local `rowidkey` :328.

## Encapsulation scope and lifetime — 6/10 (strongest aspect)
- Nesting: right — implementation detail of one method.
- Visibility: one notch too wide — `internal` with no consumer outside `GetStream`; `private` states the true scope (matching the `JsonPartialUpdatePathEntry` precedent).
- Lifetime: correct — created per result set in `SqliteDataReader.NextResult` (`SqliteDataReader.cs:180`), discarded on the next result set (:142–146); a prepared statement's column↔table mapping is fixed, so caching per (db, table) for the record's lifetime is sound, including across `Read()` advances. Single-threaded `Add`-after-miss matches the class's existing non-thread-safe contract.

## Recommended improved designs

**Option A — minimal, deletes the type entirely, restores negative caching (recommended):**
```csharp
private Dictionary<(string? Database, string? Table), int>? _rowIdOrdinals;

// in GetStream:
var key = (blobDatabaseName, blobTableName);
_rowIdOrdinals ??= new();
if (!_rowIdOrdinals.TryGetValue(key, out var rowIdOrdinal))
{
    rowIdOrdinal = -1;                    // sentinel restored: not-found is cached too
    var pkColumns = -1L;
    for (var i = 0; i < FieldCount; i++)
    {
        // ... existing scan; on match: rowIdOrdinal = i; break;
    }
    _rowIdOrdinals[key] = rowIdOrdinal;   // single write point, both outcomes
}

if (rowIdOrdinal < 0)
{
    return new MemoryStream(GetCachedBlob(ordinal), false);
}
// ...
var rowid = GetInt64(rowIdOrdinal);
```
Injective tuple key, dead `TableName` gone, negative caching restored, lazy allocation like `_columnNameOrdinalCache` (:141), no assert needed — invalid states aren't representable.

**Option B — encode absence in the value type:** `Dictionary<(string?, string?), int?>?` — missing key = not scanned; `null` value = scanned, no rowid (MemoryStream); `i` = found. Three states, each distinct; nothing left to assert — precisely what the upstream redo's replacement comment concedes at the same spot in `57dad6693`.

**Option C — if a named carrier is genuinely wanted later:** `private readonly record struct RowIdInfo(int Ordinal);` — add members only when read, matching the `JsonPartialUpdatePathEntry` precedent.

## Ratings summary

| Axis | Score | Notes |
|---|---|---|
| Encapsulation | 3/10 | Mutable publics; `internal` wider than needed; nesting/lifetime right (scope itself 6/10) |
| Invariant Expression | 2/10 | Mutable POCO; dead `TableName`; "not found" unrepresentable; stringly key 2/10 |
| Invariant Usefulness | 3/10 | Caching concept fixed #32747; type added nothing over `int`, dropped negative caching |
| Invariant Enforcement | 2/10 | No validation; nullable-oblivious `string` claim; the sole check caused issue #32944 and the revert |

---

# Consolidated PR Review Summary

## Critical (1)
- **[silent-failure-hunter, code-reviewer, comment-analyzer, type-design-analyzer, pr-test-analyzer — unanimous]** `Debug.Assert(rowIdForOrdinal!=null)` contradicts the supported null fallback three lines below and fires on legitimate paths already exercised by existing tests (expression columns, composite PKs, WITHOUT ROWID) in Debug builds — invisible to Release-only CI. `SqliteDataRecord.cs:393`. **Externally verified:** this caused upstream issue #32944, a full revert (PR #32945), and a re-land (PR #33111) with the assert commented out.

## Important (5)
- **Negative-result caching lost** — every `GetStream`/`GetBytes`/`GetChars` on a no-rowid table re-runs the full scan including a hidden `pragma_table_info` SQL query per chunked read. `SqliteDataRecord.cs:329–394`. Still present in upstream `main`. [4 agents]
- **Collision-prone string key** `$"{db}_{table}"` — non-injective; collision silently yields the wrong rowid → wrong blob data or opaque exception; tuple key fixes it for free. `SqliteDataRecord.cs:328`. [4 agents]
- **Self-join silently returns the wrong row's blob** — pre-existing failure class the per-table-name cache structurally bakes in; untested and undocumented. `SqliteDataRecord.cs:328–402`. [3 agents]
- **Cache-hit branch never executed by any test** — the core new mechanism has zero coverage; multiple-row cache reuse untested. `SqliteDataRecord.cs:329`. [pr-test-analyzer]
- **`RowIdInfo` type design** — mutable POCO with a dead `TableName` property, contrary to repo precedent (`readonly record struct`); reduces to `Dictionary<(string?, string?), int>`. `SqliteDataRecord.cs:20–30`. [3 agents]

## Suggestions
- Field `RowIds` → `private readonly ... _rowIds` (naming + accessibility + lazy allocation per `.editorconfig` and sibling fields), `SqliteDataRecord.cs:39`.
- Test: replace `Console.WriteLine` with assertions (:170–171), delete stale/history comments (:173, :179), add `[Fact] // Issue #32747`, assert `IsType<SqliteBlob>` for streaming, check `GetBytes` return values, clean trailing whitespace in the SQL literal.
- Whitespace noise: `SqliteDataRecord.cs:17` (trailing-whitespace line), :40, :331.
- Use the indexer instead of `Add` for idempotence (:355, :387).

## Strengths (agreed across agents)
- The per-(database, table) caching **concept** is the correct fix for #32747, and the found-rowid path preserves the original scan logic.
- The regression test is a faithful minimal repro that fails pre-PR for the right reason; the deliberate `A.ID=1`/`B.ID=1000` asymmetry prevents a false pass.
- Cache lifetime is sound (fresh record per result set, `SqliteDataReader.cs:180`); native return codes remain checked; the MemoryStream fallback degrades honestly.

## Recommended action (were this PR still open)
1. Delete the assert at :393 (upstream ultimately did).
2. Replace `RowIdInfo` + string key with a lazily-allocated `Dictionary<(string?, string?), int>?` using a `-1` sentinel — fixes negative caching, key collisions, dead code, and naming in one change (type-design-analyzer's Option A).
3. Extend the test: multi-row cache-hit coverage, a fallback-table-in-join case (would have caught the assert pre-merge), and assertions instead of `Console.WriteLine`.
4. File/document the self-join limitation.
