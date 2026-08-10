# subagent agent-a8c1d62b3f23e526c

The diff exactly matches the cited hunk. All four verification points hold: (1) `RowIds.Add` only occurs on the two found branches; the fall-through path leaves `rowIdForOrdinal == null` uncached, (2) old code cached the negative outcome via `_rowidOrdinal = -1` set unconditionally before the scan began, (3) `GetBytes`/`GetChars`/`GetTextReader` all call `GetStream` unconditionally, and `_record` persists for the whole result set (created once in `NextResult()`), (4) the pragma query is a real `command.ExecuteScalar()` SQL execution inside the scan loop, not merely a C-API call.

```json
{
  "finding": "#4",
  "verdict": "confirmed",
  "reason": "Direct read of the working-tree code confirms RowIds.Add() only fires on the two 'found' branches (lines 355, 387); when the scan completes without a match (composite PK / WITHOUT ROWID / expression column), rowIdForOrdinal stays null and nothing is added to RowIds, so the next GetStream call on that table re-enters the TryGetValue-miss branch and re-runs the full O(FieldCount) scan plus the pragma_table_info command.ExecuteScalar() call. The old code (HEAD~1) set `_rowidOrdinal = -1` unconditionally before the scan, so the negative result was cached permanently after one scan. GetBytes/GetChars/GetTextReader all call GetStream unconditionally, and SqliteDataReader.NextResult() creates `_record` once per statement, so it persists across the whole result set — this is a genuine behavioral regression matching the finding exactly as described, at the cited file:line.",
  "corrections": null
}
```
