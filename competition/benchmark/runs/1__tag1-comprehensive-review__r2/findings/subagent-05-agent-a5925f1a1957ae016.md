# subagent agent-a5925f1a1957ae016

Now I have the full context needed. Let me finalize the review.

## Blind Review

### Approach
Reviewed 2 files (1 source, 1 test) / ~75 changed lines of diff with no project context. The change replaces a single nullable `int?` cache (`_rowidOrdinal`) with a `Dictionary<string, RowIdInfo>` (`RowIds`) keyed by `"{database}_{table}"`, apparently to support resolving blob rowids across multiple tables in a single query (e.g., joins), as demonstrated by the new `GetBytes_works_streaming_join` test.

### Findings

#### High

- **[Logic Requiring Invisible Assumptions]** `Debug.Assert(rowIdForOrdinal!=null)` at `src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs:393` is no longer tautological and can now genuinely fail for a previously-supported code path. — `src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs:327-396`
  - **Why (from diff alone):** In the old code, `_rowidOrdinal = -1;` was set as a sentinel *before* the discovery loop ran, so `Debug.Assert(_rowidOrdinal.HasValue)` afterward was always true regardless of whether a rowid was actually found — it was a no-op assertion by construction. In the new code, `rowIdForOrdinal` is declared as `null` (line 327) and is only reassigned inside the two `break` branches when a rowid **is** found (lines 354, 386). If neither branch fires (e.g. a `WITHOUT ROWID` table, a table with a composite primary key, or any table where no single-column `INTEGER PRIMARY KEY` exists), `rowIdForOrdinal` remains `null` when the assert executes at line 393 — which now fires for real. The very next lines (`if (rowIdForOrdinal == null) { return new MemoryStream(...); }`, line 396) prove this is an intentionally-supported, non-error outcome, not a genuine invariant violation. In Debug builds this changes previously-silent, correct behavior into an assertion failure on a legitimate code path.
  - **Remediation:** Remove the assert, or change it to only assert the invariant that actually holds (e.g., that the dictionary lookup/loop always terminates), not that a rowid was found.
  - **Confidence:** 82/100

- **[Missing Guardrails / Surprising Behavior]** The "no rowid found" result is no longer cached, causing the full discovery loop (and a live SQL query) to re-run on every call. — `src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs:327-393`
  - **Why (from diff alone):** `RowIds.Add(rowidkey, rowIdForOrdinal)` (lines 355, 387) is only invoked inside the two success branches. When no rowid/single-column PK is found, nothing is added to `RowIds`, so on the *next* call to `GetStream` for that same table/column the `RowIds.TryGetValue` check misses again and the entire `for` loop over `FieldCount` re-executes — including, when a candidate `INTEGER PRIMARY KEY` column is inspected, a live `command.ExecuteScalar()` query against `pragma_table_info` (lines ~372-379). The old code cached this "not found" outcome as `_rowidOrdinal = -1` permanently, avoiding repeated work. This is a real behavior regression: repeated per-row SQL queries for any table that lacks a discoverable rowid.
  - **Remediation:** Add a "not found" sentinel to the dictionary too (e.g., store a nullable/sentinel `RowIdInfo` or a separate `HashSet<string>` of keys known to have no rowid) so the negative result is cached just like the positive one.
  - **Confidence:** 80/100

#### Medium

- **[Missing Guardrails]** Cache key built by naive string concatenation can collide between distinct database/table pairs. — `src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs:328`
  - **Why (from diff alone):** `string rowidkey = $"{blobDatabaseName}_{blobTableName}";` has no unambiguous delimiter. A table named `"A_B"` in a database named `"main"` produces the same key (`"main_A_B"`) as a table `"B"` in a database named `"main_A"` (SQLite attached-database names are arbitrary identifiers, so this is reachable in principle). On collision, `RowIds.TryGetValue` returns the wrong `RowIdInfo`, and `GetInt64(rowIdForOrdinal.Ordinal)` (line 402) would read the rowid from the wrong column ordinal, silently producing an incorrect `SqliteBlob` handle (wrong row/rowid) for one of the two tables.
  - **Remediation:** Use a non-ambiguous composite key, e.g. a `ValueTuple<string,string>` (`(blobDatabaseName, blobTableName)`) as the dictionary key instead of string concatenation, or a struct key — avoids any collision risk entirely.
  - **Confidence:** 78/100

