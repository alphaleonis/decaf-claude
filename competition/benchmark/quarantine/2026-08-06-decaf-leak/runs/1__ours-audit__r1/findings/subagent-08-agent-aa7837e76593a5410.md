# subagent agent-aa7837e76593a5410

I have everything I need. The existing tests `GetStream_works_with_text`, `_with_int`, `_with_float`, and `GetStream_works_when_composite_pk` all drive the no-rowid path, confirming the `Debug.Assert` regression concretely.

# Code Review

**Reviewer**: broad-reviewer
**Date**: 2026-08-06
**Scope**: PR dotnet/efcore #32770 — `src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs` (`GetStream` rowid caching), plus the added test in `test/Microsoft.Data.Sqlite.Tests/SqliteDataReaderTest.cs`. Reviewed the full file and surrounding tests.

## Summary

| Severity | Count |
|----------|-------|
| 🔴 Critical | 0 |
| 🟠 High | 1 |
| 🟡 Medium | 1 |
| 🟢 Low | 3 |

**Verdict**: NEEDS_CHANGES

## Project Standards Applied

No repo-local `CLAUDE.md` found in the efcore tree under review. The dotnet/efcore repo's well-established field-naming convention (`private readonly` fields prefixed `_camelCase`) is applied as an implicit-but-consistent in-file standard, evidenced by every other field in this same class.

---

## Findings

### 🟠 High: `Debug.Assert(rowIdForOrdinal != null)` fires on the legitimate no-rowid path
| | |
|---|---|
| **File** | `src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs:393` |
| **Category** | NULL_REFERENCE / logic-regression |
| **Confidence** | 100 |
| **Pre-existing** | no — introduced by this change |

**Issue:** The old code set `_rowidOrdinal = -1` on entry, so `Debug.Assert(_rowidOrdinal.HasValue)` was *always* true. The new code leaves `rowIdForOrdinal` as `null` when the scan finds neither a `rowid` column nor a single-column integer PK, and the very next line (396–399) treats `null` as a legitimate outcome (return an in-memory `MemoryStream`). The re-added assert `Debug.Assert(rowIdForOrdinal != null)` therefore fires on a normal, expected path in Debug builds.

**Why High:** Forward path — a blob column with no backing rowid (an expression column, a composite-PK table, or a `WITHOUT ROWID` table) → scan finds no match → `rowIdForOrdinal` stays `null` → assert fails. Backward path — for the assert to fire, `rowIdForOrdinal` must be `null`, which requires exactly the no-rowid case the code deliberately supports. Both paths hold. Existing tests exercise this directly: `GetStream_works_with_text`, `GetStream_works_with_int`, `GetStream_works_with_float` (single expression column — the scan loop finds no sibling columns) and `GetStream_works_when_composite_pk` (composite PK, `pkColumns == 2`). Under a Debug build these now trip the assertion; in modern .NET a failed `Debug.Assert` with no debugger attached calls `Environment.FailFast`, aborting the test host. This is a regression the change's own added test does not catch (it only covers the integer-PK rowid case).

**Fix:**
```csharp
// Remove the assert — null is a valid result meaning "no rowid mapping for this table".
// (Delete the Debug.Assert line entirely, or move it inside the branches that DO assign.)
```

**Actionability Check:**
- [x] Fix specifies exact change
- [x] Fix requires no additional decisions

---

### 🟡 Medium: No-rowid result is no longer cached — full scan + SQL query re-runs on every `GetStream`
| | |
|---|---|
| **File** | `src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs:396` |
| **Category** | EFFICIENCY / performance-regression |
| **Confidence** | 100 |
| **Pre-existing** | no — introduced by this change |

**Issue:** The old code cached the negative result (`_rowidOrdinal = -1`), so a no-rowid table short-circuited on repeat calls. The new code adds an entry to `RowIds` only on the two *success* branches (lines 354–355 and 386–387). On the no-rowid path nothing is inserted, so `RowIds.TryGetValue(rowidkey, …)` misses every time and the entire `FieldCount` scan re-runs on each `GetStream` call for that table — including a `SELECT COUNT(*) FROM pragma_table_info(...)` round-trip for each integer-PK candidate column.

**Why Medium:** `GetBytes` and `GetChars` call `GetStream` on every invocation, and callers commonly read a blob in chunks (repeated `GetBytes`), so a composite-PK/no-rowid blob column re-issues the `pragma_table_info` query per read. Correctness is unaffected; throughput on repeated reads of no-rowid blob columns regresses versus the prior caching behavior.

