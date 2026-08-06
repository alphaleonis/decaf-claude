# subagent agent-ad21d207270f50a3a

## Sibling-Consistency Review — SqliteDataRecord.cs (PR #32770)

Sibling census built from `src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs` (all 9 pre-existing private fields, both existing constructor-assigned properties, both `TryGetValue` idiom siblings) plus repo-wide siblings for the `TryGetValue` idiom (`SqliteConnectionFactory.cs`, `SqliteValueBinder.cs`, `SqliteConnectionStringBuilder.cs`, `SQLitePCLExtensions.cs`) and for constructor-populated value types (`SqliteConnectionPoolGroup.cs`). Checked `.editorconfig` first and excluded anything it already governs (`dotnet_style_require_accessibility_modifiers`, `csharp_space_around_binary_operators`, `trim_trailing_whitespace`) — those belong to quick-reviewer, not this lane.

```json
[
  {
    "file": "src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs",
    "line": 39,
    "severity": "Low",
    "category": "naming",
    "issue": "[CONS_NAMING] New field `RowIds` breaks the file's private-field naming convention: every existing field uses an underscore-prefixed camelCase name — `_connection` (L32), `_addChanges` (L33), `_blobCache` (L34), `_typeCache` (L35), `_columnNameOrdinalCache` (L36), `_columnNameCache` (L37), `_stepped` (L38), `_alreadyThrown` (L41), `_alreadyAddedChanges` (L42). It also drops the `Cache` suffix that every other cache-purpose dictionary/array field in the class uses (`_blobCache`, `_typeCache`, `_columnNameOrdinalCache`, `_columnNameCache`), despite serving the exact same caching role for rowid lookups.",
    "fix": "Rename to `_rowIdCache` (or `_rowIdInfoCache`) to match the established `_camelCase` + `Cache`-suffix convention.",
    "confidence": 100,
    "pre_existing": false
  },
  {
    "file": "src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs",
    "line": 22,
    "severity": "Low",
    "category": "design",
    "issue": "[CONS_SYMMETRY] `RowIdInfo.Ordinal`/`RowIdInfo.TableName` are declared `{ get; set; }` even though they are assigned only once, in the constructor (L25-29), and never mutated afterward. The file's own convention for constructor-only-assigned properties is get-only: `public sqlite3_stmt Handle { get; }` (L61, set in ctor L46) and `public bool HasRows { get; }` (L63, set in ctor L47).",
    "fix": "Change both properties to `{ get; }` to match the `Handle`/`HasRows` convention in the same file.",
    "confidence": 100,
    "pre_existing": false
  },
  {
    "file": "src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs",
    "line": 327,
    "severity": "Low",
    "category": "design",
    "issue": "[CONS_HELPER] `RowIdInfo? rowIdForOrdinal = null;` is pre-declared then passed as `out rowIdForOrdinal` (L329), instead of using the inline `out var` idiom every other `TryGetValue` call site in this file and project uses: `_columnNameOrdinalCache.TryGetValue(name, out var ordinal)` (SqliteDataRecord.cs:150), plus `SqliteConnectionFactory.cs:56,66`, `SqliteValueBinder.cs:277`, `SqliteConnectionStringBuilder.cs:346,363,375,422`, `SQLitePCLExtensions.cs:29` — all use `out var x`.",
    "fix": "Drop the pre-declaration and write `if (!RowIds.TryGetValue(rowidkey, out var rowIdForOrdinal))` to match the established idiom.",
    "confidence": 100,
    "pre_existing": false
  },
  {
    "file": "src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs",
    "line": 328,
    "severity": "Low",
    "category": "naming",
    "issue": "[CONS_NAMING] Local variable `rowidkey` is an all-lowercase compound word, deviating from the camelCase-compound convention every other multi-word local in this method (and file) follows: `blobDatabaseName` (L324), `blobTableName` (L325), `tableName` (L345), `columnName` (L351), `blobColumnName` (L401).",
    "fix": "Rename to `rowIdKey` to match the camelCase-compound convention used by sibling locals in the same method.",
    "confidence": 100,
    "pre_existing": false
  }
]
```

## Considered But Not Flagged

- **Missing `private` modifier on `RowIds` (L39)**: deviates from sibling fields, but `.editorconfig:59` sets `dotnet_style_require_accessibility_modifiers = always` — this is a documented-standard violation, quick-reviewer's territory, not mine.
- **`Debug.Assert(rowIdForOrdinal!=null)` missing spaces around `!=` (L393)**: deviates from sibling comparisons in the same method (`databaseName != blobDatabaseName` L340, `tableName != blobTableName` L346, `primaryKey != 0` L371), but `.editorconfig:157` sets `csharp_space_around_binary_operators = before_and_after` — documented standard, quick-reviewer's territory.
- **Stray blank line with trailing whitespace after `namespace Microsoft.Data.Sqlite {` (L17)**: `.editorconfig:10` sets `trim_trailing_whitespace = true`, and the blank line itself is trivial scaffolding noise with no established "no blank line after namespace brace" convention to cite — closer to a mechanical formatting slip than a convention drift; left to quick-reviewer.
- **`new Dictionary<string, RowIdInfo>()` not using target-typed `new()` (L39)**: checked whether the file's convention favors target-typed `new`; it does not — every existing field initializer in the file uses the explicit-type form (`new Dictionary<string, int>()` L143, `new string[FieldCount]` L133, `new int?[FieldCount]` L223, `new byte[FieldCount][]` L493). The change is actually consistent with the file, not a deviation — not flagged.
- **`RowIdInfo` placement as a nested type at the very top of the class, before all fields (L20-30)**: no other nested type exists anywhere in this file to compare placement against — first-of-kind, no sibling to cite.
- **Redundant `= null` initializer combined with `out` (not `out var`) on L327**: the redundancy itself is a simplification/code-quality point, not a sibling-convention deviation — covered functionally by the `CONS_HELPER` idiom finding above; not double-counted as a separate finding.
