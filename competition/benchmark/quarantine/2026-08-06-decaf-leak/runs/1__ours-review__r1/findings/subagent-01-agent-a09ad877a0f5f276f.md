# subagent agent-a09ad877a0f5f276f

```json
{
  "finding": "Re-added Debug.Assert(rowIdForOrdinal != null) fires on the legitimate no-rowid path",
  "verdict": "confirmed",
  "reason": "Read src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs lines 316-405: rowIdForOrdinal starts null (line 327) and is only ever assigned inside the two branches that also do RowIds.Add (lines 354-355, 386-387); for a composite-PK table with no rowid alias selected, pkColumns resolves to 2 so the pkColumns==1L branch never fires, leaving rowIdForOrdinal null after the loop and tripping Debug.Assert(rowIdForOrdinal!=null) at line 393, immediately before the null-handling code at lines 396-398 that treats this as a legitimate outcome. `git show 9e69b85` confirms the pre-PR code unconditionally set `_rowidOrdinal = -1;` before the loop (a valid int? value), making the old assert trivially true; that unconditional sentinel assignment was removed in the refactor to the RowIds dictionary, so the invariant the assert encodes no longer holds. The existing test GetStream_works_when_composite_pk (test/Microsoft.Data.Sqlite.Tests/SqliteDataReaderTest.cs:516-541) exercises exactly this scenario (composite PK, no rowid in SELECT list) and expects a MemoryStream result, confirming this is a legitimate, tested code path that the assert now contradicts.",
  "corrections": null
}
```
