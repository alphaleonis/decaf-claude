# subagent agent-a38292914a8211f0d

## Edge Case Analysis

### Pass 1: Path Walk

Traced 1 method (`SqliteDataRecord.GetStream`, the only method with materially changed control flow) across 1 source file (`src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs`). Found 8 branching constructs relevant to the diff: ordinal bounds check, `RowIds.TryGetValue` hit/miss, per-column database/table-name equality filters, `origin_name == "rowid"` match, `pkColumns` sentinel/compute branch, `pkColumns == 1L` match, the post-loop `Debug.Assert`, and the final `rowIdForOrdinal == null` fallback branch.

8 candidates identified; 2 confirmed as findings after Pass 2 (one retained at low confidence below the JSON-inclusion threshold), 5 discarded (ruled out by Pass 2 — verified safe by reading `SqliteDataReader.cs` construction/reuse logic and pre-existing, unchanged code paths).

### Pass 2: Validated Findings

#### High

- **[Unguarded inputs / cache-key collision]** Self-joins (the same table referenced twice via aliases) collide on the same `RowIds` cache key, causing the wrong row's rowid to be used for the second blob column — `src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs:328-357,401-404`
  - **Unhandled path:** `rowidkey = $"{blobDatabaseName}_{blobTableName}"` (line 328) is built only from the database and table name returned by `sqlite3_column_database_name`/`sqlite3_column_table_name`. These SQLite C APIs report the *underlying* table name, not the query alias, so for `SELECT a1.blob, a2.blob FROM T a1 JOIN T a2 ON ...` both blob columns produce the identical key `"main_T"`. The first `GetStream` call scans and caches `RowIdInfo` pointing at whichever `rowid`/PK column it finds first (e.g., `a1`'s), then `RowIds.Add(rowidkey, ...)` (lines 355, 387). The second blob column's `GetStream` call hits `TryGetValue` successfully (line 329) and reuses `a1`'s cached ordinal even though it belongs to `a2`.
  - **Consequence:** `GetInt64(rowIdForOrdinal.Ordinal)` (line 402) reads the wrong row's rowid, and the returned `SqliteBlob` silently opens/streams the blob from a *different row of the same table* — no exception, just wrong data returned to the caller. This is exactly the self-join scenario the PR's own fix does not address (its new test `GetBytes_works_streaming_join` only exercises two *different* tables, not the same table joined to itself).
  - **Remediation:** Don't key purely by database+table name; either disambiguate cache entries using each candidate rowid column's ordinal proximity/position relative to the blob column (SQLite doesn't expose aliases, so exact instance matching requires positional heuristics), or detect the collision (a second distinct match for the same key within one scan) and fail closed (throw `NotSupportedException` for self-joins) rather than silently returning incorrect data.
  - **Confidence:** 80/100

#### Medium

- **[Missing else/default — broken invariant + resource-cleanup-adjacent regression]** The "no derivable rowid" result is no longer cached, unlike the old code, causing repeated full rescans (with a nested SQL query) and a `Debug.Assert` that can now genuinely fire for common, already-tested query shapes — `src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs:329-394`
  - **Unhandled path:** In the pre-change code, `_rowidOrdinal = -1;` was assigned as a sentinel *before* the scan loop, so `Debug.Assert(_rowidOrdinal.HasValue)` was tautologically always true, and the negative ("not found") outcome was cached forever via `_rowidOrdinal.Value < 0`. In the new code there is no pre-loop sentinel: if the loop completes without a match (expression/literal columns, composite-PK tables, etc. — all exercised by the existing `GetStream_works`, `GetStream_works_with_text`, `GetStream_works_with_int`, `GetStream_works_with_float`, and `GetStream_works_when_composite_pk` tests), `rowIdForOrdinal` stays `null`, `Debug.Assert(rowIdForOrdinal!=null)` (line 393) now evaluates a condition that is genuinely false, and — critically — nothing is ever written to `RowIds` for that key.
  - **Consequence:** Every subsequent `GetStream`/`GetBytes`/`GetChars` call on such a column (note `GetBytes` at line 276 calls `GetStream` fresh every invocation, e.g. for chunked reads) re-executes the full `O(FieldCount)` scan plus, when an INTEGER PK column is present, a fresh `command.ExecuteScalar()` round trip (`SELECT COUNT(*) FROM pragma_table_info($table)`, lines 375-381) on *every single call* instead of once. Additionally, the assert firing on a legitimate, already-tested code path represents a false invariant; in Debug builds/configurations where `Debug.Assert` failures are surfaced (e.g. UI dialog on net462/Windows, or a custom listener that throws), this would abort or hang test/production runs on inputs the code otherwise handles correctly one line later.
  - **Remediation:** Cache the negative outcome too (e.g., store a sentinel/null-marker entry in `RowIds` for keys with no derivable rowid, mirroring the old `-1` sentinel pattern), and remove or relocate the `Debug.Assert` since "no derivable rowid" is an expected, already-handled outcome, not a broken invariant.
  - **Confidence:** 80/100

#### Low

- **[Unguarded inputs — hash-style key collision]** `rowidkey = $"{blobDatabaseName}_{blobTableName}"` uses a plain underscore delimiter with no escaping, so distinct `(database, table)` pairs can collide, e.g. database `"a"` + table `"b_c"` and database `"a_b"` + table `"c"` both produce `"a_b_c"` — `src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs:328`. This requires an `ATTACH`ed database whose name happens to overlap a delimiter split with another table's schema/name, which is a fairly specific, low-likelihood real-world coincidence, so this is retained only as a low-confidence observation (below the ≥75 threshold for the JSON block).
  - **Confidence:** ~50/100 (not included in `json-findings`)

### Positive Observations

- The core bug this PR targets — ordinary joins across *different* tables each getting their own correctly cached rowid ordinal — is handled correctly and is covered by the new `GetBytes_works_streaming_join` test.
- Multiple blob columns from the *same* table (non-self-join) correctly share one `RowIds` cache entry, since they legitimately share the same rowid ordinal.
- `RowIds` is an instance field on `SqliteDataRecord`, and a fresh `SqliteDataRecord` is constructed per prepared statement (`SqliteDataReader.cs:180`), so there's no stale-cache leakage across different statements in a batch/`NextResult()` — verified by reading the reader's statement-iteration loop.
- The ordinal bounds check (`ordinal < 0 || ordinal >= FieldCount`) at the top of `GetStream` is unchanged and still throws `ArgumentOutOfRangeException` for out-of-range ordinals.

```json-findings
[
  {"severity":"High","confidence":80,"category":"edge-case","file":"src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs","line":328,"finding":"Self-joins (same table referenced twice via aliases) collide on the same RowIds cache key ($\"{blobDatabaseName}_{blobTableName}\"), because sqlite3_column_table_name reports the underlying table name, not the query alias. The second blob column's GetStream call reuses the first alias's cached rowid ordinal, silently returning blob data from the wrong row of the same table.","remediation":"Disambiguate cache entries beyond database+table name (e.g. detect duplicate matches within one scan and fail closed with a clear exception for self-joins) instead of silently returning incorrect data.","source":"edge-case-hunter"},
  {"severity":"Medium","confidence":80,"category":"edge-case","file":"src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs","line":393,"finding":"The 'no derivable rowid' outcome is no longer cached (unlike the old sentinel-based code), so every GetStream/GetBytes/GetChars call on such a column re-runs the full scan plus a nested SQL round trip (pragma_table_info count query), and Debug.Assert(rowIdForOrdinal!=null) now evaluates a condition that is genuinely false for legitimate, already-tested cases (expression columns, composite-PK tables) instead of being a tautology as before.","remediation":"Cache the negative result too (sentinel entry in RowIds) and remove/relocate the Debug.Assert since 'no rowid' is an expected, handled outcome.","source":"edge-case-hunter"}
]
```

Files referenced: `/home/decaf/code/decaf-claude/competition/benchmark/repos/1/src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs`, `/home/decaf/code/decaf-claude/competition/benchmark/repos/1/src/Microsoft.Data.Sqlite.Core/SqliteDataReader.cs`, `/home/decaf/code/decaf-claude/competition/benchmark/repos/1/test/Microsoft.Data.Sqlite.Tests/SqliteDataReaderTest.cs`.
