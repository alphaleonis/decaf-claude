Review complete. Here is the review comment I would have posted (printed to terminal only — nothing was sent to GitHub):

---

### Code review

Reviewed dotnet/efcore#32770 ("Microsoft.Data.Sqlite.Core issue with multiple Blob columns", fixes #32747). Found 2 issues:

**1. `Debug.Assert(rowIdForOrdinal!=null)` fires on legitimate, explicitly-handled inputs — crashes Debug builds** (`src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs:393`, confidence 100)

The old code pre-seeded `_rowidOrdinal = -1` before the search, so its `Debug.Assert(_rowidOrdinal.HasValue)` was trivially always true. The rewrite represents "no rowid found" as `rowIdForOrdinal` staying `null` — which is a normal, supported outcome (composite-PK tables, `WITHOUT ROWID` tables, bare literals like `SELECT x'0102'`) that the very next line handles with the `MemoryStream` fallback. The kept assert now contradicts that fallback and fails on ordinary input. A review agent built the repo and ran the unmodified test suite: 260/260 pass at the pre-PR commit; 15 failures at this commit (`GetStream_works`, `GetStream_works_when_composite_pk`, `GetBytes_works`, `GetChars_works`, `GetTextReader_works`, …), all at this assert. History confirms it: the assert was commented out by the author, re-added on reviewer request ("Re-add Assert"), then caused issue #32944 (`SELECT 'test';` crashing), the full revert in PR #32945, and its removal in the replacement PR #33111.

https://github.com/dotnet/efcore/blob/9e69b85b90e0d490fa46dbf25ffac0c3f7747455/src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs#L392-L399

**2. Negative result is never cached — full column scan + PRAGMA query re-runs on every call** (`src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs:329`, confidence 85)

The old `-1` sentinel memoized both outcomes, so the discovery block — an O(FieldCount) metadata scan plus a nested SQL round-trip (`SELECT COUNT(*) FROM pragma_table_info($table) WHERE pk != 0`) — ran at most once per record. The new `RowIds` dictionary is populated only on the two "found" branches (`RowIds.Add` at lines 355 and 387); when no rowid exists for the table, nothing is stored, so `TryGetValue` misses on every subsequent `GetStream`/`GetBytes`/`GetChars`/`GetTextReader` call and the scan + PRAGMA query re-execute per row. Unlike issue 1, this survives Release builds. Bulk-reading blob columns from a composite-PK table regresses from one-time discovery to an extra SQL query per row.

https://github.com/dotnet/efcore/blob/9e69b85b90e0d490fa46dbf25ffac0c3f7747455/src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs#L327-L331

https://github.com/dotnet/efcore/blob/9e69b85b90e0d490fa46dbf25ffac0c3f7747455/src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs#L384-L394

---

**Workflow notes:**

- **Eligibility**: The PR is merged (2024-01-27) — the workflow would normally halt there; I proceeded per your explicit request since nothing was being posted. It was in fact later reverted (#32945) and superseded by #33111.
- **CLAUDE.md**: none exist in dotnet/efcore, so the CLAUDE.md-compliance reviewer was skipped.
- **Filtered out** (below the 80-confidence threshold): the `$"{database}_{table}"` cache key at `SqliteDataRecord.cs:328` can collide across distinct (database, table) pairs (e.g. `main_orders` + `items` vs `main` + `orders_items`), reusing the wrong `RowIdInfo` — real logic flaw, but scored 50 since it requires `ATTACH DATABASE` with colliding underscore names.
- Issue 1 is verified against real execution and the repo's own subsequent history — the revert of this exact commit is direct confirmation, not inference.
