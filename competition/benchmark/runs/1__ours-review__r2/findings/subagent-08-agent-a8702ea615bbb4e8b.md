# subagent agent-a8702ea615bbb4e8b

Now I have everything needed to write the report.

# Code Review

**Reviewer**: broad-reviewer
**Date**: 2026-08-06
**Scope**: `src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs` — commit `9e69b85` (PR #32770), replacing the single `int? _rowidOrdinal` cache with a per-table `Dictionary<string, RowIdInfo> RowIds`. Test-only change to `test/Microsoft.Data.Sqlite.Tests/SqliteDataReaderTest.cs` reviewed for context, no findings there.

## Summary

| Severity | Count |
|----------|-------|
| 🔴 Critical | 0 |
| 🟠 High | 2 |
| 🟡 Medium | 2 |
| 🟢 Low | 1 |

**Verdict**: NEEDS_CHANGES

## Project Standards Applied

- `.editorconfig` naming-convention rules (`dotnet_naming_style._camelCase`, required `_` prefix) — defined but not wired to an enforced `dotnet_naming_rule`, so treated as a sibling-consistency signal rather than an explicit-standard violation.
- `src/Microsoft.Data.Sqlite.Core/Microsoft.Data.Sqlite.Core.ruleset` — SA1309 (no-underscore-prefix) is explicitly disabled (`Action="None"`), confirming underscore-prefixed private fields are the accepted, unenforced-but-intended house style in this project (every other field in this exact class uses it).

---

## Findings

### 🟠 High: `Debug.Assert` now fires on a legitimate, explicitly-handled code path

| | |
|---|---|
| **File** | `src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs:393` |
| **Category** | ERROR_HANDLING |
| **Confidence** | 100 |
| **Pre-existing** | no |

**Issue:** Before this change, `_rowidOrdinal` was unconditionally set to `-1` at the top of the cache-miss branch, so `Debug.Assert(_rowidOrdinal.HasValue)` was a tautology (it could never fail — a `Nullable<int>` assigned `-1` always `HasValue == true`). This change removes that unconditional pre-assignment; `rowIdForOrdinal` now stays `null` whenever the scanning loop doesn't find a rowid substitute (WITHOUT ROWID tables, tables with a composite primary key, tables with no PK at all). The very next 8 lines (`if (rowIdForOrdinal == null) return new MemoryStream(...)`) prove this is an expected, supported outcome — yet the assert immediately above it now asserts the opposite.

**Why High:** In Debug builds (default for local dev and often for `dotnet test` runs), calling `GetStream` on a BLOB column of a joined table that lacks a single-column INTEGER PRIMARY KEY will trip this assertion on every call, even though the code was explicitly written to tolerate that case. This turns a normal, already-handled scenario into an assertion failure purely because of the caching refactor — the assert's truth value silently flipped from "always true" to "false whenever the fallback path is taken."

**Fix:**
```csharp
// Remove the now-incorrect assert, or make it consistent with the fallback path it precedes:
// Debug.Assert(rowIdForOrdinal!=null);   // DELETE — contradicts the null-fallback handling below
```

**Actionability Check:**
- [x] Fix specifies exact change
- [x] Fix requires no additional decisions

---

### 🟠 High: Negative lookup result is no longer cached — expensive scan/query repeats on every `GetStream` call

| | |
|---|---|
| **File** | `src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs:329-393` |
| **Category** | PERFORMANCE_REGRESSION |
| **Confidence** | 100 |
| **Pre-existing** | no |

**Issue:** Previously the "no rowid found" result was cached (`_rowidOrdinal = -1`), so the expensive column scan — including the `SELECT COUNT(*) FROM pragma_table_info($table) WHERE pk != 0` round-trip via `command.ExecuteScalar()` — ran at most once per reader for a given table. With the dictionary change, `RowIds.Add(rowidkey, ...)` is only called on the two "found" branches (lines 355, 387); when the loop falls through without finding a rowid, nothing is ever stored under `rowidkey`. Every subsequent `GetStream` call for that same table (e.g., once per row while iterating a result set, or for each of several BLOB columns on that table) re-runs the full column scan and re-issues the `pragma_table_info` SQL query.

**Why High:** For any joined query with a BLOB column on a table without a single-integer-column primary key, this is an unbounded N+1 SQL round-trip pattern — one extra query execution per `GetStream` call for the life of the reader, where before the fix there was exactly one. This is a genuine performance regression introduced by the caching-strategy change, not a pre-existing cost.

**Fix:**
```csharp
// Use a nullable dictionary value (or TryGetValue + ContainsKey) so "searched, found nothing" is distinguishable
// from "never searched", and cache both outcomes:
readonly Dictionary<string, RowIdInfo?> RowIds = new Dictionary<string, RowIdInfo?>();
...
if (!RowIds.TryGetValue(rowidkey, out var rowIdForOrdinal))
{
    ... // unchanged scan
    RowIds[rowidkey] = rowIdForOrdinal; // cache the miss too, even when it stays null
}
```

**Actionability Check:**
- [x] Fix specifies exact change
- [x] Fix requires no additional decisions

---

### 🟡 Medium: Cache key built by string concatenation can collide across distinct (database, table) pairs

| | |
|---|---|
| **File** | `src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs:328` |
| **Category** | DATA_LOSS |
| **Confidence** | 50 |
| **Pre-existing** | no |

**Issue:** `rowidkey = $"{blobDatabaseName}_{blobTableName}"` uses a plain `_` separator with no escaping. Two distinct `(database, table)` pairs can produce the same key, e.g. `database="main", table="Foo_Bar"` and `database="main_Foo", table="Bar"` both yield `"main_Foo_Bar"`. Underscore-delimited identifiers are common in SQLite schemas (snake_case tables, descriptive `ATTACH DATABASE ... AS` aliases), so this isn't purely theoretical.

**Why Medium:** If a collision occurs, `RowIds.TryGetValue` returns the `RowIdInfo` computed for the *other* table — a wrong column ordinal is then used with `GetInt64` against the current row, and the resulting (possibly garbage or mismatched) rowid is used to construct a `SqliteBlob` against `blobDatabaseName`/`blobTableName`. This can silently return the wrong blob data rather than throwing, which is a correctness/data-integrity concern, not just a crash.

**Fix:**
```csharp
// Use a delimiter/key construction that can't collide, e.g. a tuple key or length-prefixed encoding:
var rowidkey = (blobDatabaseName, blobTableName);
readonly Dictionary<(string, string), RowIdInfo> RowIds = new();
```

**Actionability Check:**
- [x] Fix specifies exact change
- [x] Fix requires no additional decisions

---

### 🟡 Medium: `RowIdInfo.TableName` is written but never read

| | |
|---|---|
| **File** | `src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs:20-30` |
| **Category** | UNUSED_CODE |
| **Confidence** | 100 |
| **Pre-existing** | no |

**Issue:** `RowIdInfo` stores `TableName` (set via constructor at lines 354/386), but nothing in `GetStream` or elsewhere in the file ever reads `RowIdInfo.TableName` (verified: the only other `TableName`-named symbols in the method are the unrelated local variable `tableName` at line ~344 and `blobTableName`, both independent of the cached `RowIdInfo`). It is redundant with the dictionary key, which already encodes the table name.

**Why Medium:** Dead data on a type that's about to become part of a caching contract is a knowledge-preservation risk on its own: a future maintainer will reasonably assume `TableName` is load-bearing (e.g., used for cache-invalidation or a consistency check) and either be misled or spend time investigating why it's unused. It also has a public mutable setter (`{ get; set; }`) which further overstates its role as a general-purpose property rather than write-once-at-construction data.

**Fix:**
```csharp
// Either use TableName (e.g. as a defensive check that the cached entry matches the current query
// plan) or remove it entirely and keep RowIdInfo as { public int Ordinal { get; } }.
```

**Actionability Check:**
- [x] Fix specifies exact change
- [x] Fix requires no additional decisions

---

### 🟢 Low: New field breaks the class's established private-field naming convention

| | |
|---|---|
| **File** | `src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs:39` |
| **Category** | NAMING |
| **Confidence** | 100 |
| **Pre-existing** | no |

**Issue:** Every other field in this class uses the `_camelCase` convention with an explicit `private` modifier: `_connection`, `_addChanges`, `_blobCache`, `_hasBytes`, `_columnNameOrdinalCache`, `_columnNameCache`, `_stepped`, `_alreadyThrown`, `_alreadyAddedChanges`. The new field is declared `readonly Dictionary<string, RowIdInfo> RowIds = ...` — PascalCase, no `_` prefix, and no explicit accessibility modifier (relies on C#'s implicit-private default). This is a direct, visible inconsistency within the very file it was added to.

**Why Low:** Purely cosmetic — no functional impact — but it's a clean, mechanical fix and the inconsistency is 100% verifiable by inspection of sibling fields in the same class.

**Fix:**
```csharp
private readonly Dictionary<string, RowIdInfo> _rowIds = new Dictionary<string, RowIdInfo>();
// ...and update the three call sites (lines 329, 355, 387) accordingly.
```

**Actionability Check:**
- [x] Fix specifies exact change
- [x] Fix requires no additional decisions

---

## Considered But Not Flagged

- **Dictionary lifetime**: `RowIds` (like the old `_rowidOrdinal`) lives for the lifetime of the `SqliteDataRecord`/reader instance and is never cleared mid-iteration. This is unchanged behavior relative to before (schema doesn't change across rows of the same result set), not a regression.
- **Thread safety of the dictionary**: `SqliteDataRecord` is single-threaded-per-reader by design (same as the prior nullable-int field); the change from scalar to dictionary doesn't introduce a new concurrency surface.
- **Stray blank line** added after the `namespace` opening brace (line 17) — pure whitespace noise, not worth a separate finding.
- **`RowIdInfo` public mutable setters** — noted only as a contributor to the "unused `TableName`" finding above; on its own it's a stylistic nit for an `internal` type with a constructor that already sets both values, not worth flagging independently.

## Positive Observations

- The core fix — keying the rowid-ordinal cache by `(database, table)` instead of a single global cache — correctly addresses the reported bug (issue #32747): a join over two tables no longer has the second table's blob lookup reuse the first table's rowid ordinal.
- A regression test (`GetBytes_works_streaming_join`) was added that reproduces the exact join scenario from the bug report and exercises `GetBytes` on BLOB columns from both joined tables.
- The found-path caching (`RowIds.Add(rowidkey, rowIdForOrdinal); break;`) correctly avoids re-adding an already-present key and preserves the original early-exit-on-first-match scanning logic.

## Probe Requests

- Confirm whether `dotnet test` / CI for `Microsoft.Data.Sqlite.Core` builds in `Debug` configuration (would make the `Debug.Assert` finding above concretely test-breaking rather than only a local-dev concern) — e.g. `grep -n "Configuration" eng/**/*.yml` or checking the relevant Azure Pipelines definition.