**Fix:**
```csharp
// Cache the negative result too, so repeat calls short-circuit like before.
// After the scan loop, before returning:
RowIds[rowidkey] = rowIdForOrdinal; // stores null-or-value; then have the
                                    // dictionary hold RowIdInfo? and treat a
                                    // present-but-null entry as "no rowid".
```
(Requires making the dictionary value nullable or using a sentinel, mirroring the old `-1` sentinel — one design decision.)

**Actionability Check:**
- [x] Fix specifies exact change
- [ ] Fix requires a small design choice (nullable value vs. sentinel)

---

### 🟢 Low: `RowIdInfo.TableName` is written but never read (dead field)
| | |
|---|---|
| **File** | `src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs:23` |
| **Category** | UNUSED_CODE |
| **Confidence** | 100 |
| **Pre-existing** | no |

**Issue:** `TableName` is set in the constructor and both call sites but never read anywhere. Only `Ordinal` is consumed (line 402). The field adds memory and reader confusion for no benefit.

**Fix:** Drop `TableName` from `RowIdInfo` and pass only the ordinal, or collapse the dictionary value type to `int`.

---

### 🟢 Low: Field `RowIds` violates the class's naming convention
| | |
|---|---|
| **File** | `src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs:39` |
| **Category** | CONVENTION_VIOLATION |
| **Confidence** | 100 |
| **Pre-existing** | no |

**Issue:** Every other instance field in this class is `private readonly _camelCase` (`_connection`, `_addChanges`, `_blobCache`, `_typeCache`, …). The new field is declared `readonly Dictionary<string, RowIdInfo> RowIds` — no explicit access modifier and PascalCase, inconsistent with the file and the broader dotnet/efcore convention. Related nits in the same change: `RowIdInfo` exposes mutable `{ get; set; }` auto-properties where the type is only ever constructed once (should be readonly), and `Debug.Assert(rowIdForOrdinal!=null)` / `string rowidkey` omit the spacing and naming used elsewhere.

**Fix:** Rename to `private readonly Dictionary<string, RowIdInfo> _rowIds`; make `RowIdInfo` properties get-only; normalize spacing.

---

### 🟢 Low: Composite dictionary key can collide across db/table name boundaries
| | |
|---|---|
| **File** | `src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs:328` |
| **Category** | CORRECTNESS (edge case) |
| **Confidence** | 50 |
| **Pre-existing** | no |

**Issue:** `rowidkey = $"{blobDatabaseName}_{blobTableName}"` uses `_` as an unescaped separator. Distinct (database, table) pairs can map to the same key — e.g. db `a`, table `b_c` vs. db `a_b`, table `c` both yield `a_b_c`. With attached databases and underscore-containing identifiers this could theoretically map two different tables to one cached rowid ordinal — the exact class of bug this PR set out to fix.

**Fix:** Use a `ValueTuple<string,string>` key, or a separator that cannot appear in SQLite identifiers, or a nested dictionary keyed by database then table.

---

## Considered But Not Flagged

- **Thread-safety of the mutable `RowIds` dictionary** — `SqliteDataRecord` is a per-reader, single-threaded object like the rest of the class (all fields are unsynchronized caches); no new concurrency contract is introduced. Not an issue (anchor 25).
- **`RowIds` never cleared on `Read()`** (unlike `_blobCache` at line 439–442) — rowid *ordinals* are a function of the statement's column layout, which is stable across rows, so this is correct and intentional; matches the old single-field behavior. Not an issue.
- **The added test only covers the integer-PK JOIN case** — it does correctly exercise the reported bug (two blob columns from two tables). Broader no-rowid-in-JOIN coverage would be nice-to-have but the primary regression is covered.

## Positive Observations

- The core fix is correct: keying rowid resolution by `(database, table)` instead of a single shared field genuinely resolves the cross-table `no such rowid` bug in #32747, and the added `GetBytes_works_streaming_join` test reproduces the original failure and asserts the corrected bytes.
- The scan logic (rowid column vs. single-column integer PK vs. fall back to in-memory blob) was preserved intact; only the cache keying changed.

## Probe Requests

No dotnet SDK available and this is read-only, so I did not run these. Suggested verification for a maintainer with the SDK:

1. Run `GetStream_works_with_text`, `GetStream_works_with_int`, `GetStream_works_with_float`, and `GetStream_works_when_composite_pk` against a **Debug** build of `Microsoft.Data.Sqlite.Core` to confirm whether the re-added `Debug.Assert` (line 393) aborts the test host. This determines whether the High finding is CI-visible or Debug-only-latent.
2. Benchmark repeated `GetBytes` chunked reads on a composite-PK blob column to quantify the re-scan/`pragma_table_info` regression (Medium finding).
