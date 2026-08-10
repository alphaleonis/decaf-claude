# subagent agent-acb430f34fffe4855

## Edge Case Analysis

### Pass 1: Path Walk

Traced 1 method (`SqliteDataRecord.GetStream`, `src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs:316-405`) across the 2 changed files (test file reviewed only to confirm coverage, not for its own control flow). Found ~10 branching constructs: the `ordinal` range guard, the `RowIds.TryGetValue` cache-hit/miss branch, the `for` loop's three `continue` guards (`i == ordinal`, database-name mismatch, table-name mismatch), the `columnName == "rowid"` branch, the `dataType == "INTEGER" && primaryKey != 0` branch, the lazy `pkColumns < 0L` compute branch, the `pkColumns == 1L` branch, the `Debug.Assert`, and the final `rowIdForOrdinal == null` fallback branch.

8 candidates identified; 4 confirmed as findings after Pass 2, 4 discarded (ruled out by Pass 2).

Discarded candidates (Pass 2):
- **Duplicate `RowIds.Add` → `ArgumentException`**: unreachable — `Add` is only called inside the `!TryGetValue` branch, and each of the two call sites `break`s immediately after adding, so no key can be added twice within one call, and the class has no concurrency contract that would allow interleaved calls.
- **Expression/aggregate blob column (`sqlite3_column_table_name` → null) causing cross-column cache pollution**: does not manifest — unresolved lookups (`rowIdForOrdinal == null`) are never written to `RowIds`, so two different null-table-name columns never share a poisoned cache entry; they merely each re-scan every call (see confirmed finding below).
- **WITHOUT ROWID table producing a false-positive "rowid" via the single-column `pkColumns == 1` check**: this branch is unchanged from the pre-diff code (only the storage wrapper changed); any resulting misuse would surface as a normal `SqliteException` from `SqliteBlob`'s constructor, which is pre-existing, unchanged behavior, not a new gap introduced by this diff.
- **Multi-statement batch cache lifetime**: verified via `SqliteDataReader.cs:180` (`_record = new SqliteDataRecord(stmt, ...)`) that a new `SqliteDataRecord` — and therefore a fresh, empty `RowIds` dictionary — is constructed per result set/statement in `NextResult`, so no cross-statement bleed occurs.

### Pass 2: Validated Findings

#### High

