# subagent agent-a64ddaa6b84629561

Depth: standard — ~40 executable lines changed in a data-access hot path (blob streaming with cache + per-call SQL). All four techniques applied; no cascade beyond the scan-repetition chain.

I read the full post-change method and the diff against the prior `_rowidOrdinal` implementation. Findings below.

```json
[
  {
    "file": "src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs",
    "line": 329,
    "severity": "High",
    "category": "performance",
    "issue": "[ADV_ABUSE] Blob column on a WITHOUT ROWID / expression source → rowIdForOrdinal stays null → nothing added to RowIds → every GetStream call across every row re-runs the full FieldCount metadata scan AND the 'SELECT COUNT(*) FROM pragma_table_info' query; reading such a column over N rows executes N extra SQL queries + N×FieldCount native metadata calls.",
    "fix": "Cache the negative result too: insert a sentinel into RowIds for rowidkey when the scan finds no rowid (mirror the old _rowidOrdinal = -1 memoization), and treat the sentinel as the MemoryStream fallback path.",
    "confidence": 100,
    "pre_existing": false
  },
  {
    "file": "src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs",
    "line": 328,
    "severity": "High",
    "category": "other",
    "issue": "[ADV_COMPOSITION] Ambiguous cache key: $\"{db}_{table}\" collides across distinct sources. ATTACH a schema named \"main_a\" holding table \"b\", plus a main table named \"a_b\"; a JOIN selecting a blob from each yields identical key \"main_a_b\". Whichever resolves first caches its rowid *ordinal*; the second reuses that ordinal, so rowid = GetInt64(wrong ordinal) → SqliteBlob built with the correct db/table/column but the wrong rowid → silently wrong blob content, or a reincarnation of the original 'no such rowid' error.",
    "fix": "Use a delimiter that cannot appear via concatenation ambiguity, or key on a tuple/composite key (ValueTuple<string,string> or an escaped separator) instead of interpolating db and table with a bare underscore.",
    "confidence": 75,
    "pre_existing": false
  },
  {
    "file": "src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs",
    "line": 393,
    "severity": "Medium",
    "category": "error-handling",
    "issue": "[ADV_ASSUMPTION] Debug.Assert(rowIdForOrdinal != null) fires on the legitimate no-rowid path. e.g. CREATE TABLE t(a,b,data BLOB, PRIMARY KEY(a,b)) WITHOUT ROWID; SELECT data FROM t → scan finds no rowid, rowIdForOrdinal is null by design, the very next lines handle null via MemoryStream fallback — but the assert breaks/crashes Debug builds first. The old code pre-seeded _rowidOrdinal = -1 so its assert never tripped; this is a new regression.",
    "fix": "Remove the assert, or gate it so it only fires when a rowid was expected. The null case is a supported outcome, not an invariant violation.",
    "confidence": 100,
    "pre_existing": false
  }
]
```

## Considered But Not Flagged

- **Empty db+table names ("_" key) aliasing distinct sources into one wrong rowid.** For expression/computed blob columns `sqlite3_column_table_name` is null → key "_". Traced it: such columns have no origin table, so the resolve loop finds no rowid column and no single-INTEGER-PK match → the negative (MemoryStream) path, not a wrong-rowid path. I could not construct a concrete case where an *empty-table* key actually resolves a rowid ordinal from a mismatched table, so no data-corruption scenario survives — it collapses into Finding 1 (repeated scan). The real correctness collision is the non-empty underscore case (Finding 2).

- **`pragma_table_info` command executed on `_connection` while the reader is mid-enumeration.** Pre-existing (present in old code); SQLite supports concurrent statements on one connection, and no new failure step is introduced by this change.

- **`RowIdInfo.TableName` is stored but never read in `GetStream`.** Dead field, not a failure scenario — no traced bad outcome.

### Probe Requests
- None required; all findings are constructible from the source and diff already read.
