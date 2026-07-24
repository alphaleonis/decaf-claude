# subagent agent-abc11083af48e7160

Depth: **Standard** — ~30 changed executable source lines (below the 200 deep threshold), but the change sits in persistence/data-read streaming (high-risk domain) and the dispatch instructions enumerate composition/cascade angles to probe, so assumption + composition + abuse techniques were applied. All scenarios verified statically against `/home/decaf/code/decaf-claude/competition/benchmark/repos/1/src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs`, the pre-change version (`git show HEAD~1`), `SqliteDataReader.cs` (record lifetime), and the existing test suite. No build available; confidence set per static-reasoning anchors.

Key verified facts the findings rest on:
- Old code set `_rowidOrdinal = -1` *before* scanning, so "no rowid found" was negatively cached once per record. New code adds to `RowIds` only at lines 355/387 (success branches); the null path (line 396) caches nothing.
- `pkColumns` is a local reset to `-1L` on every `GetStream` call (line 331), so the `pragma_table_info` COUNT query memoization no longer survives across calls.
- `GetBytes` (line 276), `GetChars` (line 290), and `GetTextReader` each call `GetStream` on every invocation.
- The scan loop's table/database guards (lines 339–349) are correct — it does *not* break on a foreign table's `rowid`; `RowIdInfo.TableName` always equals `blobTableName` (redundant but harmless).
- `SqliteDataRecord` is recreated per result set (`SqliteDataReader.cs` line 180), so cache lifetime across `Read()`/`NextResult()` is sound.
- Existing test `GetStream_works_when_composite_pk` (test file line 516) reaches the null-scan-result path and asserts the `MemoryStream` fallback works — i.e., null is a legitimate, handled outcome.

```json
[
  {
    "file": "src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs",
    "line": 396,
    "severity": "High",
    "category": "performance",
    "issue": "[ADV_COMPOSITION] Negative-cache removed: no-rowid scan result never stored in RowIds → chunked GetBytes loop re-runs full scan every call → for composite-PK/view/expression tables each 8KB chunk of a blob issues N sqlite3_table_column_metadata calls plus a fresh 'SELECT COUNT(*) FROM pragma_table_info' command (pkColumns is a per-call local, line 331) → reading one 100MB blob in chunks from 'SELECT Id1, Id2, Data FROM CompositePkTable' executes ~12,800 extra SQL commands mid-read on the same connection. Old code cached _rowidOrdinal=-1 once per record; the fix silently dropped that path.",
    "fix": "On scan failure, store a sentinel entry (e.g. RowIds.Add(rowidkey, new RowIdInfo(-1, blobTableName))) and treat Ordinal < 0 as the MemoryStream fallback, restoring the old negative-cache semantics per (db, table).",
    "confidence": 100,
    "pre_existing": false
  },
  {
    "file": "src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs",
    "line": 328,
    "severity": "High",
    "category": "other",
    "issue": "[ADV_ASSUMPTION] Self-join breaks the one-rowid-per-(db,table) key assumption: 'SELECT a1.ID, a1.VALUE, a2.ID, a2.VALUE FROM A a1 JOIN A a2 ON ...' — sqlite3_column_table_name returns the origin table ('A') for both aliases, so both blob columns map to key 'main_A'; GetStream(1) caches a1.ID's ordinal, then GetStream(3) reuses it → SqliteBlob opened for a2.VALUE with a1's rowid → silently returns the wrong row's blob (both rowids exist in A, so no exception is thrown). The PR's stated purpose is fixing joined-query blob streaming, but its key granularity cannot distinguish two instances of the same table.",
    "fix": "During the scan, if more than one candidate rowid/INTEGER-PK column from the same (db, table) exists at distinct ordinals (alias ambiguity), do not cache a rowid — fall back to the eager MemoryStream path, which is always correct.",
    "confidence": 75,
    "pre_existing": true
  },
  {
    "file": "src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs",
    "line": 393,
    "severity": "Medium",
    "category": "error-handling",
    "issue": "[ADV_ASSUMPTION] Debug.Assert semantics silently inverted: old code set _rowidOrdinal=-1 before scanning so Debug.Assert(_rowidOrdinal.HasValue) was vacuously true; new Debug.Assert(rowIdForOrdinal!=null) is FALSE on every legitimate no-rowid scan (composite PK, expression blob, blob selected without its PK) — the exact path the very next statement (line 396) handles gracefully. Existing tests GetStream_works_when_composite_pk and GetStream_works reach this state, so any Debug-configuration build/test run trips the assertion (Environment.FailFast on .NET Core without a custom trace listener).",
    "fix": "Delete the Debug.Assert — null is a supported outcome consumed by the fallback branch immediately below — or assert the actual invariant (e.g. rowIdForOrdinal == null || RowIds.ContainsKey(rowidkey)).",
    "confidence": 100,
    "pre_existing": false
  },
  {
    "file": "src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs",
    "line": 328,
    "severity": "Medium",
    "category": "other",
    "issue": "[ADV_COMPOSITION] Composite key '{db}_{table}' with '_' separator collides on underscore-containing names: ATTACH databases aliased 'a_b' (table 'c') and 'a' (table 'b_c') both produce key 'a_b_c' — streaming a blob from each in one query makes the second lookup hit the first table's cached RowIdInfo → GetInt64 reads the wrong table's rowid → SqliteBlob throws 'no such rowid: N' or silently returns the wrong row's blob, reintroducing the exact bug class this PR fixes for that name pair.",
    "fix": "Key the dictionary on the pair itself — Dictionary<(string db, string table), RowIdInfo> — or join with a character illegal in identifiers (e.g. '\\0') instead of '_'.",
    "confidence": 75,
    "pre_existing": false
  }
]
```

