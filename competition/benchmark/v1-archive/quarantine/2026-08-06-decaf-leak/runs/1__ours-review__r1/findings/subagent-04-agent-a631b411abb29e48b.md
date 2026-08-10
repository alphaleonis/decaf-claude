# subagent agent-a631b411abb29e48b

## Verdict

```json
{
  "finding": "the negative rowid-lookup memoization regression",
  "verdict": "confirmed",
  "reason": "Verified directly against git show HEAD:.../SqliteDataRecord.cs and git show HEAD~1:.../SqliteDataRecord.cs. Old code: `_rowidOrdinal = -1;` is set unconditionally at the start of the scan (line 315 of the old file) and `_rowidOrdinal.HasValue` is true regardless of outcome, so both hit and miss are memoized on the SqliteDataRecord instance. New code (HEAD, GetStream ~line 316-405): `RowIds.Add(rowidkey, rowIdForOrdinal)` is only reached from the two `break` branches inside the loop (lines 354-356 and 386-388) — the success paths. If the loop completes with no match (composite PK, WITHOUT ROWID table, view, or computed blob expression), `rowIdForOrdinal` stays null and nothing is added to `RowIds`; the next `GetStream`/`GetBytes` call on the same db_table misses the dictionary again and re-executes the full O(FieldCount) native metadata scan, including a fresh `SELECT COUNT(*) FROM pragma_table_info($table) WHERE pk != 0;` command for INTEGER-PK candidates since `pkColumns` is a method-local reset to -1 each call. I also confirmed `RowIds`/`_rowidOrdinal` live on the SqliteDataRecord instance, and that a single SqliteDataRecord instance persists across all rows of a result set (SqliteDataReader.Read() calls `_record.Read()` on the same instance; only NextResult() creates a new record) — so the memoization genuinely spans multiple rows in both old and new code, meaning the claimed O(rows) regression for the miss case is real and not masked by per-row instance recreation. As a bonus corroborating detail, `Debug.Assert(rowIdForOrdinal != null)` on line 393 of the new code would actually fire on this exact miss path in Debug builds, further evidence the negative-outcome branch was not properly accounted for in the refactor.",
  "corrections": {
    "line": 316,
    "pre_existing": false
  },
  "recommended_severity": "High — agree with broad-reviewer/performance-reviewer over quick-reviewer's Medium. The regression isn't just a repeated in-memory scan; for INTEGER-PK-but-composite-key tables it re-executes a real SQL command (CreateCommand + ExecuteScalar) per GetStream/GetBytes call, which is O(rows) SQL round-trips instead of O(1). Combined with the newly-introduced Debug.Assert that will fault in Debug builds on exactly this path, this warrants High."
}
```