#### Low

- **[Naming Incoherence]** New field `RowIds` breaks the private-field naming convention used everywhere else in the same class. — `src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs:39`
  - **Why (from diff alone):** Every other private field in this class visible in the diff uses `_camelCase` with an explicit intent of being private (`_connection`, `_addChanges`, `_blobCache`, `_columnNameOrdinalCache`, `_columnNameCache`, `_stepped`, `_alreadyThrown`, `_alreadyAddedChanges`). The new field is declared as `readonly Dictionary<string, RowIdInfo> RowIds = new Dictionary<string, RowIdInfo>();` — PascalCase, with no explicit access modifier — which reads like a public property/field at a glance and is inconsistent with the rest of the same file.
  - **Remediation:** Rename to `_rowIds` and add an explicit `private` modifier to match the surrounding code.
  - **Confidence:** 78/100

### Positive Observations
- The core motivation of the change (resolving a distinct rowid ordinal per table rather than a single connection-wide ordinal) is a sensible fix for the join scenario shown in the new test, and the new `GetBytes_works_streaming_join` test itself has correct, verifiable assertions for the byte values it checks.
- The fallback path (`if (rowIdForOrdinal == null) return new MemoryStream(GetCachedBlob(ordinal), false);`) is preserved from the original code, so Release-build behavior for the "no rowid" case remains functionally correct despite the caching regression noted above.

```json-findings
[
  {"severity":"High","confidence":82,"category":"edge-case","file":"src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs","line":393,"finding":"Debug.Assert(rowIdForOrdinal!=null) is no longer tautological (unlike the prior sentinel-based _rowidOrdinal=-1 assert) and now genuinely fires for any table without a discoverable rowid or single-column INTEGER PRIMARY KEY (e.g. WITHOUT ROWID tables, composite primary keys), a scenario the very next line handles as a legitimate, expected outcome via a MemoryStream fallback.","remediation":"Remove the assert or rework it to check a real invariant (e.g. that the loop always terminates), not that a rowid was necessarily found.","source":"blind-hunter"},
  {"severity":"High","confidence":80,"category":"other","file":"src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs","line":355,"finding":"RowIds.Add is only called when a rowid IS found (inside the two break branches); the negative/not-found outcome is never cached, so every GetStream call for a blob column on a table lacking a discoverable rowid re-runs the full column-scan loop and potentially a live pragma_table_info SQL query, unlike the prior code which cached the -1 sentinel permanently.","remediation":"Cache the negative result too (e.g. store a sentinel RowIdInfo or track known no-rowid keys in a separate set) so repeated calls short-circuit as before.","source":"blind-hunter"},
  {"severity":"Medium","confidence":78,"category":"edge-case","file":"src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs","line":328,"finding":"The dictionary cache key `$\"{blobDatabaseName}_{blobTableName}\"` uses plain string concatenation with an ambiguous separator, so distinct (database, table) pairs can collide (e.g. database \"main\", table \"A_B\" vs database \"main_A\", table \"B\" both yield key \"main_A_B\"), causing GetStream to look up the wrong cached RowIdInfo and read the rowid from an incorrect column ordinal.","remediation":"Use a tuple or struct key, e.g. (blobDatabaseName, blobTableName), instead of string concatenation to eliminate any collision risk.","source":"blind-hunter"},
  {"severity":"Low","confidence":78,"category":"lint","file":"src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs","line":39,"finding":"New field `RowIds` is declared PascalCase with no explicit access modifier, inconsistent with every other private field in the same class which uses `_camelCase` naming (_connection, _blobCache, _stepped, etc.).","remediation":"Rename to `_rowIds` and add an explicit `private` modifier for consistency with the rest of the class.","source":"blind-hunter"}
]
```
