# subagent agent-a53d681f9a231085e

# Code Review: Microsoft.Data.Sqlite.Core - Blob rowid caching fix (PR #32770)

## Findings

```json
[
  {
    "file": "src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs",
    "line": 393,
    "severity": "Medium",
    "category": "other",
    "issue": "[BUG_LOGIC] Debug.Assert(rowIdForOrdinal != null) is no longer vacuously true and can now genuinely fail. In the old code, _rowidOrdinal was unconditionally set to the sentinel -1 before the discovery loop ran, so `Debug.Assert(_rowidOrdinal.HasValue)` always passed regardless of whether a rowid column was found. The rewrite dropped the sentinel: rowIdForOrdinal stays null unless the loop breaks on a match. For any blob column whose table has no discoverable rowid/single-INTEGER-PK column (e.g. a WITHOUT ROWID table, a view, or a composite-PK table) — a case the very next `if (rowIdForOrdinal == null)` block is explicitly designed to handle via the GetCachedBlob fallback — the loop completes without a match and this assert now trips in Debug builds, which by default aborts/terminates the process outside a debugger rather than gracefully falling through to the intended fallback path.",
    "fix": "Remove the assert (it no longer holds a real invariant) or restructure so a `found` sentinel/bool tracks whether a match was located, and only assert when the code path guarantees one must exist. At minimum stop asserting non-null before the very branch that explicitly handles the null case.",
    "confidence": 100,
    "pre_existing": false
  },
  {
    "file": "src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs",
    "line": 328,
    "severity": "Medium",
    "category": "other",
    "issue": "[BUG_LOGIC] The RowIds cache key is built by naive string concatenation `$\"{blobDatabaseName}_{blobTableName}\"` with `_` as a separator. SQLite identifiers can legally contain underscores (e.g. database `x`, table `a_b` produces key `x_a_b`; database `x_a`, table `b` produces the same key `x_a_b`). Two distinct (database, table) pairs can collide onto the same dictionary key, causing the rowid ordinal discovered for one table to be reused for a blob column belonging to a different table — reintroducing the exact class of bug this PR fixes (issue #32747), just triggered by underscore-containing names instead of multi-table joins.",
    "fix": "Use a composite key that can't collide, e.g. a `(string database, string table)` tuple/ValueTuple as the dictionary key (tuples have correct structural equality), or a delimiter that cannot appear in a SQLite identifier combined with escaping, instead of plain string concatenation.",
    "confidence": 75,
    "pre_existing": false
  },
  {
    "file": "src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs",
    "line": 355,
    "severity": "Medium",
    "category": "performance",
    "issue": "[BUG_LOGIC] The \"no rowid found\" result is no longer cached. In the old code, `_rowidOrdinal = -1` was set before the loop and never reverted, so once a table was determined to have no usable rowid, that negative result was cached and subsequent GetStream calls short-circuited immediately (`_rowidOrdinal.Value < 0` check) without re-running discovery. In the new code, `RowIds.Add(...)` only happens inside the two success branches (lines 355 and 387); when the loop finds no match, nothing is added to RowIds, so the next call for the same (database, table) key re-enters the full discovery loop every time — including a nested `_connection.CreateCommand()` + `ExecuteScalar()` SQL query for tables with an INTEGER PRIMARY KEY of unknown column count. This is a caching regression that reintroduces repeated per-call overhead (and command execution against the shared connection) that the original sentinel design specifically avoided.",
    "fix": "Cache negative results too, e.g. by storing a nullable/sentinel RowIdInfo (or a `found: bool` wrapper) in RowIds even when no rowid column is located, so the miss is only computed once per (database, table) pair, matching the pre-existing caching contract.",
    "confidence": 100,
    "pre_existing": false
  },
  {
    "file": "src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs",
    "line": 23,
    "severity": "Low",
    "category": "unused-code",
    "issue": "[QUALITY_DUPLICATION] RowIdInfo.TableName is set on every construction (lines 354, 386) but never read anywhere — it duplicates blobTableName, which is already known at the call site (the loop only reaches these lines after confirming `tableName == blobTableName`). Dead state increases the object's footprint and gives a false impression it's used for lookup/validation.",
    "fix": "Remove the TableName property from RowIdInfo (keep only Ordinal), or if it's meant for future diagnostics, note that explicitly; otherwise it's unused surface to maintain.",
    "confidence": 100,
    "pre_existing": false
  },
  {
    "file": "src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs",
    "line": 396,
    "severity": "Low",
    "category": "other",
    "issue": "[QUALITY_ERROR_HANDLING] No test exercises the \"no discoverable rowid\" fallback path (WITHOUT ROWID table, view, or composite-PK table) against the new dictionary-based implementation. This is exactly the path made newly assert-fragile by finding #1 above, and the only regression test added (GetBytes_works_streaming_join) doesn't cover it — both joined tables in the test have a single-column INTEGER PRIMARY KEY, so the fallback branch is never reached.",
    "fix": "Add a test with a WITHOUT ROWID table (or a table with a composite primary key) whose blob column is read via GetStream/GetBytes, verifying the GetCachedBlob fallback still works and no assert fires.",
    "confidence": 50,
    "pre_existing": false
  }
]
```

## Considered But Not Flagged

- **Dictionary thread-safety**: `RowIds` is a plain `Dictionary<string, RowIdInfo>` with no locking. Not flagged — `SqliteDataRecord`/readers were never documented or designed for concurrent access from multiple threads (same as the prior single `int?` field), so this isn't a regression introduced by the change.
- **`RowIds` field naming (PascalCase, no `_` prefix, no explicit `private`)**: inconsistent with every other private field in this file (`_connection`, `_blobCache`, etc.), and `.editorconfig` has no explicit private-field naming rule to cite as a documented violation. This is sibling-convention drift discoverable only by comparing to neighboring code, which is `consistency-reviewer`'s scope, not mine — omitted here.
- **Extra blank line after `namespace Microsoft.Data.Sqlite\n{`** (line 17) and **missing spaces around `!=`** in `Debug.Assert(rowIdForOrdinal!=null)` (line 393): real, verifiable, but purely cosmetic nits with no behavioral consequence — below the bar worth a standalone finding at Low severity/High confidence given the more substantive issues above; mentioning here for completeness rather than as a separate finding.
- **`RowIdInfo.TableName` non-nullable without `?` in a nullable context**: could theoretically hold a null from `utf8_to_string()`, but the pattern matches how `blobTableName`/`blobDatabaseName` are already declared elsewhere in this same file, so it's consistent with existing (pre-existing) conventions, not a new issue.
- **Repeated `_connection.CreateCommand()` execution against the same connection while a reader is mid-step**: already present in the pre-existing (original) code on first discovery; the change makes it happen more often (see finding #3) but doesn't introduce a new category of risk — nested read-only queries against the same SQLite connection during a read were already relied upon.

## Residual Risks

- The Debug.Assert regression (finding #1) is dormant until a query joins a blob column from a table without a discoverable rowid; it will not be exercised by the existing test suite, so it can ship silently and only surface as a crash in a consumer's Debug-configuration test run.
- The key-collision bug (finding #2) only manifests with underscore-containing database/table names, which are common in real-world schemas (snake_case naming), making this a plausible field failure despite low likelihood of being hit in EF Core's own test suite.
