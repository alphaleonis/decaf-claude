# subagent agent-adfb55d24bfe173e2

## Verdict

I traced the exact execution path in both the pre-change and post-change code, and reproduced the failure scenario for the cited test.

**Old code** (`git show HEAD~1:src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs`, lines 313-317):
```csharp
if (!_rowidOrdinal.HasValue)
{
    _rowidOrdinal = -1;   // <-- sentinel set BEFORE the loop runs
    ...
    Debug.Assert(_rowidOrdinal.HasValue);   // always true: -1 is a value, not null
```
Because `_rowidOrdinal` is pre-seeded to `-1` before the loop, `_rowidOrdinal.HasValue` is unconditionally `true` by the time the assert runs, regardless of whether the loop found anything. The old assert was tautological and could never fire.

**New code** (on disk, `src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs:327-393`):
```csharp
RowIdInfo? rowIdForOrdinal = null;   // no sentinel
...
Debug.Assert(rowIdForOrdinal!=null);   // now a real, falsifiable check
```
`rowIdForOrdinal` is left `null` unless the loop actually finds a `rowid` alias column or a single-column INTEGER PK. If the loop completes (or is skipped entirely) without a match, the assert now genuinely fires.

I confirmed reachability against the actual test file (`test/Microsoft.Data.Sqlite.Tests/SqliteDataReaderTest.cs`):

- `GetStream_works_when_composite_pk` (lines 516-541): table `DataTable(Id1 INTEGER, Id2 INTEGER, Data BLOB, PRIMARY KEY (Id1, Id2))`, `GetStream(2)` on `Data`. Loop visits `Id1` (i=0) and `Id2` (i=1): both are `INTEGER` with `primaryKey != 0`, but the `pragma_table_info` count yields `pkColumns == 2`, so `pkColumns == 1L` is false both times — no assignment. `i == ordinal` skips column 2. Loop exits with `rowIdForOrdinal == null` → assert fires.
- Even more basic: `GetStream_works` (lines 373-392), `SELECT x'427E5743';` — a single-column expression result with `FieldCount == 1`, `ordinal == 0`. The loop's only iteration has `i == ordinal`, so it `continue`s immediately without ever executing the body. `rowIdForOrdinal` stays `null` → assert fires on this basic, pre-existing test too, not just the composite-pk one.

In the old code, both of these same tests hit `_rowidOrdinal = -1` and the tautological `HasValue` check, so the assert never fired historically — confirming the regression is introduced by this diff, not pre-existing.

`Debug.Assert` is `[Conditional("DEBUG")]`, and the standard SDK-generated test csproj's default `dotnet test` configuration (`Debug`) defines `DEBUG`, so this reproduces under ordinary Debug test runs, consistent with the finding's framing.

The citation (`SqliteDataRecord.cs:393`) is accurate, and the fix suggestion (drop the assert or use a true negative-cache sentinel) correctly addresses the defect.

```json
{
  "finding": "#1",
  "verdict": "confirmed",
  "reason": "Traced both HEAD~1 and HEAD versions of GetStream: the old code pre-set `_rowidOrdinal = -1` before the loop, making `Debug.Assert(_rowidOrdinal.HasValue)` tautologically true and unfireable; the new code drops that sentinel, so `Debug.Assert(rowIdForOrdinal!=null)` at line 393 is a real check that fires whenever the loop completes without finding a rowid/single-column-PK match. Verified this is reached by the existing tests GetStream_works_when_composite_pk (composite PK, pkColumns==2 so no match) and even the more basic GetStream_works (single-column expression result where the loop body never executes because i==ordinal on its only iteration) — both pass today only because the old sentinel made the assert vacuous.",
  "corrections": {
    "line": 393,
    "pre_existing": false
  }
}
```
