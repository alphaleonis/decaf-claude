# subagent agent-abe74afafcac458c6

I have the full file and context. This is the `#32770` fix replacing a single `int? _rowidOrdinal` with a per-table `Dictionary<string, RowIdInfo>`. Assessing the .NET-idiom surface.

## Findings

```json
[
  {
    "file": "src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs",
    "line": 23,
    "severity": "Low",
    "category": "null-safety",
    "issue": "[DOTNET_NULLABILITY] RowIdInfo.TableName is a non-nullable `string` auto-property, but it is only ever constructed from `sqlite3_column_table_name(...).utf8_to_string()` (line 345/354), which returns `string?` — the sibling code at GetName (line 126) explicitly null-checks the result of `utf8_to_string()`, confirming null is a real return value. The non-nullable annotation therefore lies: the property can hold null while the type system asserts it cannot. Impact is latent only because TableName is never read anywhere in the class (write-only dead field).",
    "fix": "Either type the property `string?` to match the true nullability of `utf8_to_string()`, or drop TableName entirely since it is never read (the RowIdInfo only needs Ordinal).",
    "confidence": 50,
    "pre_existing": false
  },
  {
    "file": "src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs",
    "line": 328,
    "severity": "Low",
    "category": "type-safety",
    "issue": "[DOTNET_LINQ] The cache key `$\"{blobDatabaseName}_{blobTableName}\"` builds a composite dictionary key by concatenating two attacker-uncontrolled-but-arbitrary schema identifiers with a single `_` delimiter, which is itself a legal identifier character. Distinct (database, table) pairs can collapse to the same key (e.g. db=`a_b`/table=`c` and db=`a`/table=`b_c` both yield `a_b_c`), and when both names are null (expression/computed columns, where utf8_to_string returns null) every such column collapses to the key `_`. A collision returns the wrong table's cached rowid ordinal for a subsequent GetStream, producing a SqliteBlob bound to the wrong row.",
    "fix": "Key the dictionary on a value tuple `(blobDatabaseName, blobTableName)` (ValueTuple<string?,string?> has correct structural equality and no delimiter ambiguity) instead of an interpolated string, or use a nested Dictionary keyed by database then table.",
    "confidence": 50,
    "pre_existing": false
  },
  {
    "file": "src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs",
    "line": 393,
    "severity": "Low",
    "category": "error-handling",
    "issue": "[DOTNET_EXCEPTIONS] `Debug.Assert(rowIdForOrdinal != null)` fires unconditionally after the scan loop on any cache-miss where no single-integer-primary-key/rowid column is found for the table. That is a legitimate runtime state (WITHOUT ROWID tables, views, aggregates), immediately handled two lines later by the `if (rowIdForOrdinal == null)` fallback — so the assert flags a supported path as a bug and will trip the debugger / fail Debug-configuration tests. The behavior is inherited from the prior `Debug.Assert(_rowidOrdinal.HasValue)`.",
    "fix": "Remove the assert (the null case is a valid, explicitly-handled outcome), or scope it to a branch where a rowid is genuinely guaranteed.",
    "confidence": 75,
    "pre_existing": true
  }
]
```

## Considered But Not Flagged

- **`RowIds` field: missing `private`, PascalCase, no target-typed `new`, always-constructed vs. lazy like sibling caches** — Real convention drift (`_blobCache`/`_typeCache` are `private`, underscore-camelCase, nullable-and-lazy). But these are style/consistency concerns with no correctness or platform-semantics consequence; they belong to consistency-reviewer, not this agent's scope. Idiom preference caps at anchor 50 with no nameable consequence, so not reported here.
- **Redundant `= null` init on the `out` variable (line 327)** — `out` parameters are definitely assigned by `TryGetValue` on both hit and miss; the explicit `null` init and the separate `RowIdInfo? rowIdForOrdinal = null` declaration are harmless dead initialization. No consequence; style only.
- **Ordinal, case-sensitive default string comparer for SQLite table names** — Raised in the prompt. Not a correctness bug here: the key is derived from `sqlite3_column_table_name`/`_database_name` on a fixed statement handle, and the in-loop filters (`databaseName != blobDatabaseName`, `tableName != blobTableName`) use the same ordinal comparison against the same API's output. Casing is internally consistent across calls on one handle, so no spurious miss or collision arises from case alone. (The delimiter collision above is the real key-construction risk, not the comparer.)
- **`Dictionary.Add` throws on duplicate key (lines 355, 387)** — Add is reached only inside the `if (!RowIds.TryGetValue(...))` miss block, at most once per call (loop `break`s after Add), and the record is per-reader single-threaded. The key is verified absent immediately before. Not reachable as a throw in the intended usage; would only matter under concurrent access, which is out of scope (see next).
- **`Dictionary` shared without synchronization / thread-unsafe** — `SqliteDataRecord` is internal, per-reader, and explicitly not documented thread-safe; all sibling caches (`_blobCache`, `_typeCache`, `_columnNameOrdinalCache`) are plain non-concurrent collections following the same single-threaded-owner pattern. `RowIds` matches the established, intended contract — no new threading violation introduced.
- **Negative lookups never cached → repeated full-column scans and repeated `ExecuteScalar` pragma_table_info queries per GetStream on no-single-PK tables** — A genuine cost (re-scan + re-query on every call for such columns), but this is throughput/latency, and the prior `int? _rowidOrdinal` design likewise never memoized the negative result, so it is not a regression. Performance-reviewer territory, not language-idiom misuse.
- **`blobDatabaseName`/`blobTableName` (nullable) passed into `new SqliteBlob(...)` (line 404)** — Only reached on the `rowIdForOrdinal != null` path, which implies a column whose db/table names matched the blob's, i.e. non-null in practice. Could not confirm a null-flow from the diff plus this file alone (SqliteBlob ctor not in scope); anchor 25, not reported.

### Probe Requests
None required — the review was completed read-only against the checked-out file; no probes needed.
