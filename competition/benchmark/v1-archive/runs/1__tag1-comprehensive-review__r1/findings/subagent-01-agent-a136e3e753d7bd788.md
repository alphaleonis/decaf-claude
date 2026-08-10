# subagent agent-a136e3e753d7bd788

## Review Scope

Reviewed `git diff HEAD^..HEAD` (PR #32770) against `src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs` (full file read for surrounding conventions) and the added test in `test/Microsoft.Data.Sqlite.Tests/SqliteDataReaderTest.cs`. Cross-checked against `.editorconfig` naming/formatting rules and pre-existing tests in the same test file.

---

## Critical (90-100)

### 1. `Debug.Assert` now asserts something false on an existing, legitimate code path — breaks the pre-existing `GetStream_works_when_composite_pk` test in Debug builds
**File:** `src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs:393` (also see the fallback at :396-399)
**Confidence: 95**

```csharp
Debug.Assert(rowIdForOrdinal!=null);
...
if (rowIdForOrdinal == null)
{
    return new MemoryStream(GetCachedBlob(ordinal), false);
}
```

Before this PR, `_rowidOrdinal` was pre-seeded with a sentinel (`-1`) before the search loop, so `Debug.Assert(_rowidOrdinal.HasValue)` was always trivially true — it was a no-op. This PR changed the assert to check that `rowIdForOrdinal` (the new, unseeded local) is non-null, but the very next `if` block explicitly handles `rowIdForOrdinal == null` as a valid, expected outcome (tables without a single-column integer rowid: composite PKs, `WITHOUT ROWID` tables, views, etc.).

This is not hypothetical: the unmodified, pre-existing test `GetStream_works_when_composite_pk` (`test/Microsoft.Data.Sqlite.Tests/SqliteDataReaderTest.cs:516-541`) queries a table with `PRIMARY KEY (Id1, Id2)` and no `rowid` column selected — exactly the scenario where the loop legitimately never sets `rowIdForOrdinal`. Tracing the logic: `pkColumns` resolves to `2` (two PK columns), so `pkColumns == 1L` is never true, and `rowIdForOrdinal` remains `null` after the loop, so this assert fires in Debug builds against this passing test.

**Fix:** delete the assert (it no longer holds any invariant — the following `if` already handles both cases), or replace it with something that's actually meaningful, if any invariant needs restating.

---

## Important (80-89)

### 2. Negative lookups are no longer cached — performance regression for repeated `GetStream`/`GetBytes` calls on non-rowid blob columns
**File:** `src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs:329-394`
**Confidence: 85**

The old code cached the "no rowid found" outcome permanently via the sentinel `_rowidOrdinal = -1`, so subsequent calls took the fast path straight to `MemoryStream`. The new code only calls `RowIds.Add(...)` on the two *success* paths (lines 355, 387); the "not found" case is never memoized. Since `GetBytes` (line 274-286) calls `GetStream` on every invocation, and callers commonly call `GetBytes` repeatedly to stream a blob in chunks, every chunk read on a composite-PK/no-rowid table will re-scan all `FieldCount` columns and, for tables with an integer PK column that isn't a lone PK (e.g. composite PK), re-issue a `SELECT COUNT(*) FROM pragma_table_info(...)` command via a brand-new `SqliteCommand` on *every single call*. This is a real perf regression versus the prior behavior.

**Fix:** cache the negative result too, e.g. store a nullable `RowIdInfo?` in the dictionary (or a separate "known not found" set) keyed the same way, so the expensive scan only runs once per (database, table).

### 3. New field breaks the established private-field naming convention in this class
**File:** `src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs:39`
**Confidence: 82**

```csharp
readonly Dictionary<string, RowIdInfo> RowIds = new Dictionary<string, RowIdInfo>();
```

Every other field in this class is `private` + `_camelCase` (`_blobCache`, `_typeCache`, `_columnNameOrdinalCache`, `_columnNameCache`, `_stepped`, the removed `_rowidOrdinal`, `_alreadyThrown`, `_alreadyAddedChanges`). This new field drops the explicit `private` modifier and uses `PascalCase`, which is inconsistent with every sibling field and with the `_camelCase` private-field style already defined in `.editorconfig` (line 194-195). It reads like a public API member even though it's implementation detail.

**Fix:** `private readonly Dictionary<string, RowIdInfo> _rowIds = new();`

### 4. Composite dictionary key built by naive string concatenation risks collisions between distinct (database, table) pairs
**File:** `src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs:328`
**Confidence: 72**

```csharp
string rowidkey = $"{blobDatabaseName}_{blobTableName}";
```

Using `"_"` as a separator between two identifier strings that can themselves legally contain underscores (attached database names, table names) can cause two different `(database, table)` pairs to hash to the same key (e.g. db `"foo_bar"` + table `"baz"` vs. db `"foo"` + table `"bar_baz"`), silently resolving a blob's rowid against the wrong table. This is a new failure mode introduced by this PR's dictionary-keying approach (the old single-`_rowidOrdinal` design had no concept of composite keys at all).

**Fix:** use a value-tuple key, e.g. `Dictionary<(string Database, string Table), RowIdInfo>`, which has proper structural equality and avoids the ambiguity entirely.

---

## Minor / at-threshold (not required, included for completeness)

- `RowIdInfo.TableName` (`SqliteDataRecord.cs:23,28`) is stored but never read anywhere after construction — `blobTableName`/`blobDatabaseName` locals are used directly when constructing `SqliteBlob` at line 404. This looks like dead/vestigial state. (Confidence ~70 — borderline, flagged for awareness only.)

---

No issues found with the overall approach of keying rowid discovery per `(database, table)` to support joins — that fix itself is sound and matches the stated goal. The findings above are about the implementation's correctness (item 1, definite regression against an existing test) and its adherence to this file's established conventions (items 2-4).
