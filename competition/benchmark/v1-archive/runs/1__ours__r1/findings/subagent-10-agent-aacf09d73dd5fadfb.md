# subagent agent-aacf09d73dd5fadfb

## Findings

```json
[
  {
    "file": "src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs",
    "line": 393,
    "severity": "High",
    "category": "error-handling",
    "issue": "[DOTNET_EXCEPTIONS] Debug.Assert now checks a genuinely reachable runtime condition instead of a true invariant. The old code unconditionally set `_rowidOrdinal = -1` before the scan loop, so `Debug.Assert(_rowidOrdinal.HasValue)` was tautologically always true (it only asserted 'a value was assigned', never 'a rowid was found'). The refactor dropped that unconditional sentinel assignment: `rowIdForOrdinal` now stays `null` unless the loop actually finds a rowid/single-column integer PK. The very next lines (`if (rowIdForOrdinal == null) return new MemoryStream(GetCachedBlob(ordinal), false);`) prove this null outcome is a legitimate, pre-existing fallback path (e.g. WITHOUT ROWID tables, composite primary keys, views) rather than a programming error. In Debug/Checked builds, hitting that legitimate path now trips a failed assertion on every affected blob read.",
    "fix": "Either stop asserting non-invariant runtime state (drop the Debug.Assert here, since 'no rowid found' is an expected, handled outcome), or restore the old sentinel semantics by caching the negative result too (e.g. a `Dictionary<string, RowIdInfo?>` with a cached null/sentinel entry per table) so the assert reflects 'we always resolve the loop to a definite answer' rather than 'we always found a rowid'.",
    "confidence": 75,
    "pre_existing": false
  },
  {
    "file": "src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs",
    "line": 39,
    "severity": "Low",
    "category": "other",
    "issue": "[FIELD_CONVENTIONS] New field `RowIds` uses PascalCase and no explicit access modifier, diverging from every other private field in this class (`_blobCache`, `_typeCache`, `_columnNameOrdinalCache`, etc., all `private _camelCase`). PascalCase without a modifier reads like a public member at a glance and is inconsistent with the surrounding code's own convention.",
    "fix": "Rename to `_rowIds` and declare it `private readonly Dictionary<string, RowIdInfo> _rowIds = new();` to match the class's existing field style.",
    "confidence": 100,
    "pre_existing": false
  },
  {
    "file": "src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs",
    "line": 20,
    "severity": "Low",
    "category": "other",
    "issue": "[FIELD_CONVENTIONS] `RowIdInfo` exposes `Ordinal`/`TableName` as `{ get; set; }` even though every instance is fully initialized once via its constructor and never mutated afterward — the mutability is unused and invites accidental post-construction writes.",
    "fix": "Make the properties get-only (`public int Ordinal { get; }`) or declare `RowIdInfo` as a `readonly record class RowIdInfo(int Ordinal, string TableName);` for value-based, immutable semantics.",
    "confidence": 50,
    "pre_existing": false
  }
]
```

## Considered But Not Flagged

- **Dictionary key collision via unescaped concatenation** (`$"{blobDatabaseName}_{blobTableName}"`, line 328): a table `A_B` in database `main` and a table `B` in database `main_A` both hash to key `"main_A_B"`, which could silently reproduce the exact cross-table rowid-ordinal bug this PR fixes. Real but this is a generic string-key-collision bug anyone could spot regardless of .NET knowledge (the idiomatic .NET fix — a value-tuple `(string, string)` key — is a nicety, not what makes the bug real) — out of my scope, belongs to quick-reviewer/broad-reviewer.
- **Missing negative-result caching**: when no rowid/PK column is found, nothing is added to `RowIds`, so the full O(FieldCount) scan (including the `pragma_table_info` round-trip) reruns on every `GetStream` call for that table, unlike the old code where `_rowidOrdinal = -1` permanently cached the negative result. This is a real regression but it's a cost/repeated-work issue with no data-corruption consequence — performance-reviewer's territory, not flagged here.
- **`RowIdInfo.TableName` is a dead field** — stored but never read anywhere in the file (only `.Ordinal` is used at line 402). Not a .NET-semantics issue, just unused code — out of scope (simplify/quick-reviewer).
- **`tableName` passed into `RowIdInfo` may be `string?` under a `string`-typed constructor parameter** (nullable-enabled project, and `sqlite3_column_table_name(...).utf8_to_string()` is demonstrably nullable elsewhere in this same file, e.g. `GetName`'s null-check). This mirrors a pattern that already exists pre-PR (`blobTableName` is passed into `SqliteBlob`'s non-nullable `string tableName` parameter unchanged by this diff), and the value is never dereferenced since `TableName` is otherwise unused — no live failure scenario, so not flagged as a standalone finding.
- **Thread-safety of `RowIds`**: unsynchronized `Dictionary` access, but `SqliteDataRecord`/ADO.NET readers are single-threaded-use by contract both before and after this change — no new risk introduced.
- **`SqliteDataRecord` lifetime scoping of the new cache**: verified via `SqliteDataReader.cs` that a fresh `SqliteDataRecord` (and thus a fresh `RowIds` dictionary) is created per `NextResult()`/statement, so no stale cross-statement ordinal reuse — not an issue.
- Minor formatting nit (`Debug.Assert(rowIdForOrdinal!=null)` missing spaces around `!=`) — cosmetic, would be caught by a formatter/linter, not a semantics issue.

### Probe Requests
None — the Debug.Assert finding is decisive from static reasoning (comparing the pre- and post-diff sentinel logic directly), and no .NET SDK is available in this environment to execute a probe.
