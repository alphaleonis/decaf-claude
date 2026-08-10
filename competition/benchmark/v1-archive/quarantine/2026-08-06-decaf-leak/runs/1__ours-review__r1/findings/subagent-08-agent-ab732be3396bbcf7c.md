# subagent agent-ab732be3396bbcf7c

# Code Review

**Reviewer**: broad-reviewer
**Date**: 2026-08-06
**Scope**: `src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs` (PR #32770, fix for #32747 — blob `GetStream`/`GetBytes` across multi-table joins), plus the accompanying test addition in `test/Microsoft.Data.Sqlite.Tests/SqliteDataReaderTest.cs`. Reviewed against the full current file content and `git diff HEAD~1 HEAD` (confirmed identical to the diff supplied in the task).

## Summary

| Severity | Count |
|----------|-------|
| 🔴 Critical | 1 |
| 🟠 High | 1 |
| 🟡 Medium | 3 |
| 🟢 Low | 2 |

**Verdict**: CRITICAL_ISSUES

## Project Standards Applied

Root `.editorconfig` (checked into repo):
- `dotnet_style_require_accessibility_modifiers = always:suggestion`
- `csharp_space_around_binary_operators = before_and_after`
- `dotnet_style_readonly_field = true:warning` (satisfied — new field is `readonly`)

---

## Findings

### 🔴 Critical: `Debug.Assert` now fails on a legitimate, already-tested "no rowid" code path

| | |
|---|---|
| **File** | `src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs:393` |
| **Category** | ERROR_HANDLING (broken invariant) |
| **Confidence** | 100 (anchor) |
| **Pre-existing** | no |

**Issue:** In the old code, `_rowidOrdinal` was seeded to the sentinel `-1` *before* the scan loop, so `Debug.Assert(_rowidOrdinal.HasValue)` was a tautology — it could never fail, regardless of whether a rowid was found. The new code removed the sentinel: `rowIdForOrdinal` starts (and stays) `null` unless the loop actually finds a rowid/single-column INTEGER primary key. `Debug.Assert(rowIdForOrdinal!=null)` at line 393 therefore now asserts something that is **not** always true — it is false precisely on the "no discoverable rowid" path (`WITHOUT ROWID` tables, composite primary keys), which is not an error condition at all: it's the exact scenario the very next line (`if (rowIdForOrdinal == null) return new MemoryStream(...)`) is designed to handle correctly.

This is not hypothetical: the pre-existing test `GetStream_works_when_composite_pk` (`test/Microsoft.Data.Sqlite.Tests/SqliteDataReaderTest.cs:515-541`) selects `Id1, Id2, Data` from a table with `PRIMARY KEY (Id1, Id2)` and no `rowid` column in the result set. With this change, `pkColumns` never reaches `1` (composite key) and no column is named `"rowid"`, so `rowIdForOrdinal` remains `null` and the loop falls through straight into the now-broken assert.

**Why Critical:** Dual-path check — Forward: composite-PK/`WITHOUT ROWID` table + blob column selected → loop exits without setting `rowIdForOrdinal` → assert condition is false → assertion fires on a path the code is explicitly designed to support. Backward: for the assert to fire, no rowid-aliasing column can exist for that table — exactly the condition `GetStream_works_when_composite_pk` constructs. Both paths converge, so this is confirmed, not speculative.

[Verified from code] The logical invariant is broken on a normal, already-covered input.
[Unverified/Inference] The exact runtime consequence of a failed `Debug.Assert` (silent trace-log continuation, debugger break, or process termination via `Environment.FailFast`) depends on the hosting environment's `TraceListener` configuration and was not executed in this sandbox (no dotnet toolchain available per pre-flight gates) — I cannot confirm which of these occurs here. Regardless of that runtime detail, `Debug.Assert` calls are compiled out entirely in Release builds (`[Conditional("DEBUG")]`), so this only manifests when the assembly is built in Debug configuration — which is the default for `dotnet test` and many local/CI workflows, i.e. this repo's own test suite.

**Fix:** Restore a way to represent "known: no rowid" distinctly from "not yet computed," e.g. cache a nullable sentinel value in the dictionary instead of only populating it on success, and assert on the *lookup outcome*, not on whether a rowid was found:

```csharp
if (!RowIds.TryGetValue(rowidkey, out var cacheHit))
{
    RowIdInfo? found = null;
    var pkColumns = -1L;
    for (var i = 0; i < FieldCount; i++)
    {
        // ... unchanged scan ...
        if (columnName == "rowid") { found = new RowIdInfo(i, tableName); break; }
        // ...
        if (pkColumns == 1L) { found = new RowIdInfo(i, tableName); break; }
    }

    RowIds.Add(rowidkey, found); // cache the negative result too — see High finding below
    rowIdForOrdinal = found;
}
else
{
    rowIdForOrdinal = cacheHit;
}
```

(This also requires `Dictionary<string, RowIdInfo?>` and removing the now-incorrect assert, or replacing it with an assert that only checks internal consistency, not "a rowid was found.")

**Actionability Check:**
- [x] Fix specifies exact change
- [x] Fix requires no additional decisions (aside from picking the exact caching representation, sketched above)

---

### 🟠 High: Negative lookups are no longer memoized — full rescan (and a nested SQL sub-query) reruns on every `GetStream` call for tables without a discoverable rowid

| | |
|---|---|
| **File** | `src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs:329-394` |
| **Category** | SCALABILITY |
| **Confidence** | 100 (anchor) |
| **Pre-existing** | no |

**Issue:** The old code cached the negative result (`_rowidOrdinal = -1`) so the `O(FieldCount)` scan — which can include a call to `sqlite3_table_column_metadata` and, for INTEGER PRIMARY KEY columns, a full command execution (`SELECT COUNT(*) FROM pragma_table_info($table) WHERE pk != 0`, lines 375-381) — ran at most once per `SqliteDataRecord` instance. The new code only calls `RowIds.Add(...)` on the success branches (lines 355, 387); when no rowid is found, nothing is added to `RowIds`, so `RowIds.TryGetValue` misses again on every subsequent call to `GetStream`/`GetBytes`/`GetChars` for that same blob column across every row of the result set, re-running the entire scan (and the nested `ExecuteScalar()` sub-query) each time.

**Why High:** For a query joining tables with composite/`WITHOUT ROWID` keys and streaming blob columns over many rows, this reintroduces an O(rows × columns) re-scan plus a nested command execution per row where the old code was O(1) after the first row. This is a genuine, silent performance regression introduced by the refactor, not called out anywhere in the PR description or commit messages.

**Fix:** Cache the negative outcome as well (see the sketch in the Critical finding above — add `null`/a sentinel to `RowIds` even when no rowid is found), restoring the original memoization guarantee while keeping the per-table (rather than global) cache key.

**Actionability Check:**
- [x] Fix specifies exact change
- [x] Fix requires no additional decisions

---

### 🟡 Medium: New field omits the required `private` accessibility modifier

| | |
|---|---|
| **File** | `src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs:39` |
| **Category** | CONVENTION_VIOLATION |
| **Confidence** | 100 (anchor) |
| **Pre-existing** | no |

**Issue:** `readonly Dictionary<string, RowIdInfo> RowIds = new Dictionary<string, RowIdInfo>();` has no explicit accessibility modifier (it is implicitly `private`). The repo's root `.editorconfig` sets `dotnet_style_require_accessibility_modifiers = always`, and every sibling field in this exact class (`_connection`, `_addChanges`, `_blobCache`, `_typeCache`, `_columnNameOrdinalCache`, `_columnNameCache`, `_stepped`, `_alreadyThrown`, `_alreadyAddedChanges`) is declared `private` with an `_camelCase` name. `RowIds` breaks both the explicit rule and the file's own established convention.

**Fix:**
```csharp
private readonly Dictionary<string, RowIdInfo> _rowIds = new();
```
(and update the two call sites accordingly).

**Actionability Check:**
- [x] Fix specifies exact change
- [x] Fix requires no additional decisions

---

### 🟡 Medium: Cache key can't distinguish two occurrences of the same table (self-joins) — same failure class as the bug being fixed

| | |
|---|---|
| **File** | `src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs:328-329` |
| **Category** | DATA_LOSS (silently wrong blob data) |
| **Confidence** | 50 (anchor) |
| **Pre-existing** | yes — the underlying inability to distinguish two occurrences of the same physical table was present before this PR too (the old code was arguably worse: one global ordinal shared across *all* tables); this PR narrows but does not eliminate the class of defect it targets |

**Issue:** `rowidkey = $"{blobDatabaseName}_{blobTableName}"` is keyed purely by database + table name, both obtained via `sqlite3_column_table_name`, which returns the underlying table name, not any query alias. For a self-join (`SELECT a.blob, b.blob FROM T a JOIN T b ON ...`) with blob columns selected from both sides, both blob columns resolve to the same key `"main_T"`, so the second lookup reuses the first occurrence's cached `RowIdInfo` (rowid ordinal) — potentially applying instance `a`'s rowid to `b`'s blob column, i.e. exactly the "wrong data returned" symptom the parent issue #32747 was filed for, just for a narrower trigger condition.

**Why Medium (not Critical):** Requires a self-join specifically involving two blob columns from the same underlying table, which is a much rarer query shape than the plain multi-table join this PR targets; existence and exact reachability weren't executed/verified in this sandbox.

**Fix:** Disambiguate by the columns' actual ordinal grouping rather than table name alone (e.g., key on the rowid-defining source column's position or the SQL-level table/alias index if available), or explicitly document this as a known limitation and add a regression test to lock in current (even if imperfect) behavior.

