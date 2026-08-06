# subagent agent-a302350236e92f1e2

I have enough to complete the review. Let me record my analysis.

## Requirement mapping

**Spec (GitHub #32747, linked — full strength):** A joined query selecting blob columns from two different tables must let `GetBytes`/`GetStream` read both blobs in one row. The bug was a single cached `_rowidOrdinal` that, once set from table A's rowid, was wrongly reused for table B, producing `SQLite Error 1: 'no such rowid'`.

**Core fix verdict:** The change correctly addresses the reported scenario. Replacing `int? _rowidOrdinal` with a `Dictionary<string, RowIdInfo>` keyed by `"{database}_{table}"` means each table resolves and caches its own rowid ordinal independently, so `GetInt64(rowIdForOrdinal.Ordinal)` reads the right table's rowid for each blob column (SqliteDataRecord.cs:328-402). The added test reproduces the reported A-then-B ordering within a single row (reads AVALUE at ordinal 1, then BVALUE at ordinal 3), which is exactly where the original caching bug manifested. Ordering is covered.

However, the refactor dropped the original `-1` sentinel that handled the "no rowid found" fallback, introducing a regression, and left an unused field.

---

```json
[
  {
    "file": "src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs",
    "line": 393,
    "severity": "High",
    "category": "spec-compliance",
    "issue": "[SPEC_DEVIATION] The rowid-lookup rewrite drops the original `-1` sentinel, so when no rowid ordinal exists for a table (composite PK, WITHOUT ROWID table, or computed/expression blob) `rowIdForOrdinal` stays null and `Debug.Assert(rowIdForOrdinal != null)` fires. The original code assigned `_rowidOrdinal = -1` first, so `Debug.Assert(_rowidOrdinal.HasValue)` always held and the code fell through to the MemoryStream fallback. This regresses the no-rowid fallback path and, in Debug builds (dotnet test's default config), trips the assertion for the existing passing test `GetStream_works_when_composite_pk` (SELECT with no rowid alias, composite PK -> ordinal 2 blob).",
    "fix": "Either remove the now-incorrect `Debug.Assert(rowIdForOrdinal != null)` (null is a legitimate 'no rowid, use cached blob' outcome), or cache a negative sentinel entry so the not-found result is both asserted-safe and memoized. The subsequent `if (rowIdForOrdinal == null) return new MemoryStream(GetCachedBlob(ordinal), false);` already handles the value correctly; only the assert is wrong.",
    "confidence": 75,
    "pre_existing": false
  },
  {
    "file": "src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs",
    "line": 23,
    "severity": "Low",
    "category": "spec-compliance",
    "issue": "[SPEC_UNCOVERED] `RowIdInfo.TableName` is captured at both construction sites (lines 354, 386) but never read anywhere. The rowid resolution only ever consumes `.Ordinal`. This is scope creep introduced by the fix — a stored field the spec does not require and no code path uses.",
    "fix": "Drop the `TableName` property and simplify `RowIdInfo` to carry just the ordinal (or replace the class with a plain `int`), since the dictionary key already encodes database+table.",
    "confidence": 100,
    "pre_existing": false
  }
]
```

## Requirement Coverage Matrix

| Req | Description | Status | Evidence |
|-----|-------------|--------|----------|
| R1 | Reading blob columns from two different tables in one joined query succeeds (functional) | Covered | Per-table rowid cache, SqliteDataRecord.cs:327-355, 386-388; keyed lookup at :328-329; `GetInt64(rowIdForOrdinal.Ordinal)` at :402 |
| R2 | The A-then-B read ordering from the repro must work (edge-case/ordering) | Covered | Test `GetBytes_works_streaming_join` reads AVALUE (ord 1) then BVALUE (ord 3) in one row, SqliteDataReaderTest.cs:149-183 |
| R3 | Existing single-table / rowid / no-rowid blob-streaming behavior preserved (implicit constraint) | Deviated | No-rowid fallback now trips `Debug.Assert` at :393; regresses `GetStream_works_when_composite_pk` (SqliteDataReaderTest.cs:516) in Debug builds |

## Considered But Not Flagged

- **Multi-row iteration not tested.** The repro wraps the reads in `while (reader.Read())`; the added test reads a single row. Not a code gap — the cross-table caching bug manifests within one row, and the per-table cache (column ordinals are row-invariant) is correctly reused across rows. Adequate coverage of the reported failure. This is a minor test-thoroughness note (test-reviewer scope), not a spec gap.
- **Fallback path no longer memoized (minor perf deviation).** The original `-1` sentinel meant a table with no rowid was resolved once; the new code caches nothing on the not-found path, so every `GetStream` call for such a column re-runs the full column loop plus the `pragma_table_info` query. Real behavioral divergence but low impact and squarely performance-reviewer scope; folds into the fix for the line-393 finding if a sentinel entry is cached.
- **Key collision `"{database}_{table}"`.** Theoretically `db="a",table="b_c"` and `db="a_b",table="c"` both map to `a_b_c`. Not reachable in the spec scenario and astronomically unlikely; noted only for completeness.
- **`RowIds` field naming / style.** Non-private, PascalCase, no `_` prefix — diverges from sibling fields (`_blobCache`, `_typeCache`). Consistency-reviewer scope, not spec compliance.
- **Blank line added after `namespace {` (line 17).** Cosmetic; out of scope.

Provenance note: spec is `linked` (issue #32747 via "Fixes #32747" in PR #32770), reviewed at full strength — no severity cap applied. The `[Inference]` element in the line-393 finding is the exact dotnet-test runner reaction to a failed `Debug.Assert`; what is certain from the code alone is that the assertion condition now evaluates false on a legitimate, already-tested input where it previously always held.

Relevant files: `/home/decaf/code/decaf-claude/competition/benchmark/repos/1/src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs` and `/home/decaf/code/decaf-claude/competition/benchmark/repos/1/test/Microsoft.Data.Sqlite.Tests/SqliteDataReaderTest.cs`.
