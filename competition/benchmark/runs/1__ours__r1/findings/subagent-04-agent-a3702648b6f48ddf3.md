# subagent agent-a3702648b6f48ddf3

Depth: **quick** — ~30 changed executable source lines (below the 50-line standard threshold), spawned via high-risk domain (data-access library over an external native API, SQLite BLOB I/O). Per calibration: `ADV_ASSUMPTION` technique, max 3 findings. All three findings below trace to assumptions introduced by the rewrite of the rowid-ordinal cache; all were verified statically against the full post-change file (`/home/decaf/code/decaf-claude/competition/benchmark/repos/1/src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs`) and the pre-change side of `git diff HEAD~1..HEAD`.

```json
[
  {
    "file": "src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs",
    "line": 328,
    "severity": "High",
    "category": "other",
    "issue": "[ADV_ASSUMPTION] Cache key assumes '_' cannot appear ambiguously in identifiers: ATTACH db \"db_x\" with table \"t\" + ATTACH db \"db\" with table \"x_t\" -> both keys are \"db_x_t\" -> GetStream on the first table's blob caches its PK ordinal -> GetStream on the second table's blob hits the colliding key, reads the FIRST table's Id as rowid -> SqliteBlob opened on the wrong row: silent wrong blob data if that rowid exists in the second table, or SqliteException 'no such rowid' if not — the exact bug class this PR fixes, resurrected via key collision",
    "fix": "Key the dictionary on the pair, not a concatenated string: use Dictionary<(string Db, string Table), RowIdInfo> (value-tuple keys have structural equality), eliminating any separator ambiguity",
    "confidence": 100,
    "pre_existing": false
  },
  {
    "file": "src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs",
    "line": 329,
    "severity": "High",
    "category": "performance",
    "issue": "[ADV_ASSUMPTION] Rewrite assumes dictionary-absence reproduces the old '-1' negative sentinel, but the not-found result is never cached: composite-PK table (e.g. GetStream_works_when_composite_pk schema) -> every GetBytes/GetChars/GetStream call misses TryGetValue -> full column re-scan with per-column sqlite3_table_column_metadata calls PLUS a fresh 'SELECT COUNT(*) FROM pragma_table_info' command prepared and executed on the live connection -> chunked blob reads (GetBytes loop) and multi-row iteration amplify this to one hidden query per chunk per row (a 1 GB blob read in 4 KB chunks issues ~262k pragma queries where the old code issued exactly 1)",
    "fix": "Cache the negative result too: add a sentinel entry (e.g. RowIds.Add(rowidkey, NoRowId) with Ordinal = -1, or a Dictionary<key, RowIdInfo?> storing null) after the search loop completes without a match, restoring the pre-change once-per-table cost",
    "confidence": 100,
    "pre_existing": false
  },
  {
    "file": "src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs",
    "line": 393,
    "severity": "Medium",
    "category": "error-handling",
    "issue": "[ADV_ASSUMPTION] New assert assumes a rowid ordinal is always found, but null is a legitimate outcome: composite-PK table or expression column (existing test GetStream_works_when_composite_pk, or SELECT of a computed blob) -> search loop completes with rowIdForOrdinal == null -> Debug.Assert(rowIdForOrdinal!=null) fires on every such call in Debug builds (the old code pre-assigned -1 so Debug.Assert(_rowidOrdinal.HasValue) was vacuously true) -> Debug-configuration test runs and any Debug consumer of the library hit assertion failure (process FailFast under default .NET Core trace listeners) on a fully valid query",
    "fix": "Delete the assert (null is the designed signal for the MemoryStream fallback on line 396), or assert the actual invariant, e.g. that a found entry was added to RowIds",
    "confidence": 75,
    "pre_existing": false
  }
]
```

## Considered But Not Flagged

- **`sqlite3_table_column_metadata` invoked with null database/table/column names** when the streamed blob is an expression column and another expression column exists in the select list (null db/table names compare equal, origin name null skips the "rowid" check, metadata call proceeds with nulls). Fell out of scope: the loop body is byte-for-byte unchanged from the pre-change code — every step already existed before this changeset (pre-existing, not emergent from this diff).
- **WITHOUT ROWID table with a single INTEGER PK** → search classifies the PK as a rowid alias → `sqlite3_blob_open` fails ("cannot open table without rowid"). Same classification logic existed pre-change; not introduced here.
- **Concurrent GetStream on the same record mutating `RowIds`** (Dictionary corruption under parallel `Add`). Fell apart at the precondition step: `DbDataReader` is documented non-thread-safe, and the replaced `int?` field had equivalent (in fact worse, torn-read) exposure — no new legitimate-usage scenario constructs.
- **Unbounded `RowIds` growth as abuse vector** — dictionary size is bounded by the number of distinct (db, table) pairs in one statement's select list; SQLite caps joined tables; no exhaustion chain survives.
- **Same table cached under differently-cased keys across calls** — `sqlite3_column_table_name` returns the declared schema name consistently for a given statement, so the key is stable; scenario failed at step 1.

### Probe Requests

- **Test**: `test/Microsoft.Data.Sqlite.Tests/SqliteDataReaderTest.cs`, `GetStream_works_when_composite_pk`, run with `Microsoft.Data.Sqlite.Core` compiled in **Debug** configuration (no production-line removal — configuration probe). **Expected failure**: `Debug.Assert(rowIdForOrdinal!=null)` at line 393 fires (assertion failure / test-host FailFast), confirming finding 3's runtime impact. [Unverified — no .NET SDK in this environment; confidence for that finding set from static reasoning accordingly.]
