# subagent agent-a30408d7e66e83994

## Code Review Findings

```json
[
  {
    "file": "src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs",
    "line": 393,
    "severity": "High",
    "category": "other",
    "issue": "[BUG_LOGIC] `Debug.Assert(rowIdForOrdinal!=null)` now fires for legitimate tables that have no identifiable rowid (WITHOUT ROWID tables, composite primary keys, views). The old code always satisfied this assert because it explicitly cached the negative result (`_rowidOrdinal = -1`) before the assert ran. The new code only populates `rowIdForOrdinal`/`RowIds` inside the `columnName == \"rowid\"` or `pkColumns == 1L` branches; if the scan never matches either, the loop exits with `rowIdForOrdinal` still null and nothing added to `RowIds`, so the assert is reached with a false condition. That the pre-change code explicitly special-cased this ('no rowid found' → cache `-1`) is direct evidence this path is reachable in real usage, not theoretical.",
    "fix": "Cache the negative ('no rowid for this table') result explicitly before the assert — e.g. wrap the found ordinal in a nullable-tolerant cache entry or a separate 'not found' set — so the invariant the assert checks always holds, mirroring the old `_rowidOrdinal = -1` behavior.",
    "confidence": 100,
    "pre_existing": false
  },
  {
    "file": "src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs",
    "line": 329,
    "severity": "Medium",
    "category": "performance",
    "issue": "[BUG_LOGIC] The 'no rowid found for this table' result is no longer cached in `RowIds`, unlike the pre-change code which cached `_rowidOrdinal = -1`. Every subsequent `GetStream` call for a BLOB column in a table without a rowid re-runs the full `FieldCount` column scan and can re-issue a `pragma_table_info` COUNT query (via a new `SqliteCommand`) on every single call instead of once.",
    "fix": "Store a sentinel/negative entry in `RowIds` (or a separate 'not found' set) after the loop completes without a match, so the expensive scan/metadata query runs at most once per table.",
    "confidence": 90,
    "pre_existing": false
  },
  {
    "file": "src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs",
    "line": 328,
    "severity": "Low",
    "category": "other",
    "issue": "[BUG_LOGIC] The cache key `$\"{blobDatabaseName}_{blobTableName}\"` uses a bare underscore separator with no escaping, so two distinct (database, table) pairs can collide, e.g. database `main_foo` + table `bar` and database `main` + table `foo_bar` both produce key `main_foo_bar`. A collision would return the wrong cached rowid ordinal for a table, silently producing an incorrect rowid lookup / wrong blob.",
    "fix": "Use a non-collidable composite key, e.g. a `(string, string)` tuple as the dictionary key, instead of string concatenation with a separator that can legally appear in identifiers.",
    "confidence": 50,
    "pre_existing": false
  },
  {
    "file": "src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs",
    "line": 39,
    "severity": "Low",
    "category": "naming",
    "issue": "[CONVENTION_VIOLATION] The new field `RowIds` lacks an explicit accessibility modifier and uses PascalCase instead of the project's `_camelCase` private-field style. The repo's `.editorconfig` sets `dotnet_style_require_accessibility_modifiers = always:suggestion`, and every sibling field in this same class (`_stepped`, `_alreadyThrown`, `_columnNameCache`, etc.) is declared `private` with an underscore-prefixed camelCase name.",
    "fix": "Declare as `private readonly Dictionary<string, RowIdInfo> _rowIds = new();` to match the surrounding fields and the project's naming/accessibility conventions.",
    "confidence": 75,
    "pre_existing": false
  },
  {
    "file": "src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs",
    "line": 23,
    "severity": "Low",
    "category": "unused-code",
    "issue": "[QUALITY_DUPLICATION] `RowIdInfo.TableName` is assigned at both construction sites but never read anywhere afterward — only `.Ordinal` is used (line ~401). It's dead state carried on every cache entry.",
    "fix": "Remove the unused `TableName` property/constructor parameter from `RowIdInfo`, or use it for something meaningful.",
    "confidence": 75,
    "pre_existing": false
  }
]
```

## Considered But Not Flagged

- **Thread-safety of the new `Dictionary<string, RowIdInfo>` field**: it's per-instance state on `SqliteDataRecord`, same lifetime/ownership model as the field it replaced (`_rowidOrdinal`). No new concurrency exposure introduced by this change.
- **`RowIdInfo?` nullable pattern / redundant `= null` initializer before `TryGetValue`**: stylistic only, not a functional issue; `TryGetValue`'s `out` parameter overwrites it unconditionally on both branches.
- **`RowIdInfo` having public mutable setters (`{ get; set; }`)**: a type-design smell, but out of scope for this reviewer (falls under design-reviewer's territory for nested-type design, not a line-level bug).
- **Missing test coverage for the "no rowid found" path** (the one that now trips the Debug.Assert): real gap, but test-quality/coverage judgments are test-reviewer's scope, not mine — flagging only the underlying code defect above.

Root cause worth restating for the fix: this PR's stated goal was to stop reusing one global rowid ordinal across tables in a join — that part of the fix is sound. But in doing so, it dropped the explicit "not found" caching that the original single-ordinal design relied on to keep `Debug.Assert(_rowidOrdinal.HasValue)` always true. That is the direct cause of both the assert regression (finding 1) and the lost caching for the not-found path (finding 2).