## Considered But Not Flagged

- **WITHOUT ROWID table with single INTEGER PK** — `sqlite3_table_column_metadata` reports it as PK, `pragma_table_info` count is 1, so the code caches it as a rowid and `sqlite3_blob_open` fails ("cannot open table without rowid") instead of falling back to `MemoryStream`. Fell out of scope as a *new* finding: the pre-change scan had byte-identical logic — pure pre-existing single-pattern issue, and I could not confirm the metadata-API PK flag behavior for WITHOUT ROWID tables without running code (anchor 50 on the chain, but fully pre-existing and single-category → quick-reviewer territory).
- **LEFT JOIN unmatched row → NULL rowid** — cached ordinal for B.ID is NULL on unmatched rows; `GetInt64` on it throws `InvalidOperationException`. Step that failed: callers reading a NULL blob column normally gate on `IsDBNull` first, and the pre-change code failed the same query worse (wrong table's rowid); no new emergent outcome.
- **`sqlite3_table_column_metadata` called with NULL db/table/column names** when two expression blobs coexist (`SELECT randomblob(16), randomblob(16)`) — origin names are all NULL and the guards pass NULLs through. Could not confirm the C API's behavior on a NULL table name statically (anchor 25); also pre-existing on first call, and the repetition aspect is subsumed by the negative-cache finding.
- **Dictionary double-Add / concurrent GetStream** — `Add` sites are each followed by `break` and guarded by the same-call `TryGetValue` miss; cross-thread use violates the DbDataReader thread-safety contract. Scenario fell apart at the "legitimate usage" step.
- **Cache staleness across result sets** — verified `SqliteDataReader.NextResult` disposes and recreates `SqliteDataRecord` (line 180 of `/home/decaf/code/decaf-claude/competition/benchmark/repos/1/src/Microsoft.Data.Sqlite.Core/SqliteDataReader.cs`), so `RowIds` cannot leak stale ordinals across statements. No scenario.
- **Scan loop matching a foreign table's `rowid`** (dispatch prompt's question) — verified not an issue: the db/table guards at lines 339–349 run before the `columnName == "rowid"` check, so only same-table columns are considered.
