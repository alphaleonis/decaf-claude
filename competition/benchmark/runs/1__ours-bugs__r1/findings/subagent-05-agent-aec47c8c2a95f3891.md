# subagent agent-aec47c8c2a95f3891

## Analysis

I've read the full file and traced through the logic. Here are the .NET-idiom defects introduced by this change:

### Critical Finding: Debug.Assert Contradiction

**Lines 393–396**: The assertion contradicts the next line's null-check handler:

```csharp
Debug.Assert(rowIdForOrdinal != null);  // L393
...
if (rowIdForOrdinal == null)  // L396
{
    return new MemoryStream(GetCachedBlob(ordinal), false);
}
```

The assertion fires on a **legitimate code path**: when a blob's table exposes no `rowid` column and no single-column INTEGER primary key, the search loop completes without finding one, leaving `rowIdForOrdinal == null`. This is a supported case (returns a cached blob via `MemoryStream`). In DEBUG builds, the assertion crashes the process; in RELEASE, it's stripped and the fallback executes. The code works in production but fails under debugging/testing.

**Root cause**: The assert was meant to document the invariant "we always find a rowid or INTEGER PK," but the code path that finds neither is real and handled. The assertion is logically wrong.

---

### High Finding: NRT Violation on RowIdInfo.TableName

**Line 23**: `RowIdInfo.TableName` is declared non-nullable `string`:

```csharp
public string TableName { get; set; }
```

But it's populated from `utf8_to_string()` (lines 354, 386), which returns nullable `string?`. Evidence from line 125–126 in `GetName()` shows `utf8_to_string()` can return null:

```csharp
var name = _columnNameCache?[ordinal] ?? sqlite3_column_name(Handle, ordinal).utf8_to_string();
if (name == null  // <- null-check required
```

The field's NRT annotation lies: it claims non-nullable, but accepts potentially-null assignments. This breaks static null-safety guarantees.

---

### Medium Finding: Field Naming Convention Violation

**Line 39**: `readonly Dictionary<string, RowIdInfo> RowIds` uses PascalCase without underscore prefix. Sibling fields in the class all follow `camelCase_underscore` pattern (`_connection`, `_addChanges`, `_blobCache`, `_typeCache`, `_columnNameCache`, `_stepped`, etc.). Should be `_rowIds`.

---

### Low Finding: Dead Code

**Line 23**: `RowIdInfo.TableName` is never read after assignment. It's set in the constructor (line 28) but never accessed. This is unused dead code. Either remove it or document it as reserved for future use.

---

## Considered But Not Flagged

- **Thread-safety of Dictionary**: The check-then-add pattern on `RowIds` (lines 329–356) is unsynchronized. However, the old code with `int? _rowidOrdinal` had the same property. `SqliteDataRecord` wraps a statement handle, which is single-threaded per instance by SQLite contract. Not a new violation introduced by this change.

- **Disposal of SqliteDataRecord**: Class implements `IDisposable` and disposes the statement handle. No disposal leaks introduced by the change.

---

## Report

```json
[
  {
    "file": "src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs",
    "line": 393,
    "severity": "Critical",
    "category": "error-handling",
    "issue": "[DOTNET_EXCEPTIONS] Debug.Assert(rowIdForOrdinal != null) contradicted by immediate null-check handler; assertion crashes in DEBUG builds on valid blob-with-no-rowid paths, violating code symmetry between DEBUG and RELEASE",
    "fix": "Remove the assertion; the null case is legitimate and handled on line 396. If the invariant is that we *should* find a rowid, instead add explicit logic to cache a sentinel value (-1 or similar) to avoid the null check, or restructure to make the null case impossible by design",
    "confidence": 100,
    "pre_existing": false
  },
  {
    "file": "src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs",
    "line": 23,
    "severity": "High",
    "category": "null-safety",
    "issue": "[DOTNET_NULLABILITY] RowIdInfo.TableName declared non-nullable string but receives potentially-null values from utf8_to_string(); NRT annotation is a lie. Evidence: GetName() at line 125 null-checks the same utf8_to_string() result",
    "fix": "Change property to `public string? TableName { get; set; }` to accurately reflect that it can be null, or guarantee via contract that sqlite3_column_table_name never returns NULL (add asserts if guaranteed)",
    "confidence": 75,
    "pre_existing": false
  },
  {
    "file": "src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs",
    "line": 39,
    "severity": "Medium",
    "category": "type-safety",
    "issue": "[DOTNET_NULLABILITY] Field naming violates class convention; RowIds uses PascalCase without underscore, breaking pattern set by _connection, _addChanges, _blobCache, _typeCache, _columnNameCache, etc.",
    "fix": "Rename `RowIds` to `_rowIds` to match private-field convention",
    "confidence": 100,
    "pre_existing": false
  },
  {
    "file": "src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs",
    "line": 23,
    "severity": "Low",
    "category": "other",
    "issue": "[DOTNET_NULLABILITY] RowIdInfo.TableName property is populated in constructor but never read anywhere in the codebase; dead code",
    "fix": "Remove the TableName property unless reserved for future use (document if kept)",
    "confidence": 100,
    "pre_existing": false
  }
]
```

---

## Considered But Not Flagged

- **Thread-safety of Dictionary cache**: The `TryGetValue` + `Add` pattern on `_rowIds` is unsynchronized; concurrent calls to `GetStream()` on the same instance could race. However, this matches the thread-safety contract of the old `int? _rowidOrdinal` field (simple field reads/writes are also unsynchronized). `SqliteDataRecord` wraps a statement handle (single-threaded per instance by SQLite design), so contention is not expected. Not a new hazard introduced by the change.
