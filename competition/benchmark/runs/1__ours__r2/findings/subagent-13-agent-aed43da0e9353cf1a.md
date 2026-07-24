# subagent agent-aed43da0e9353cf1a

# Code Review

**Reviewer**: broad-reviewer
**Date**: 2026-07-22
**Scope**: `src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs` and `test/Microsoft.Data.Sqlite.Tests/SqliteDataReaderTest.cs`, PR #32770 (commit `9e69b85`, diffed against `7128186`)

## Summary

| Severity | Count |
|----------|-------|
| 🔴 Critical | 0 |
| 🟠 High | 1 |
| 🟡 Medium | 2 |
| 🟢 Low | 2 |

**Verdict**: NEEDS_CHANGES

## Project Standards Applied

From `.editorconfig` (explicit, repo-root):
- `dotnet_style_require_accessibility_modifiers = always` (line 59)
- `csharp_space_around_binary_operators = before_and_after` (line 157)
- `trim_trailing_whitespace = true` (line 10)
- Established (informal but consistent) pattern in this file: every existing private field uses `_camelCase` (`_connection`, `_blobCache`, `_typeCache`, `_stepped`, …).

No CI format-verification gate was found in `azure-pipelines.yml`/`eng/`, so these are non-build-breaking "suggestion"-level violations, not compile errors. `_BuildConfig` defaults to `Release` in CI (line 24 of `azure-pipelines.yml`), which is relevant to Finding 1 below.

---

## Findings

### 🟠 High: Negative rowid-lookup result is never cached, defeating the fix's own purpose and falsifying `Debug.Assert`

| | |
|---|---|
| **File** | `src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs:329-402` |
| **Category** | ERROR_HANDLING / cache-invalidation (Production Reliability) |
| **Confidence** | 100 |
| **Pre-existing** | no |

**Issue:** In the pre-fix code, `_rowidOrdinal` was set to the sentinel `-1` *before* the search loop ran, so a table with no usable rowid (a `WITHOUT ROWID` table, or a table with a composite primary key) was permanently cached as "no rowid" after the very first `GetStream` call. In the new code, `rowIdForOrdinal` is only written to the `RowIds` dictionary inside the two "found" branches (`RowIds.Add(rowidkey, ...)` at lines 355 and 387). If the loop completes without finding a rowid column, nothing is added to `RowIds` for that key. The consequence is two-fold:

1. **Every subsequent `GetStream`/`GetBytes` call for a blob column on such a table re-runs the entire discovery loop** — including, when a candidate integer-PK column is found, issuing a fresh `SELECT COUNT(*) FROM pragma_table_info($table) WHERE pk != 0;` query via `command.ExecuteScalar()` (lines 375-380) on every single call. This is a real regression versus the pre-fix behavior, and it directly hits the API's own documented use case: `GetBytes(ordinal, dataOffset, buffer, ...)` is designed for chunked reads of a large blob by repeated calls with increasing `dataOffset` — exactly the pattern that will now re-trigger the expensive lookup (and an extra SQL query) on every chunk for `WITHOUT ROWID`/composite-PK tables.
2. `Debug.Assert(rowIdForOrdinal!=null)` (line 393) is now a **real, sometimes-false assertion** for a case the codebase already exercises in `test/Microsoft.Data.Sqlite.Tests/SqliteDataReaderTest.cs:515-541` (`GetStream_works_when_composite_pk`, which explicitly expects `rowIdForOrdinal == null` → the `MemoryStream` fallback path). Previously this assert was checking `_rowidOrdinal.HasValue`, which was trivially always true because of the `-1` sentinel — i.e. it was vacuous and never fired. Now it will fire for this legitimate scenario whenever the code is compiled with `DEBUG` defined (`Debug.Assert` is `[Conditional("DEBUG")]`). CI here builds with `_BuildConfig: Release` (so this is stripped in the shipped NuGet package), but any contributor running `dotnet test` locally without `-c Release` (the common default) will trip this on an already-passing, pre-existing test. [Unverified/Inference]: whether this manifests as noisy console output or a harder failure (e.g. via `Environment.FailFast` inside `DefaultTraceListener.Fail`) depends on the .NET Core trace-listener runtime behavior, which I could not verify by execution in this environment (no SDK installed); either way the assertion is logically wrong.

**Why High:** Forward path — for a `WITHOUT ROWID`/composite-PK table, every blob-stream call now re-executes the full column-metadata scan and an extra SQL query, therefore chunked/streamed blob reads on such tables (the exact scenario `GetBytes` is designed for) get measurably slower, and the invariant the assert encodes is now false for code paths already under test. Backward path — this requires the specific configuration of a table lacking a single-column rowid; since CI ships Release binaries, production consumers only see the performance regression, not the assert; that divergence is why this is rated High rather than Critical.

