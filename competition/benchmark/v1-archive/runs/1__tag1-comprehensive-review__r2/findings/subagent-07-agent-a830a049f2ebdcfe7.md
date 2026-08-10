# subagent agent-a830a049f2ebdcfe7

## Security Analysis

### Languages Detected
C#

### Findings

#### Medium

- **[data handling / cache-key collision]** The per-table rowid cache key is built by string concatenation with an ambiguous `_` delimiter: `string rowidkey = $"{blobDatabaseName}_{blobTableName}"` — `src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs:328`. SQLite database and table names may themselves contain underscores (extremely common), so two distinct `(database, table)` pairs referenced in the same query can collide — e.g. main-database table `A_B` (key `main_A_B`) and an ATTACHed database named `main_A` with table `B` (key `main_A_B`). The scan loop itself compares `databaseName`/`tableName` individually and correctly (lines 340, 346), but on a key collision `RowIds.TryGetValue` (line 329) short-circuits that scan and returns the *other* table's `RowIdInfo`. `GetInt64(rowIdForOrdinal.Ordinal)` (line 402) then reads the colliding table's rowid value, and `new SqliteBlob(_connection, blobDatabaseName, blobTableName, blobColumnName, rowid, readOnly: true)` (line 404) opens the correct table but at the wrong row — silently returning another row's BLOB contents, or throwing if that rowid doesn't exist.
  - **Impact**: Wrong-row data disclosure within the connection's own database — an application can hand row X's blob to a caller that requested row Y (an IDOR-shaped integrity/confidentiality failure at the application layer). Only data the connection can already read is exposed, and it requires colliding names co-occurring in one statement (realistic where ATTACH names or table names are dynamic), hence Medium rather than High.
  - **Remediation**: Key the cache on the pair, not a joined string: `Dictionary<(string?, string?), RowIdInfo>` keyed by `(blobDatabaseName, blobTableName)` (value tuples give correct equality/hashing, including nulls for expression columns). Rejected alternative: keep a string key with a `'\0'` separator — smaller diff, but SQLite identifiers are near-arbitrary byte sequences, so any in-band delimiter remains theoretically collidable; the tuple key is unambiguous by construction.
  - **Confidence**: 78/100

### Adjacent harms (below Medium security threshold, noted per governance — code-quality scope crossover)

- **Debug-build assertion regression** — `SqliteDataRecord.cs:393`. The old `Debug.Assert(_rowidOrdinal.HasValue)` was vacuous (the field was pre-set to `-1`). The rewritten `Debug.Assert(rowIdForOrdinal != null)` now actually fires in Debug builds for legitimate cases the `MemoryStream` fallback (line 396–399) is designed to handle: composite-PK tables, `WITHOUT ROWID` tables, or queries that don't select the blob table's rowid/PK column. Release NuGet builds compile the assert out, so no production impact — but Debug/source builds and test runs can fail-fast on valid usage. [Inference] based on the code path; not executed.
- **Negative-result caching removed (resource churn)** — previously `_rowidOrdinal = -1` cached "no rowid found"; now a failed scan caches nothing, so every `GetStream`/`GetBytes` call on such a table's blob (per row, per column) re-runs the full column scan including `sqlite3_table_column_metadata` calls and, for composite-PK tables, re-executes the `pragma_table_info` COUNT query (`pkColumns` is now a per-call local, line 331). Not attacker-amplifiable beyond what the app already invokes — a performance regression, not a vulnerability.

2 low-severity best-practice observations omitted (Medium+ only) — the two adjacent-harm notes above.

### Positive Observations

- The PK-count lookup remains properly parameterized: `SELECT COUNT(*) FROM pragma_table_info($table)` with `Parameters.AddWithValue("$table", tableName)` (`SqliteDataRecord.cs:377-378`) — no SQL injection surface even though `tableName` originates from schema metadata.
- All identifiers passed to `sqlite3_table_column_metadata` and `SqliteBlob` come from SQLite's own column-metadata APIs, not user input; the blob is opened `readOnly: true`.
- The `MemoryStream(GetCachedBlob(ordinal), false)` fallback is a non-writable stream over a defensive copy — safe.
- No new dependencies, no secrets, no crypto, no deserialization introduced; test-only `Console.WriteLine` output contains no sensitive data. No embedded prompt-injection content observed in the diff.

```json-findings
[{"severity":"Medium","confidence":78,"category":"edge-case","file":"src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs","line":328,"finding":"Rowid cache key is built as $\"{blobDatabaseName}_{blobTableName}\" with an ambiguous '_' delimiter; distinct (database, table) pairs such as (main, A_B) and (main_A, B) collide. On collision, RowIds.TryGetValue (line 329) bypasses the correct per-column scan and reuses the other table's rowid ordinal, so GetInt64 (line 402) reads the wrong rowid and SqliteBlob (line 404) opens the correct table at the wrong row - silently returning another row's BLOB data (wrong-row data disclosure) or throwing.","remediation":"Key the cache on the pair rather than a joined string: Dictionary<(string?, string?), RowIdInfo> keyed by (blobDatabaseName, blobTableName). Rejected alternative: an in-band '\\0' separator string key - smaller diff but still theoretically collidable since SQLite identifiers are near-arbitrary.","source":"security-reviewer"}]
```
