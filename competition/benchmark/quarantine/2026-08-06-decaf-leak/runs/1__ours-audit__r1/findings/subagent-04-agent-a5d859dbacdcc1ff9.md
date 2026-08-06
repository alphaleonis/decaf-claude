# subagent agent-a5d859dbacdcc1ff9

## Spec Compliance Review — GitHub issue #32747 (PR #32770)

**Spec source**: linked (closing "Fixes #32747") — reviewed at full strength.

### Verdict
The fix resolves the reported bug. The root cause was a single `_rowidOrdinal` cache shared across *all* blob columns: the first `GetStream`/`GetBytes` call resolved and cached a rowid ordinal for whichever blob's table it hit first, and every later blob column reused that same ordinal regardless of its own table — producing `no such rowid: N` when the second table's rowid space didn't contain that value. Replacing it with `Dictionary<string, RowIdInfo> RowIds` keyed by `{database}_{table}` gives each (database, table) pair its own resolved ordinal, so the two-table JOIN scenario now resolves each blob's rowid independently. The added test `GetBytes_works_streaming_join` faithfully reproduces the repro class (JOIN of A and B, read A's blob then B's blob) and asserts correct bytes for both.

On the length-probe question: the issue's repro used `GetBytes(…, null, 0, 0)` to read length first. That path is functionally covered — `GetBytes` unconditionally routes through `GetStream(ordinal)` (line 276) before branching on `buffer == null`, so the null-buffer length probe goes through the exact same per-table cache. It is covered by the fix mechanism, though not exercised explicitly by the new test.

### Findings (JSON)

```json
[
  {
    "file": "src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs",
    "line": 355,
    "severity": "Medium",
    "category": "spec-compliance",
    "issue": "[SPEC_EDGE_CASE] The rowid cache is keyed by underlying table name ({database}_{table}), not by result-set alias. A self-join of one table under two aliases (e.g. `SELECT a1.blob, a2.blob FROM A a1 JOIN A a2 ON ...`) yields the same key for both blob columns, so the second blob reuses the first alias's rowid ordinal. This is the same failure class the fix targets, left unresolved for aliased same-table joins — and because both aliases' rowids are valid in table A, it can return silently wrong bytes rather than throwing.",
    "fix": "Include the blob column's own result ordinal (or resolved alias) in the cache key / RowIdInfo lookup so aliases of the same base table resolve independently.",
    "confidence": 50,
    "pre_existing": false
  },
  {
    "file": "src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs",
    "line": 22,
    "severity": "Low",
    "category": "spec-compliance",
    "issue": "[SPEC_UNCOVERED] RowIdInfo.TableName is set at construction (lines 354, 386) but never read anywhere — the table is already encoded in the dictionary key. Unused state introduced by the change, accounted for by no requirement.",
    "fix": "Drop the TableName property/parameter; store only the Ordinal (or replace RowIdInfo with a Dictionary<string,int>).",
    "confidence": 75,
    "pre_existing": false
  }
]
```

### Requirement Coverage Matrix

| Req | Description | Status | Evidence |
|-----|-------------|--------|----------|
| R1 (functional) | JOIN of two tables each with a BLOB column; reading the first table's blob then the second's must both succeed | Covered | `SqliteDataRecord.cs:326-405` (per-table dictionary); test `SqliteDataReaderTest.cs` `GetBytes_works_streaming_join` |
| R2 (edge-case) | Length probe via `GetBytes(…, null, 0, 0)` before reading the blob (per issue repro) | Covered (functionally) | `GetBytes` routes through `GetStream` at line 276 before the null-buffer branch, so the probe uses the same per-table cache; not explicitly tested |

### Considered But Not Flagged

- **Negative-result memoization lost (performance, cross-scope).** The pre-fix code memoized the "no accessible rowid" outcome (`_rowidOrdinal = -1`, then `HasValue` short-circuits later calls). The new code only inserts into `RowIds` on a *positive* match; when no rowid column is found, nothing is cached, so every subsequent `GetStream`/`GetBytes`/`GetChars` call re-runs the full `FieldCount` scan (including a `pragma_table_info` query per candidate PK column) for that blob. This is a behavioral/performance deviation from prior code but not a spec requirement, and it is functionally safe (re-scan yields the same null result, and the null path uses `ordinal` directly). Belongs to performance-reviewer.
- **Test does not exercise the null-buffer length probe on a join.** The issue's repro read length first via a null buffer; the new test passes non-null buffers only. Functionally equivalent (shared `GetStream` entry point), so not a fix gap — a test-completeness nuance for test-reviewer.
- **Dictionary key underscore-separator collision** (`db="a",table="b_c"` vs `db="a_b",table="c"`). Theoretical, not spec-relevant, and pre-existing in spirit.
- **`Debug.Assert(rowIdForOrdinal != null)`, formatting/whitespace, `RowIds` non-`_`-prefixed field naming, unused `readonly` field-vs-property style** — code quality, out of spec-compliance scope (quick-reviewer / dotnet-reviewer).

No files were modified. No probes required.