**Fix:**
```csharp
// Cache both positive and negative lookups, matching the pre-fix
// sentinel behavior, so tables without a usable rowid (WITHOUT ROWID
// tables, composite primary keys) aren't re-scanned - including the
// extra pragma_table_info query - on every call.
if (!RowIds.TryGetValue(rowidkey, out var rowIdForOrdinal))
{
    var pkColumns = -1L;
    for (var i = 0; i < FieldCount; i++)
    {
        // ... unchanged discovery loop ...
    }

    RowIds[rowidkey] = rowIdForOrdinal; // may legitimately be null
}
```
and remove (or correct) `Debug.Assert(rowIdForOrdinal != null);`, since a `null` result is a valid, already-tested outcome, not a programming error.

**Actionability Check:**
- [x] Fix specifies exact change
- [x] Fix requires no additional decisions

---

### 🟡 Medium: Self-joins (same table referenced twice) remain broken by the same bug class this PR fixes

| | |
|---|---|
| **File** | `src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs:328-394` |
| **Category** | correctness (Production Reliability) |
| **Confidence** | 50 |
| **Pre-existing** | no (the specific "wrong cached ordinal reused" failure mode is a property of the new per-key cache, not the old single-cache) |

**Issue:** The cache key is `$"{blobDatabaseName}_{blobTableName}"`, and `blobTableName` comes from `sqlite3_column_table_name`, which — per SQLite's documented column-metadata API — reports the *underlying schema table name*, not the SQL alias used in the `FROM`/`JOIN` clause. For a self-join such as `SELECT a1.rowid, a1.Value, a2.rowid, a2.Value FROM A a1 JOIN A a2 ON ...`, both `a1.Value` and `a2.Value` report table name `"A"`, so both map to the same cache key `"main_A"`. The first `GetStream` call for `a1.Value` will find and cache `a1.rowid`'s ordinal under that key; the second call for `a2.Value` will reuse the cached (wrong) ordinal belonging to `a1`, constructing a `SqliteBlob` with `a2`'s database/table/column but `a1`'s rowid — either an `SqliteException: no such rowid` or, if the coincidental rowid value happens to exist in the table, silently wrong blob data. This is the exact class of bug issue #32747 reports, just triggered by "same table twice" rather than "two different tables." Notably, the new `RowIdInfo.TableName` field is populated but never read anywhere (see Low finding below) — it looks like an attempt to disambiguate this exact scenario was started but not finished.

**Why Medium:** This requires a query that both self-joins a table and streams BLOB columns from both instances — a real but narrower usage pattern than the two-different-tables case the PR's own regression test covers, so I can't confirm from the diff alone how often this is hit in practice.

**Fix:** At minimum, document the limitation explicitly since a full fix needs design work (e.g., correlating each rowid candidate to the nearest same-table column group by ordinal position, or falling back to `GetCachedBlob` when the same table-key is seen from two disjoint ordinal ranges):
```csharp
// NOTE: sqlite3_column_table_name reports the underlying schema table,
// not the SQL alias, so self-joins (the same table referenced twice)
// are not distinguished by this cache key and may resolve to the
// wrong rowid. See #<issue> for tracking a full fix.
```

**Actionability Check:**
- [x] Fix specifies exact change (documentation)
- [ ] A complete functional fix requires additional design decisions (noted above)

---

### 🟡 Medium: Unescaped `_` delimiter in the composite cache key can collide across different (database, table) pairs

| | |
|---|---|
| **File** | `src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs:328` |
| **Category** | correctness (Production Reliability) |
| **Confidence** | 50 |
| **Pre-existing** | no |

**Issue:** `string rowidkey = $"{blobDatabaseName}_{blobTableName}";` concatenates the database and table name with a plain `_`, which is also a legal character inside SQLite identifiers. Two distinct (database, table) pairs can therefore produce the same key, e.g. database `"db_A"` + table `"table"` and database `"db"` + table `"A_table"` both yield `"db_A_table"`. If a query streams blobs from both, the second lookup will reuse the first pair's cached ordinal, again risking either an exception or silently wrong rowid/data for the mismatched table. This is most likely to bite multi-attached-database schemas using underscore-delimited naming (a fairly common convention, e.g. attached per-tenant databases).

**Why Medium:** Concrete and demonstrable from the code, but requires a specific underscore-ambiguous naming pattern across attached databases/tables to actually manifest — narrower than typical single-database usage.

**Fix:** Use a delimiter-free composite key (tuple) instead of string concatenation:
```csharp
readonly Dictionary<(string Database, string Table), RowIdInfo?> RowIds = new();
...
var rowidkey = (blobDatabaseName, blobTableName);
if (!RowIds.TryGetValue(rowidkey, out var rowIdForOrdinal))
```

**Actionability Check:**
- [x] Fix specifies exact change
- [x] Fix requires no additional decisions

---

### 🟡 Medium: New code violates explicit `.editorconfig` rules

| | |
|---|---|
| **File** | `src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs:17,39,393` |
| **Category** | CONVENTION_VIOLATION |
| **Confidence** | 100 |
| **Pre-existing** | no |