**Actionability Check:**
- [x] Fix specifies exact change (direction only — the concrete disambiguation strategy needs a design decision)
- [ ] Fix requires no additional decisions — flagging the gap and the two remediation directions is the actionable part here

---

### 🟢 Low: Missing spaces around `!=` operator

| | |
|---|---|
| **File** | `src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs:393` |
| **Category** | CONVENTION_VIOLATION |
| **Confidence** | 100 (anchor) |
| **Pre-existing** | no |

**Issue:** `Debug.Assert(rowIdForOrdinal!=null);` violates `.editorconfig`'s explicit `csharp_space_around_binary_operators = before_and_after`.

**Fix:** `Debug.Assert(rowIdForOrdinal != null);` (moot if the Critical finding's fix removes/reworks this assert).

**Actionability Check:**
- [x] Fix specifies exact change
- [x] Fix requires no additional decisions

---

### 🟢 Low: `RowIdInfo` exposes mutable public setters for values that are only ever set once, at construction

| | |
|---|---|
| **File** | `src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs:20-30` |
| **Category** | API_DESIGN |
| **Confidence** | 75 (anchor) |
| **Pre-existing** | no |

**Issue:** `RowIdInfo.Ordinal`/`TableName` use `{ get; set; }` even though every construction path sets them once via the constructor and nothing in the class ever mutates them afterward. Since instances are cached in a shared dictionary for the record's lifetime, unintended external mutation would silently corrupt cached lookups for all subsequent rows/columns sharing that table.

**Fix:**
```csharp
internal class RowIdInfo
{
    public int Ordinal { get; }
    public string TableName { get; }

    public RowIdInfo(int ordinal, string tableName)
    {
        Ordinal = ordinal;
        TableName = tableName;
    }
}
```

**Actionability Check:**
- [x] Fix specifies exact change
- [x] Fix requires no additional decisions

---

## Considered But Not Flagged

- **Redundant `RowIdInfo? rowIdForOrdinal = null;` before the `out` assignment** (line 327-329): the initializer is immediately overwritten by `TryGetValue`'s `out` parameter. Purely cosmetic dead initialization, no behavioral effect — not worth a separate finding.
- **Extraneous blank line inserted after `namespace Microsoft.Data.Sqlite {`** (line 17): whitespace-only artifact of the diff, no functional or convention impact worth flagging on its own.
- **Repeated nested `_connection.CreateCommand()` + `ExecuteScalar()` while a `SqliteDataReader` is mid-iteration on the same connection**: this pattern (running a second statement on the same connection while the outer statement is active) is pre-existing (it existed in the code before this PR, just executed at most once); this PR only affects *how often* it runs (see the High finding above), not its correctness, so not separately flagged as pre-existing.
- **Nullable-reference annotation gaps on `blobDatabaseName`/`blobTableName`/`tableName` locals** (typed `string`, sourced from `.utf8_to_string()` which can return null): this pattern is unchanged from before the diff and not introduced by this change — pre-existing, out of scope per the "norm" reach.

## Positive Observations

- The core fix (keying the rowid-ordinal cache by database+table rather than a single global ordinal) correctly targets and resolves the reported bug (#32747) for the common case of a straightforward multi-table join, and the added test (`GetBytes_works_streaming_join`) directly reproduces the originally reported failure mode with a clear before/after comment.
- The per-table cache correctly persists across `Read()` calls within the same `SqliteDataRecord` (single reader lifetime), which is the right lifetime for this data — table/column shape doesn't change between rows of the same query.
- Existing regression tests for composite-PK and composite-PK-with-explicit-rowid scenarios (`GetStream_works_when_composite_pk`, `GetStream_works_when_composite_pk_and_rowid`) were already in place and — despite the Critical regression above — are exactly the tests that would have caught it, underscoring the value of running the full existing suite before merge.

### Probe Requests

- Run `dotnet test --filter FullyQualifiedName~GetStream_works_when_composite_pk` (Debug configuration, the default) to confirm/refute the exact runtime behavior of the failed `Debug.Assert` described in the Critical finding.
- Run the full `Microsoft.Data.Sqlite.Tests` suite in Debug configuration to check for any other tests hitting the "no rowid found" branch that might also be affected.
