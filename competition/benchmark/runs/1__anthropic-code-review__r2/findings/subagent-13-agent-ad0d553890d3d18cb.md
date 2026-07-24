# subagent agent-ad0d553890d3d18cb

## Summary

I read the full current versions of both PR-modified files (`src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs`, `test/Microsoft.Data.Sqlite.Tests/SqliteDataReaderTest.cs`), diffed them against the pre-PR versions (`HEAD~1`), and cross-checked against the public XML doc comment on `SqliteDataReader.GetStream` (`src/Microsoft.Data.Sqlite.Core/SqliteDataReader.cs:540-542`).

Key finding (most severe): the refactor from a single nullable `_rowidOrdinal` field to a `Dictionary<string, RowIdInfo> RowIds` silently changed the semantics of the `Debug.Assert` that used to be a harmless tautology (`_rowidOrdinal` was pre-seeded to a `-1` sentinel, so `HasValue` was always true) into a real invariant check that now fires whenever no rowid/single-column-INTEGER-PK is found for the table — i.e. exactly the case the very next lines (and the public doc comment "Otherwise, ... a MemoryStream is returned") say is normal, supported behavior. This is provably hit by the pre-existing, unmodified test `GetStream_works_when_composite_pk` (and even the most basic `GetStream_works`), both of which resolve `rowIdForOrdinal == null` by design.

Two more findings reported at lower severity: the new caching only remembers "found" results (never the negative case), regressing the "compute once" caching pattern the class otherwise follows everywhere else; and a stale/misleading comment (`//get len of abuff`) in the new join test that doesn't match what the code actually does.

Full details, line numbers, and reasoning were submitted via the findings report above.
