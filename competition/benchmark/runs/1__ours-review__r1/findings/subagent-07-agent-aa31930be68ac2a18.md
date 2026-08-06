# subagent agent-aa31930be68ac2a18

```json
[
  {
    "file": "src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs",
    "line": 393,
    "severity": "High",
    "category": "other",
    "issue": "[BUG_LOGIC] `Debug.Assert(rowIdForOrdinal!=null)` now fires for a legitimate, already-handled case",
    "fix": "Before this change, `_rowidOrdinal` was pre-initialized to `-1` so `Debug.Assert(_rowidOrdinal.HasValue)` was always trivially true (a no-op assert). After the refactor, `rowIdForOrdinal` starts as `null` and stays `null` whenever the target table has no rowid alias and no single-column INTEGER PRIMARY KEY (e.g. a `WITHOUT ROWID` table, a composite primary key, or no primary key at all). That is a supported path — the very next `if (rowIdForOrdinal == null)` block (line 396) falls back to `GetCachedBlob`/`MemoryStream` for exactly this case. So the assert will now fail on a legitimate, intentionally-handled scenario, which in Debug builds/test runs can abort or fail the run. Remove the assert, or change it to assert something that's actually always true post-loop (e.g. drop it entirely since the null branch below is the real handling for 'no rowid found').",
    "confidence": 100,
    "pre_existing": false
  },
  {
    "file": "src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs",
    "line": 329,
    "severity": "Medium",
    "category": "performance",
    "issue": "[BUG_LOGIC] Negative result ('no rowid for this table') is no longer cached, causing repeated expensive lookups",
    "fix": "Previously `_rowidOrdinal = -1` was cached once the 'no usable rowid' conclusion was reached, so subsequent `GetStream`/`GetBytes` calls on the same table skipped the O(FieldCount) scan and the `SELECT COUNT(*) FROM pragma_table_info($table)` round-trip (line 375-381). With the new `Dictionary<string, RowIdInfo>`, nothing is added to `RowIds` when no rowid column is found (both `RowIds.Add` calls only happen inside the `break` branches), so every future call for that database+table re-runs the full metadata scan and re-executes the pragma_table_info SQL query. Cache the negative result too, e.g. by storing a nullable/sentinel entry in the dictionary (or a separate `HashSet<string>` of 'no rowid' keys) so the lookup is only performed once per table.",
    "confidence": 75,
    "pre_existing": false
  },
  {
    "file": "src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs",
    "line": 39,
    "severity": "Low",
    "category": "naming",
    "issue": "[CONVENTION_VIOLATION] New field `RowIds` breaks the file's private-field naming convention",
    "fix": "Every other field in this class is `private` and uses the `_camelCase` prefix (`_connection`, `_blobCache`, `_typeCache`, `_columnNameOrdinalCache`, `_stepped`, `_alreadyThrown`, ...). The new field is declared `readonly Dictionary<string, RowIdInfo> RowIds = ...` — no `private` modifier and PascalCase, which reads as a public member. Rename to `_rowIds` and add the explicit `private` modifier for consistency with the rest of the file.",
    "confidence": 100,
    "pre_existing": false
  },
  {
    "file": "src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs",
    "line": 328,
    "severity": "Medium",
    "category": "other",
    "issue": "[BUG_LOGIC] Composite cache key built by naive string concatenation can collide across distinct database/table pairs",
    "fix": "`$\"{blobDatabaseName}_{blobTableName}\"` is ambiguous: e.g. database `\"main\"` + table `\"foo_bar\"` produces the same key (`\"main_foo_bar\"`) as database `\"main_foo\"` + table `\"bar\"`. Underscore-separated table/database names are common (e.g. attached databases, snake_case tables), so two distinct blob columns could end up sharing (and corrupting) each other's cached rowid ordinal — reintroducing a milder version of the exact cross-table ordinal mixup this PR is fixing. Use an unambiguous composite key, e.g. a tuple key (`(string, string)` via a `ValueTuple`-keyed dictionary) or an escaped/length-prefixed string.",
    "confidence": 50,
    "pre_existing": false
  },
  {
    "file": "src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs",
    "line": 23,
    "severity": "Low",
    "category": "unused-code",
    "issue": "[QUALITY_DUPLICATION] `RowIdInfo.TableName` is stored but never read",
    "fix": "`RowIdInfo` carries a `TableName` property that is populated at both construction sites (lines 354, 386) but only `.Ordinal` is ever read (line 402). Either remove the unused property or use it (e.g. as part of a safer composite cache key, addressing the collision issue above) to justify keeping it.",
    "confidence": 75,
    "pre_existing": false
  }
]
```

## Considered But Not Flagged

- **Extra blank line inserted at line 17** (inside `namespace Microsoft.Data.Sqlite {`): pure whitespace noise, no behavioral or convention impact — too trivial to report.
- **`RowIdInfo? rowIdForOrdinal = null;` initializer immediately overwritten by the `out` parameter on the next line**: redundant but harmless; stylistic only, below the reporting threshold.
- **Mutable public setters on `RowIdInfo` (`Ordinal`, `TableName`)**: could be constructor-only/get-only for tighter encapsulation, but the type is `internal`, short-lived, and never mutated after construction — speculative nice-to-have, not a defect.
- **Thread-safety of the new `Dictionary<string, RowIdInfo>`**: not thread-safe under concurrent access, but this matches the original single-field design (`_rowidOrdinal` was likewise unsynchronized) and `SqliteDataRecord` instances are not documented/used concurrently — pre-existing assumption, not a regression introduced by this diff.
- **`GetBytes` regression for the JOIN scenario**: verified via full file read that `GetBytes` (line 274) delegates to `GetStream`, so the fix and any issues found apply uniformly; no separate duplicated logic path exists to flag.