- **[Missing else/default-equivalent: key collision]** Self-join on the same table (two aliases) reuses the wrong cached rowid ordinal, silently returning the wrong row's blob data — `src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs:325-329,354,386,402`
  - **Unhandled path:** `sqlite3_column_table_name`/`sqlite3_column_database_name` return the underlying table name, not the SQL alias. For a query like `SELECT a.id, a.blob, b.id, b.blob FROM T a JOIN T b ON ...`, both `a.blob` and `b.blob` compute the identical `rowidkey = "main_T"`. The first `GetStream` call (e.g., for `a.blob`) resolves and caches `RowIdInfo(Ordinal=<a.id ordinal>)` under `"main_T"`. The second call (for `b.blob`) hits `RowIds.TryGetValue` and reuses that same cached ordinal — i.e., `a.id`'s value — instead of resolving `b.id`'s ordinal.
  - **Consequence:** `GetInt64(rowIdForOrdinal.Ordinal)` at line 402 reads `a`'s rowid when streaming `b`'s blob column, so `SqliteBlob` opens the wrong row's blob for one side of the join. This is silent, incorrect data, not a crash — no exception is raised, so callers have no signal anything is wrong.
  - **Remediation:** Key the cache on something that disambiguates repeated occurrences of the same table within one result set (e.g., a `(databaseName, tableName)` tuple keyed together with the discovered "sibling" pk/rowid column's own database/table occurrence position), or detect that a table appears more than once among the result columns and skip caching (recompute) for that ordinal group. Rejected alternative: keying purely by column ordinal was considered but discarded — it would eliminate the intended benefit of sharing one lookup across multiple blob columns belonging to the *same* table occurrence.
  - **Confidence:** 85/100

#### Medium

- **[Missing else/default via tautological-to-live assert]** `Debug.Assert(rowIdForOrdinal != null)` changed from a dead (always-true) assertion to one that can genuinely fail — `src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs:393`
  - **Unhandled path:** In the removed code, `_rowidOrdinal = -1;` was set unconditionally *before* the search loop, so `Debug.Assert(_rowidOrdinal.HasValue)` could never fail (a nullable `int?` holding `-1` still `HasValue == true`). The new `rowIdForOrdinal` starts as `null` and is only set when a rowid/single-column-PK match is found, so `Debug.Assert(rowIdForOrdinal != null)` now genuinely fires whenever no match is found — reachable for WITHOUT ROWID tables, expression/aggregate blob columns (null table name), and tables with composite (multi-column) primary keys.
  - **Consequence:** In Debug builds, calling `GetStream` on any blob column with no discoverable rowid/PK trips the assert; in Release builds `Debug.Assert` is compiled out and the code falls through correctly to the `GetCachedBlob` fallback at line 396-399. This is a newly-introduced Debug-only failure path for scenarios (WITHOUT ROWID tables, expression columns, composite PKs) that are otherwise legitimately and correctly handled by the fallback.
  - **Remediation:** Remove the assert or change it to reflect that "not found" is an expected, handled outcome (e.g., a comment or conditional trace) rather than an invariant, since the very next `if (rowIdForOrdinal == null)` branch already handles this case correctly.
  - **Confidence:** 82/100

- **[Off-by-one/ambiguous delimiter — key collision]** Cache key built via unescaped string interpolation can collide across distinct (database, table) pairs — `src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs:328`
  - **Unhandled path:** `string rowidkey = $"{blobDatabaseName}_{blobTableName}";` has no escaping. An ATTACHed database named e.g. `"a_b"` with table `"c"` produces the same key (`"a_b_c"`) as database `"a"` with table `"b_c"`. Since ATTACH aliases and snake_case table names are common, this is a realistic naming collision, not purely theoretical.
  - **Consequence:** The second (database, table) pair to be queried would hit the first pair's cached `RowIdInfo` and silently use the wrong ordinal as the rowid source for `SqliteBlob`, i.e., the same silent-wrong-data class of bug as the self-join finding.
  - **Remediation:** Use a composite (non-string) key, e.g. `Dictionary<(string DatabaseName, string TableName), RowIdInfo>`, which eliminates the ambiguity entirely rather than relying on a delimiter that could appear in identifiers.
  - **Confidence:** 76/100

#### Low

- **[Missing else/default — negative-result caching dropped]** Failed rowid/PK lookups are never cached, so every `GetStream` call on an unresolvable blob column re-runs the full column scan (and, for INTEGER-PK candidate columns, re-executes a `pragma_table_info` query) — `src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs:329-394`
  - **Unhandled path:** The old code cached the "not found" sentinel (`_rowidOrdinal = -1`) so the scan ran once per reader. The new code only calls `RowIds.Add` on success; when the loop completes without a match (WITHOUT ROWID tables, expression/aggregate blob columns, composite-PK tables), nothing is added to `RowIds`, so the next `GetStream` call for that same ordinal repeats the entire `FieldCount` scan, including any `_connection.CreateCommand()`/`ExecuteScalar()` pragma query, from scratch.
  - **Consequence:** No incorrect result (the fallback to `GetCachedBlob` is always reached), but repeated, unnecessary work on every call for these column types — a performance regression relative to the removed sentinel-based negative caching, most noticeable when the same unresolvable blob ordinal is read many times (e.g., once per row).
  - **Remediation:** Cache negative results too, but scoped per `(database, table)` key rather than globally (the old design's actual bug was global scope, not that negative caching existed at all).
  - **Confidence:** 78/100

### Positive Observations

- Cross-table disambiguation (the PR's stated goal) is correctly handled: two genuinely different real tables (e.g., `A` and `B` in the added test) get distinct cache keys and each independently resolves and caches its own rowid ordinal, fixing the original single-`_rowidOrdinal` bug (#32747) for the straightforward multi-table-join case.
- Cache lifetime is correctly scoped to one result set: `SqliteDataReader.cs:180` constructs a new `SqliteDataRecord` (and thus a fresh `RowIds` dictionary) per statement/result set in `NextResult`, so no stale ordinal bleeds across statements in a batch.
- `ordinal` range validation (`ArgumentOutOfRangeException`) at the top of `GetStream` is unchanged and still guards all downstream `sqlite3_column_*` calls against out-of-range input.

```json-findings
[
  {"severity":"High","confidence":85,"category":"edge-case","file":"src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs","line":328,"finding":"Self-join on the same underlying table (two SQL aliases) produces an identical rowidkey ($\"{blobDatabaseName}_{blobTableName}\") for both occurrences, because sqlite3_column_table_name returns the underlying table name, not the alias. The first GetStream call caches a RowIdInfo pointing at one alias's rowid/PK ordinal; the second alias's GetStream call reuses that same cached ordinal via RowIds.TryGetValue, silently reading the wrong row's rowid and returning the wrong blob data with no exception.","remediation":"Key the RowIds cache on something that disambiguates repeated occurrences of the same table in one result set (e.g. detect duplicate table references among result columns and skip/bypass caching for those ordinals), or otherwise avoid assuming database+table name alone uniquely identifies a rowid source within a single result set."},
  {"severity":"Medium","confidence":82,"category":"edge-case","file":"src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs","line":393,"finding":"Debug.Assert(rowIdForOrdinal!=null) replaces the old Debug.Assert(_rowidOrdinal.HasValue), which was always true because _rowidOrdinal was unconditionally set to -1 (a non-null sentinel) before the search loop ran. The new rowIdForOrdinal starts as null and stays null when no rowid/single-column-PK match is found (WITHOUT ROWID tables, expression/aggregate blob columns, composite-PK tables), so the assert can now genuinely fire in Debug builds for these previously-benign cases, even though the very next line correctly handles the null case via the GetCachedBlob fallback.","remediation":"Remove the assert, or replace it with a non-fatal diagnostic, since 'no rowid found' is a legitimate, already-handled outcome rather than a broken invariant."},
  {"severity":"Medium","confidence":76,"category":"edge-case","file":"src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs","line":328,"finding":"rowidkey is built via unescaped string interpolation ($\"{blobDatabaseName}_{blobTableName}\"), so distinct (database, table) pairs can collide, e.g. database 'a_b' + table 'c' vs database 'a' + table 'b_c' both yield 'a_b_c'. A collision causes the second pair's GetStream call to silently reuse the first pair's cached rowid ordinal, streaming the wrong row's blob.","remediation":"Use a composite (non-string-concatenated) dictionary key, e.g. Dictionary<(string DatabaseName, string TableName), RowIdInfo>, to remove the ambiguity."},
  {"severity":"Low","confidence":78,"category":"edge-case","file":"src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs","line":394,"finding":"Only successful rowid/PK lookups are added to RowIds; failed lookups (WITHOUT ROWID tables, expression/aggregate blob columns, composite-PK tables) are never cached, so every subsequent GetStream call on that ordinal re-runs the full FieldCount scan and, for INTEGER-PK candidate columns, re-executes the pragma_table_info command — a repeated-work regression versus the removed global negative-caching sentinel (previously _rowidOrdinal = -1 cached the failure once).","remediation":"Cache negative results too, but scoped per (database, table) key instead of globally, avoiding the original bug (which stemmed from global scope, not from negative caching itself)."}
]
```
