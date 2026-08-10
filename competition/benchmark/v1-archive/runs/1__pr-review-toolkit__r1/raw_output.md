All five agents completed. Nothing was posted to GitHub — this is a read-only report. Line numbers are post-merge positions in the local checkout (HEAD `9e69b85`, which contains PR #32770 merged). One note on evidence quality: the silent-failure-hunter compiled the merged sources and ran actual repros (outputs quoted); the other agents' behavioral claims are static analysis, labeled as such where they said so.

---

# PR #32770 — "Microsoft.Data.Sqlite.Core issue with multiple Blob colums" (francopettinari, MERGED)

**Change:** `SqliteDataRecord.GetStream`'s single cached `_rowidOrdinal` replaced by a per-`(database, table)` `Dictionary<string, RowIdInfo> RowIds` keyed by `$"{blobDatabaseName}_{blobTableName}"`, so BLOB streaming works across multiple tables in a JOIN. One new test: `GetBytes_works_streaming_join`.

---

## 1. code-reviewer

### Critical

**1. Inverted `Debug.Assert` now fires on every legitimate no-rowid fallback** — `src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs:393`
`Debug.Assert(rowIdForOrdinal!=null)`. The old assert `Debug.Assert(_rowidOrdinal.HasValue)` was vacuously true (`-1` was assigned before the scan). The new assert claims a rowid is *always* found — but the very next statement (`if (rowIdForOrdinal == null)` at line 396) is a supported fallback branch for exactly the case where none exists: expression columns, WITHOUT ROWID / composite-PK tables, projections without the blob table's rowid. The assert and the fallback directly contradict each other. Pre-existing tests reach this path: `GetStream_works` (test file :379, `SELECT x'427E5743';`), `GetBytes_works` (:97), `GetStream_works_when_composite_pk` (:516, which explicitly asserts the `MemoryStream` fallback). [Code-path analysis, not executed by this agent:] a failed `Debug.Assert` with no debugger terminates the process in Debug builds. **Fix:** delete the assert.

### Important

**2. "No rowid found" no longer cached — full rescan on every call** — `SqliteDataRecord.cs:329-394`
Old code cached the `-1` sentinel once per record. New code only inserts on success (:355, :387); on failure the entire scan re-runs on *every* `GetStream` call — up to `FieldCount` × 3 native string conversions plus `sqlite3_table_column_metadata` P/Invokes, and for composite-INTEGER-PK tables a full `SELECT COUNT(*) FROM pragma_table_info($table)` execution (:377) per call. `GetBytes`/`GetChars` call `GetStream` per invocation, so a chunked read of a large blob runs a query per chunk, per row. Correct-but-wasteful — a real performance regression on the fallback path. **Fix:** cache the negative outcome too (e.g. store `-1` or a sentinel entry).

**3. Composite string key `$"{db}_{table}"` is collision-prone** — `SqliteDataRecord.cs:328`
`_` is legal in both ATTACH aliases and table names, so the key is not injective: database `db_a` + table `b` and database `db` + table `a_b` both produce `"db_a_b"`. On collision, a cached ordinal from one table is used to read the rowid for a different table — silently wrong row's blob or a spurious "no such rowid" error. **Fix:** key by `(string?, string?)` value tuple, which also avoids the interpolated-string allocation on every `GetStream` call (including cache hits) and handles null names from expression columns.

**4. `RowIds` field violates repo field conventions** — `SqliteDataRecord.cs:39`
Violates `.editorconfig` `dotnet_style_require_accessibility_modifiers = always` (no `private`) and the `_camelCase` private-field naming rule every sibling follows (`_connection`, `_blobCache`, `_stepped`, …). Should be `private readonly Dictionary<...> _rowIds = new();`. Stray blank line at :40 splits the field block.

**5. `RowIdInfo` is over-built** — `SqliteDataRecord.cs:20-30`
`TableName` (:23) is written but never read — dead data, and redundant by construction (the scan filters `tableName != blobTableName → continue` at :346, so it always equals the key's table component). Properties are `get; set;` but only assigned in the constructor. `internal` on a nested type of an internal class grants nothing over `private sealed`. With `TableName` deleted, the class reduces to a single `int`; `Dictionary<(string?, string?), int>` resolves findings 2, 3, and 5 at once.

**6. `Console.WriteLine` in the test instead of assertions** — `test/Microsoft.Data.Sqlite.Tests/SqliteDataReaderTest.cs:171`
The only `Console.WriteLine` in the entire test project; under xunit v2 it isn't associated with the test (that needs `ITestOutputHelper`), so it verifies nothing. Should be `Assert.Equal(1, reader.GetInt32(0)); Assert.Equal(1000, reader.GetInt32(2));`.

### Minor

**7.** `SqliteDataRecord.cs:393` — `rowIdForOrdinal!=null` missing spaces around `!=` (`csharp_space_around_binary_operators = before_and_after`). Moot if the assert is deleted.
**8.** `SqliteDataRecord.cs:17` — stray whitespace-only line (four spaces) added after the namespace declaration; `.editorconfig` sets `trim_trailing_whitespace = true`. (Similar whitespace at :448 is pre-existing per `git blame`.) Also removed the blank line after `var pkColumns = -1L;` (:331) — formatting churn.
**9.** `SqliteDataRecord.cs:327-329` — redundant pre-initialization of `rowIdForOrdinal` before the `out` argument (`csharp_style_inlined_variable_declaration` prefers `out var`); `string rowidkey` should be `var` and named `rowIdKey`.
**10.** `SqliteDataReaderTest.cs:170,173,179` — comments lack space after `//`; "fields that does" grammar; `//get len of abuff` is inaccurate (reads 2 bytes at offset 1, gets no length); `//this was failing. now should be fixed` narrates change history that belongs in the commit/PR.
**11.** `SqliteDataReaderTest.cs:158,163,165,181` — trailing whitespace inside the verbatim SQL literal; stray blank line before closing brace; deeply indented multi-line SQL diverges from the file's compact single-line convention.
**12.** `SqliteDataReaderTest.cs:149-184` — `GetBytes` return values discarded; only A-then-B order exercised; no JOIN + fallback-table combination (the case that would have exposed findings 1 and 2).

### Positive observations
- Per-(database, table) caching is the correct granularity, and statement-lifetime cache scope is sound (prepared-statement column metadata is stable across rows).
- The fix also quietly resolves the converse bug: previously a first-examined blob with no reachable rowid poisoned (`-1`) all other blob columns into the in-memory fallback.
- The nontrivial discovery logic (rowid origin-name match, INTEGER-PK alias, composite-PK count check) was preserved unchanged — small risk surface.
- The regression test faithfully reproduces the reported scenario and asserts actual bytes from both tables.
- Pre-existing limitation (not regressed): self-joins map both aliases to one cache key (`sqlite3_column_table_name` returns the real table name), so both blobs resolve against whichever alias's rowid was found first — untested and undocumented, likely unfixable at this layer.

**Highest-value combined fix:** `Dictionary<(string?, string?), int>`, store `-1` on failure, drop the assert, delete `RowIdInfo` — addresses findings 1, 2, 3, 5 together.

---

## 2. silent-failure-hunter

*(Findings 1–3 verified empirically: the agent compiled the merged `Microsoft.Data.Sqlite.Core` sources into a scratch net10.0 project and ran repros; outputs quoted verbatim.)*

**Finding 1 — CRITICAL (verified): `Debug.Assert` fires on every legitimate fallback and terminates the process in Debug builds** — `SqliteDataRecord.cs:393`
Ran the exact query shape of the repo's own `GetStream_works_when_composite_pk` against a Debug build of the merged sources:
```
about to call GetStream on composite-pk blob (fallback path)...
Process terminated.
Assertion failed.
rowIdForOrdinal!=null
   at Microsoft.Data.Sqlite.SqliteDataRecord.GetStream(Int32 ordinal) in .../SqliteDataRecord.cs:line 393
EXIT CODE: 134
```
Reachable triggers are ordinary queries: `SELECT Value FROM Test` (blob without PK projected — existing test `GetBytes_works`, test file :97), any expression column (`SELECT x'...'`, `SELECT 'têst'`, `SELECT 12` — hit by ~11 existing tests including `GetChars_works` :261, `GetStream_works` :373, `GetStream_works_with_text` :395, `GetStream_works_with_int` :416), composite PK (`GetStream_works_when_composite_pk` :516). In Release the assert is stripped and the null routes into the fallback — Debug and Release now diverge: crash vs. silent degradation. [Inference] dotnet/efcore CI validating in Debug would fail; the assert firing on those query shapes is verified, the CI configuration is not.

**Finding 2 — CRITICAL (verified): key collision returns wrong-row BLOB data silently, or throws a spurious SqliteException** — `SqliteDataRecord.cs:328-329, 355, 387`
The scan itself compares database and table per column, but the *cache lookup* at :329 has no such protection. Repro with ATTACHed DB `main_b` containing table `c`, and main DB containing table `b_c` (both key to `main_b_c`):
```
bc.Data = AAAAAAAA (expect AAAAAAAA)
c.Data  = 11111111 (expect 22222222)          <- SILENT WRONG DATA
```
Reversed read order instead throws: `SqliteException: SQLite Error 1: 'no such rowid: 2'` — a hard error on a valid query whose message mentions neither collision nor cause, and which depends on column read order. Hits Release builds identically. The stored `RowIdInfo.TableName` (:23) could have validated cache hits but is never read.
On Q3 (can `Add` throw): single-threaded, no — each `Add` is reachable only after a `TryGetValue` miss in the same invocation and is followed by `break`. Under multithreaded misuse (out of DbDataReader's contract) `Dictionary.Add` can throw `ArgumentException` or corrupt state where the old `int?` raced benignly — new failure mode, Low severity given the contract.

**Finding 3 — HIGH (verified): negative results not cached — O(FieldCount) scan + SQL pragma query per GetStream call** — `SqliteDataRecord.cs:329-394`, `:274-286`
Release build, 64 KB blob read in 4 KB chunks (16,000 `GetBytes` calls), 3-column select:
```
resolvable rowid (positive cache hit):  44 ms for 16000 GetBytes calls
unresolvable rowid (no negative cache): 136 ms for 16000 GetBytes calls
```
3× slowdown on a trivially narrow select; grows with column count; composite-PK adds one SQL statement execution per `GetBytes` call. Invisible to users — no error, no log; nobody will trace "SQLite reads got slow after upgrading" to this line.

**Finding 4 — MEDIUM: the new test cannot distinguish true streaming from the buffered fallback** — `SqliteDataReaderTest.cs:148-184`
If `GetStream(3)` took the `MemoryStream(GetCachedBlob(3))` fallback, the bytes would be identical (`[0x06, 0x07]`) and the test would pass. It does catch the *original* bug (old code → `no such rowid`), but a future regression to buffered mode sails through green. Sibling tests show the established pattern: `Assert.IsType<SqliteBlob>` (:478, :505, :561) / `Assert.IsType<MemoryStream>` (:385, :533). Also: despite "works_streaming" in the name, the test never obtains a stream. Missing: reversed read order, second blob in the same table, JOIN with one unresolvable table (would have exposed Finding 1).

**Finding 5 — LOW: hygiene** — `SqliteDataReaderTest.cs:171` (Console.WriteLine — a wrong integer read passes silently), `:173`/`:179` (inaccurate + change-history comments), `SqliteDataRecord.cs:23` (dead, mutable `TableName`), `:39` (naming/modifier convention), `:17` (stray whitespace line), `:393` (operator spacing).

**Clean categories (explicitly checked):**
- *Swallowed exceptions:* clean. No catch blocks added; `sqlite3_table_column_metadata` rc checked and thrown (:369); `ExecuteScalar` (:380) propagates. The file's only catch (:427-437 in `Read()`) is untouched, rethrows immediately, and uses `_alreadyThrown` solely so `Dispose()` (:455-461) doesn't mask the original exception — correct error preservation.
- *Wrong-table rowid within a single scan:* clean — the loop compares database (:339-343) **and** table (:345-349) before considering a column; contamination exists only via the cache-key collision.
- *Duplicate-key `Add` single-threaded:* clean.
- *Fallback classification:* the buffered `MemoryStream` fallback itself is pre-existing behavior preserved (old `< 0` branch did the same; `GetCachedBlob` :480-498 buffers once per row, cache cleared per `Read()` :439-442). The PR actually *reduces* fallback frequency (no more global `-1` poisoning). What's new and degraded: the repeated scan (Finding 3) and the Debug crash (Finding 1) in front of it.

---

## 3. pr-test-analyzer

*(No .NET SDK in that agent's environment — no test executed; .NET-side claims are traced from source and labeled [Inference]. SQLite C-API semantics — blob_open with stale rowid → "no such rowid"; with valid-but-wrong rowid → silently wrong bytes — verified against SQLite 3.46.1.)*

**Coverage rating: 5/10.** The reported bug has a genuine fails-before/passes-after regression test, but for a change whose essence is *introducing a keyed cache*, no test reads from the cache, no test exercises the database half of the key, two traced wrong-data scenarios remain untested (and would fail today), and the assertion style cannot detect a fallback regression.

1. **[Confirmed by trace] The new test does exercise the fixed path** — `GetBytes` routes through `GetStream` (SqliteDataReader.cs:516-521 → SqliteDataRecord.cs:274-286); both `A.VALUE` and `B.VALUE` resolve via the INTEGER-PK branch (:359-390) and return `SqliteBlob`. Pre-fix, the stale ordinal produced "no such rowid: 1". Note `B.ID = 1000` (test :156) is **load-bearing**: had B.ID been 1, the stale rowid would coincidentally resolve and the broken code would pass — documented nowhere.
2. **Content-only assertions; a silent fall-back-to-MemoryStream regression passes** (criticality 7) — `SqliteDataReaderTest.cs:174-180`; the file's own `Assert.IsType` convention (:478, :505, :561, :385, :533) was skipped.
3. **The dictionary cache-hit branch (`TryGetValue` → true) is executed by zero tests** (criticality 8) — `SqliteDataRecord.cs:329`. Enumerated every streaming-API caller in the test project: the new test performs two *misses* (`main_A`, `main_B`), never a hit; `GetStream_works` calls twice but on an expression column (nothing cached); everything else calls once per (db, table). The populate side runs; the read side never does — a wrong stored `Ordinal` would be invisible. Minimal test: one table with two BLOB columns, read both.
4. **Self-join silently returns the wrong row's blob — missing test would FAIL today** (criticality 8) — `sqlite3_column_table_name` reports origin table "A" for both aliases → shared key `main_A` → second alias's blob opened with the first alias's rowid → valid rowid, wrong row, no error (SQLite-side verified). Directly adjacent to the fixed scenario; the per-(db, table) key cannot represent per-alias instances. The test doubles as a defect report — can't be added green without further code change.
5. **Database-name component of the key: zero coverage** (criticality 7) — no `ATTACH` anywhere in the test project (grep). The key's db component (:328) and the scan's database filter (:339-343) exist precisely for same-named tables across attached databases — never exercised.
6. **Key delimiter collision untested** (criticality 6) — ("db_x", "T") vs ("db", "x_T") conflate; wrong data today; pin with a collision-shaped test once the key becomes a tuple.
7. **Fallback path lost its caching — untested** (criticality 5) — no test calls the streaming API twice on a composite-PK/WITHOUT ROWID table (`GetStream_works_when_composite_pk` :516 calls once); a repeated-call test would pin behavior now that the `-1` sentinel is gone.
8. **Test quality** — `:171` Console.WriteLine (xUnit doesn't capture Console; assert instead — which would also encode the load-bearing 1000); `:175`/`:179` `GetBytes` return discarded (`GetBytes_works_with_overflow` :218-219 shows the convention); `:173` inaccurate comment; `:179` change-history comment (better: "B's blob must use B's rowid, not the rowid cached for A"); trailing whitespace in SQL (:158, :165), missing spaces after commas in DDL (:155-156); naming and `using`/`:memory:` cleanup are fine.
9. **Positives** — hard-failing (exception, not subtly-wrong-bytes) regression test; distinct blob contents catch wrong-table reads at the same offset; the surrounding suite still covers single-table populate branches well.

**Prioritized missing tests:**
1. (8) Two blob columns in one table, both read — only way to hit `TryGetValue` true.
2. (8) Self-join over two different rows — exposes silent wrong-row data; file as defect + test.
3. (7) `GetStream`-based join test with `Assert.IsType<SqliteBlob>` on both streams.
4. (7) JOIN across `main` and an ATTACHed DB with same-named tables.
5. (6) Multi-row join iteration — cache reuse across `Read()` calls.
6. (6) Underscore key-collision shape.
7. (5) Repeated `GetStream` on a composite-PK table (both calls succeed, `MemoryStream`).
8. (4) WITHOUT ROWID table blob read.
9. (3) `SELECT rowid AS r, ...` aliased-rowid projection.

---

## 4. comment-analyzer

**Summary verdict: poor.** Every one of the three comments the PR adds has a defect; meanwhile the PR replaced a compact implicit contract with a materially subtler one and documented none of it.

### Critical
1. **`SqliteDataReaderTest.cs:173` — `//get len of abuff` — describes something the code does not do.** The lines allocate a 2-byte buffer and copy bytes into it; nothing obtains a length. [Inference] Leftover from a draft that passed a `null` buffer (which returns length — see SqliteDataRecord.cs:278-281). Fix: delete, or state what matters: `// Stream 2 bytes of A.VALUE`.
2. **`SqliteDataRecord.cs:393` — the assert is executable documentation making a false claim.** The invariant it asserts is contradicted by the handled, test-covered null branch at :396 (`GetStream_works_when_composite_pk`, test :516, asserts the `MemoryStream` fallback). Fix: remove, or replace with `// null here means no usable rowid — fall through to the cached-blob path`. [Verified by static reading; Debug test run not executed by this agent.]
3. **`SqliteDataRecord.cs:328` — missing comment on a collision-hazard key.** The `$"{db}_{table}"` format and its non-injectivity are documented nowhere; the reader can't tell whether it was considered. Preferred fix is a tuple key; if the string stays, it needs at minimum: `// Key is "{database}_{table}"; "_" is legal in identifiers, so distinct pairs can collide`.

### Improvement opportunities
4. **`SqliteDataRecord.cs:39` — missing comment: the cache's semantics changed subtly.** Old contract (null / -1 / ≥0) was implicit but compact. New contract — only successes cached; failures rescan every call *including* the `pragma_table_info` query at :377 — is undocumented and undiscoverable, and whether the regression is intentional can't be determined. Suggested: `// Per-(database, table) ordinal of the rowid column in this result set. Only found rowids are cached; a table with no usable rowid is rescanned on every GetStream call.` — better, cache the negative result and document that.
5. **`SqliteDataReaderTest.cs:170` — grammar ("fields that does"), style (`//lowercase`, no space — the codebase uses `// Sentence case`, e.g. test :1288, :1474; src :294, :308), and the code doesn't demonstrate the claim** (a Console.WriteLine with no assertion; xunit doesn't surface it). Fix: assert and reword: `// Non-blob columns read normally alongside blob streaming`.
6. **`SqliteDataRecord.cs:20-30` — `RowIdInfo.TableName` written (:354, :386) and never read anywhere (grep-verified), and redundant by construction (:346 guarantees it equals the key's table).** No XML docs is consistent with local convention for internals — the problem is dead, unexplained state. Preferred fix: remove; the type collapses to an `int`.

### Recommended removals / rewrites
7. **`SqliteDataReaderTest.cs:179` — `//this was failing. now should be fixed` — change-history narration that rots immediately.** The repo's convention for fixed-bug provenance is an issue reference on the attribute: `[Fact] // Issue #29744` (test :2264), `[Fact] // Issue #30765` (:2321). Fix: delete; put `[Fact] // Issue #NNNNN` on :148 (the agent could not verify the linked issue number offline) and state the *why*: `// Second blob column from a different table in a join; the rowid ordinal cached for table A must not be reused for table B`.

### Rot check
8. **No existing comments rotted — there were none.** Pre-merge `GetStream` contained zero comments (verified against `HEAD~1`) and still does. Nearby comments (`// TODO: Consider using a stackalloc buffer...` :294, `// NB: Message is provided by the framework` :308) are in `GetChars`, unaffected and accurate. The inverse-of-rot problem: a ~90-line two-phase discovery-and-cache algorithm got *more* subtle in this PR while gaining no explanatory comments — findings 3, 4, 6 mark the decision points that need them.

---

## 5. type-design-analyzer

Credit first: the *conceptual* change is right — the cached invariant ("which ordinal holds this blob's rowid") is genuinely per (database, table), and keying on that pair is the correct fix. The findings are about how poorly the types express that correct idea.

### `RowIdInfo` (`SqliteDataRecord.cs:20-30`)
- **Invariants:** intended `0 <= Ordinal < FieldCount` for a column reading the keyed table's rowid — expressed and enforced nowhere. `TableName` provably always equals the key's table component (loop guard :346) — 100% redundant, never read (grep-verified), and creates ambiguity about which table string is authoritative. Unintended states (negative ordinal, unrelated table, post-hoc mutation) are all representable.
1. **Mutable cache entry with two initialization paths** (:22-23 vs :25-29) — public setters with zero call sites; any reference holder can corrupt the shared cache (`entry.Ordinal = 7;` compiles). Write-once cache values have exactly one correct shape: immutable.
2. **The type is unnecessary** — only `Ordinal` is consumed (single read, :402). A one-used-field wrapper around an `int` plus a dead string is not a domain concept; `Dictionary<..., int>` (or a named tuple element) says the same with less surface.
3. **Class vs struct** — a heap allocation per entry to carry semantically one `int`, on the blob-streaming hot path (`GetBytes` → `GetStream` per chunk, :276). Codebase precedent for value shapes: `Utilities/SharedStopwatch.cs:10` (`internal readonly struct`), `SqliteConnection.cs:963` (ValueTuple dictionary key).
4. **Accessibility/placement** — `internal` nested in an internal class widens it to the assembly for nothing; sibling idiom is `private sealed class` (`SqliteConnection.cs:938, 954, 963`).
5. **Naming** — "Info" is a non-name; the thing cached is *the ordinal of the rowid column*, which as a plain value needs no class name.

### `SqliteDataRecord` state redesign (`:39`, `:327-402`)
1. **Stringly-typed key with false injectivity assumption** (:328) — `("a", "b_c")` and `("a_b", "c")` both key to `"a_b_c"`; on collision `TryGetValue` (:329) serves the other table's entry, `GetInt64` (:402) reads the wrong table's rowid, and the `SqliteBlob` (:404) opens the wrong row — silently reintroducing, via key encoding, the exact cross-table-confusion bug class the PR fixes. A key type exists to make this unrepresentable; the in-assembly idiom already exists (`FunctionsKeyComparer` over `(string name, int arity)`, SqliteConnection.cs:963). The interpolated string also allocates on every call including cache hits.
2. **Lost negative caching — "searched and not found" is no longer representable.** The old `int?` had three states (null / -1 / ≥0) with the not-found result cached. The dictionary has two (present/absent); absence conflates "never searched" with "searched, absent." Verified against the code path: unresolvable tables re-run the full scan per call — `FieldCount` native calls, `sqlite3_table_column_metadata` (:359), and re-execution of `SELECT COUNT(*) FROM pragma_table_info(...)` (:375-381, since `pkColumns` resets at :331) — one extra SQL statement per `GetBytes`/`GetChars` chunk.
3. **The `Debug.Assert` (:393) inverted its meaning** — the old one documented "sentinel always assigned" (tautology); the PR deleted the sentinel but kept the assert, which now fires precisely in the legitimate, explicitly-handled not-found case; the :396 fallback is unreachable in Debug builds without tripping it. Statically confirmed reachable via `GetStream_works_when_composite_pk` (test :516/:533). [Inference] failed assert without a debugger terminates Debug-configuration processes — not verified by running the suite by this agent (but see silent-failure-hunter's empirical confirmation above).
4. **Field style breaks every convention in the file** (:39) — PascalCase, no `_` prefix, no `private`, and **eagerly allocated** in every `SqliteDataRecord` (one per result set) including records that never touch a blob, while every sibling cache is lazy (`_blobCache ??=` :493, `_columnNameOrdinalCache` :141, `_typeCache ??=` :223). Nits: stray whitespace line :17; `rowidkey` → `rowIdKey`.

### Ratings
| Dimension | Score | Rationale |
|---|---|---|
| Encapsulation | 3/10 | Field implicitly private/readonly (good), but entries are mutable-from-anywhere, the nested type is assembly-visible, and key construction is an inline convention no type owns |
| Invariant expression | 2/10 | Central invariant smeared across string concatenation with a false injectivity assumption; tri-state lifecycle collapsed to two states; the one assert asserts the wrong thing |
| Invariant usefulness | 5/10 | The keyed-cache invariant itself is exactly right and fixes a real bug — `RowIdInfo` contributes nothing to it |
| Invariant enforcement | 3/10 | Nothing validates construction; setters allow post-hoc violation; key injectivity unenforced; the only runtime check misfires on a valid, tested path |

### Recommended design
Delete `RowIdInfo`; tuple-keyed dictionary of ordinals with an explicit not-found state, lazily initialized like every sibling cache:

```csharp
// null entry value = searched, no usable rowid column; absent key = not yet searched
private Dictionary<(string? Database, string? Table), int?>? _rowIdOrdinals;

var key = (blobDatabaseName, blobTableName);
_rowIdOrdinals ??= new();
if (!_rowIdOrdinals.TryGetValue(key, out var rowIdOrdinal))
{
    rowIdOrdinal = FindRowIdOrdinal(ordinal, blobDatabaseName, blobTableName); // extracted scan; null if absent
    _rowIdOrdinals.Add(key, rowIdOrdinal);   // negative results cached too
}

if (rowIdOrdinal is not { } found)
{
    return new MemoryStream(GetCachedBlob(ordinal), false);
}
var rowid = GetInt64(found);
```

(Variant B: `Dictionary<(string?, string?), int>` with `-1` — faithful sentinel port, no `Nullable<int>` overhead.) The tuple key makes the collision unrepresentable and allocation-free; the `int?` value restores the third state; extracting `FindRowIdOrdinal` gives the search-once rule an owner and removes the bad assert naturally; lazy `??=` + `_camelCase` restore file consistency. Net complexity is *negative* — fewer lines than merged. On the `netstandard2.0` target, the tuple avoids `IsExternalInit` concerns a record struct would raise.

---

# Consolidated summary

## Critical (2)
1. **[silent-failure-hunter — empirically verified; code-reviewer, comment-analyzer, type-design-analyzer concur]** `Debug.Assert(rowIdForOrdinal!=null)` fires on ordinary queries (expression columns, blob-without-PK projections, composite PK) and kills the process in Debug builds (verified exit 134); Release silently diverges — `SqliteDataRecord.cs:393`
2. **[silent-failure-hunter — empirically verified; all agents flagged]** `$"{db}_{table}"` key collision serves one table's cached rowid ordinal for another → silently wrong row's BLOB bytes (verified repro) or spurious read-order-dependent `no such rowid` — `SqliteDataRecord.cs:328`

## Important (5)
3. Negative results no longer cached → full scan + `pragma_table_info` SQL query per `GetBytes` chunk on unresolvable tables; verified 3× slowdown — `SqliteDataRecord.cs:329-394` [all four code-facing agents]
4. `RowIdInfo`: unused mutable `TableName`, unnecessary type, heap allocation on hot path, wrong accessibility — `SqliteDataRecord.cs:20-30`
5. Cache-hit branch (`TryGetValue` → true) executed by zero tests; database half of the key has zero coverage (no `ATTACH` in the suite) — `SqliteDataRecord.cs:329` [pr-test-analyzer]
6. Self-join silently reads the wrong row's blob (pre-existing in kind, adjacent to the fix, untested — a test written today would fail) [pr-test-analyzer, code-reviewer]
7. New test can't distinguish `SqliteBlob` streaming from the `MemoryStream` fallback — missing `Assert.IsType<SqliteBlob>` per file convention — `SqliteDataReaderTest.cs:174-180`

## Suggestions
- `RowIds` → `private readonly ... _rowIds`, lazily initialized (`:39`); drop stray whitespace `:17`; operator spacing `:393`; `out var` inline `:327-329`
- Test: replace `Console.WriteLine` (`:171`) with `Assert.Equal(1, ...)`/`Assert.Equal(1000, ...)` (1000 is load-bearing and undocumented); assert `GetBytes` return values; fix/delete the three comments (`:170`, `:173`, `:179` — use the repo's `[Fact] // Issue #NNNNN` convention)
- Missing tests, priority order: same-table two-blob (cache hit), self-join, `IsType<SqliteBlob>` join variant, ATTACH cross-database join, multi-row iteration, key-collision shape, repeated composite-PK calls, WITHOUT ROWID, aliased rowid

## Strengths
- Correct fix concept at the correct granularity (per database+table), sound cache lifetime, discovery logic preserved unchanged
- Quietly fixes the converse bug (global `-1` poisoning all tables' streaming)
- Genuine hard-failing regression test with well-chosen distinct blob contents and non-coincidental IDs

## Recommended action
The one change that resolves findings 1, 2, 3, and 4 simultaneously: replace `Dictionary<string, RowIdInfo>` with a lazily-initialized `Dictionary<(string?, string?), int?>` (tuple key kills the collision; nullable value restores negative caching; `RowIdInfo` and the bad assert both disappear), then strengthen the test per the priority list. Note the PR is already MERGED, so these would be follow-up fixes rather than pre-merge blocks.
