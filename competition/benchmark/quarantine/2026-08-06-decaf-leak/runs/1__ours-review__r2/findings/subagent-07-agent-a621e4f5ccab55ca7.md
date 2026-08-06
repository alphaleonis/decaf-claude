# subagent agent-a621e4f5ccab55ca7

The `ReportFindings` tool schema doesn't match the output format specified in my instructions (which call for a plain JSON array with `file`/`line`/`severity`/`category`/`issue`/`fix`/`confidence`/`pre_existing`). Producing the final report as specified text instead.

```json
[
  {
    "file": "src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs",
    "line": 393,
    "severity": "High",
    "category": "null-safety",
    "issue": "[DOTNET_NULLABILITY] Debug.Assert(rowIdForOrdinal != null) asserts a false invariant. The scan loop above legitimately leaves rowIdForOrdinal null whenever the blob's table has no single-column INTEGER PRIMARY KEY (composite PK, non-integer PK, or WITHOUT ROWID table), and the very next statement (line 396, `if (rowIdForOrdinal == null)`) explicitly treats that as a normal, non-exceptional outcome, falling back to a cached-blob MemoryStream. The assert directly contradicts the null-check that immediately follows it.",
    "fix": "Remove the Debug.Assert (the subsequent null-check already documents and handles this as a legitimate outcome), or replace it with a comment explaining that null is expected for tables without a single-column INTEGER PK.",
    "confidence": 100,
    "pre_existing": false
  },
  {
    "file": "src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs",
    "line": 329,
    "severity": "Medium",
    "category": "other",
    "issue": "[DOTNET_NULLABILITY] The no-rowid outcome is never cached in RowIds — RowIds.Add is only reached on the two success branches (lines 355, 387). The previous implementation cached the negative result via the `-1` sentinel in `int? _rowidOrdinal`, so the scan ran once per statement. Now every GetStream call on a blob column of a table lacking a single-column INTEGER PK re-runs the full FieldCount scan, re-issues sqlite3_table_column_metadata calls, and re-creates/executes a SqliteCommand (`pragma_table_info`) for each candidate PK column — turning a one-time cost into a per-call cost, and (compounding the finding above) re-triggering the incorrect Debug.Assert on every call instead of once.",
    "fix": "Cache the negative result too, e.g. change to `Dictionary<string, RowIdInfo?>` and `RowIds.Add(rowidkey, null)` when no rowid is found, checking the cached null before re-scanning — restoring the memoization the old `-1` sentinel provided.",
    "confidence": 75,
    "pre_existing": false
  },
  {
    "file": "src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs",
    "line": 39,
    "severity": "Low",
    "category": "other",
    "issue": "[DOTNET_NULLABILITY] `RowIds` breaks the file's established field convention — every sibling field is `private` and `_camelCase` (e.g. `_columnNameOrdinalCache`, `_stepped`, `_blobCache`), while `RowIds` is neither `private` nor underscore-prefixed, widening its accessibility/visibility relative to the other per-instance caches in this internal class and drifting from the established nullable-cache-field pattern those siblings follow.",
    "fix": "Rename to `_rowIds` and mark it `private readonly` to match sibling cache fields.",
    "confidence": 75,
    "pre_existing": false
  },
  {
    "file": "src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs",
    "line": 23,
    "severity": "Low",
    "category": "type-safety",
    "issue": "[DOTNET_NULLABILITY] `RowIdInfo.TableName` is a non-nullable, publicly mutable auto-property (`{ get; set; }`) set only via the constructor and never read anywhere in this file — GetStream uses the local `blobTableName`/`tableName` values directly at line 404, not `rowIdForOrdinal.TableName`. It is dead state on what otherwise looks like an immutable cache-entry type, and the settable property lets callers mutate a cached lookup value with no consequence, undermining the type's role as a fixed cache record.",
    "fix": "Either drop TableName from RowIdInfo if genuinely unused, or if kept for future use, make it get-only (or convert RowIdInfo to a `record`/`readonly struct`) so a cached entry can't be silently mutated after insertion.",
    "confidence": 50,
    "pre_existing": false
  }
]
```

## Considered But Not Flagged

- **`_stepped`/state ordering, thread-safety of `RowIds`**: `SqliteDataRecord` is not documented as thread-shared (single-reader ADO.NET pattern, consistent with sibling caches like `_columnNameOrdinalCache` also being unsynchronized `Dictionary<>`). No new thread-safety exposure beyond what already exists for the other unsynchronized per-instance caches — not this changeset's regression.
- **`RowIdInfo` as class vs. record/struct**: a value-semantics type (`readonly record struct` or plain `record`) would be a better fit for an immutable cache entry, but this is a design/idiom-preference call with no nameable behavioral consequence beyond the `TableName` mutability point already flagged (capped at confidence 50, folded into that finding rather than reported twice).
- **Key construction `$"{blobDatabaseName}_{blobTableName}"`**: could collide if a database or table name itself contains `_` in an ambiguous way (e.g. db `"a"`, table `"b_c"` vs db `"a_b"`, table `"c"`), but this is a general string-composition/collision bug rather than .NET-specific idiom misuse — out of this reviewer's scope (would belong to quick-reviewer).
- **`Debug.Assert` compiling out in Release**: noted as context for severity (the assert issue doesn't crash Release-configured NuGet consumers), not a separate finding.

### Probe Requests

None — repo already checked out locally; grepped for `TableName`/`RowIds`/`GetStream`/`Debug.Assert` usages across the file to confirm dead-state and reachability claims (read-only, no tracked files modified).