**Issue:**
- Line 39: `readonly Dictionary<string, RowIdInfo> RowIds = ...` omits the access modifier, violating `dotnet_style_require_accessibility_modifiers = always`.
- Line 39: `RowIds` uses PascalCase, unlike every other private field in this class (`_connection`, `_blobCache`, `_typeCache`, `_columnNameOrdinalCache`, `_columnNameCache`, `_stepped`, `_alreadyThrown`, `_alreadyAddedChanges`), all of which follow the `_camelCase` style defined in `.editorconfig` (line 194-195).
- Line 393: `Debug.Assert(rowIdForOrdinal!=null);` has no spaces around `!=`, violating `csharp_space_around_binary_operators = before_and_after`.
- Line 17: stray blank line with trailing whitespace (`    ` then newline) added between the namespace's opening brace and the class declaration, violating `trim_trailing_whitespace = true`.

**Why Medium:** These are "suggestion"-level rules (won't fail the build, no format-verification gate found in CI), but they are explicit, documented project standards directly violated by the new code, and the naming inconsistency reduces readability for future maintainers scanning this class's fields.

**Fix:**
```csharp
private readonly Dictionary<string, RowIdInfo> _rowIds = new();
...
Debug.Assert(rowIdForOrdinal != null);
```
and remove the stray blank line after `namespace Microsoft.Data.Sqlite\n{`.

**Actionability Check:**
- [x] Fix specifies exact change
- [x] Fix requires no additional decisions

---

### 🟢 Low: `RowIdInfo.TableName` is assigned but never read

| | |
|---|---|
| **File** | `src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs:20-30,354,386` |
| **Category** | UNUSED_CODE |
| **Confidence** | 100 |
| **Pre-existing** | no |

**Issue:** `RowIdInfo.TableName` is populated at both construction sites (`new RowIdInfo(i, tableName)`) but is never read anywhere in the file — only `.Ordinal` is used (line 402). It's dead state that also has a public setter it never needs (never mutated post-construction).

**Fix:** Either remove the unused property, or (see the self-join finding above) actually use it to detect/guard against the same-table-twice case it appears intended for.

**Actionability Check:**
- [x] Fix specifies exact change
- [x] Fix requires no additional decisions

---

### 🟢 Low: New test leaves a debug `Console.WriteLine` and informal inline comment

| | |
|---|---|
| **File** | `test/Microsoft.Data.Sqlite.Tests/SqliteDataReaderTest.cs:161,169-170` |
| **Category** | test hygiene (Structural Quality) |
| **Confidence** | 100 |
| **Pre-existing** | no |

**Issue:** `Console.WriteLine($"A.ID={reader.GetInt32(0)} B.ID={reader.GetInt32(2)}");` is a debugging leftover with no assertion value; it's the only `Console.WriteLine` call in the entire `SqliteDataReaderTest.cs` file, standing out from the surrounding style. The trailing comment `//this was failing. now should be fixed` is informal (lowercase, no space after `//`, double space before it) compared to the rest of the file's comment style.

**Fix:** Remove the `Console.WriteLine`, and replace the comment with something durable, e.g. `// Regression test for #32747: previously reused the first table's rowid ordinal for the second table's blob column.`

**Actionability Check:**
- [x] Fix specifies exact change
- [x] Fix requires no additional decisions

---

## Considered But Not Flagged

- **`GetStream` re-entrancy with `_connection.CreateCommand()` mid-read** (lines 375-380): the extra `pragma_table_info` query is issued through a fresh command on the same connection while the outer reader's statement is still active. This pattern is unchanged from the pre-fix code (same call site, same conditions) — not introduced by this diff, so not flagged as a new issue (only its *frequency* changed, per the High finding above).
- **Literal/expression blob columns with empty database/table names** (e.g. `SELECT x'01', x'02';`): traced through the unchanged loop body; behavior here is identical to pre-fix code (the loop body itself was moved verbatim, only the caching wrapper changed), so any latent issue there is pre-existing and out of scope.
- **Thread-safety of the new `Dictionary`**: `SqliteDataRecord` instances are constructed fresh per statement execution (`SqliteDataReader.cs:180`) and are not documented/used across threads elsewhere in this codebase; no new concurrency concern introduced.
- **`RowIdInfo` as a mutable class with public setters** instead of an immutable record/readonly struct: true but purely stylistic (never mutated post-construction); not worth a separate finding beyond noting it in the dead-field item above.

## Positive Observations

- The core design change — replacing a single global cached ordinal with a per-(database, table) cache — correctly addresses the root cause described in issue #32747 for the common case of two *different* joined tables, and does so with a minimally invasive diff to the surrounding discovery logic.
- `GetBytes_works_streaming_join` is a good, targeted regression test: it reproduces the exact reported failure (two tables joined, blob streamed from each), asserts on the actual byte content read from each stream (not just "no exception"), and would have failed against the pre-fix code.
- The fix correctly threads through `blobDatabaseName`/`blobTableName` freshly for each `GetStream` call for the `SqliteBlob` construction itself (lines 401-404), so the actual blob identity used is always correct for the *current* column — only the cached rowid *value* is at risk in the edge cases noted above, not the blob's database/table/column identity.
