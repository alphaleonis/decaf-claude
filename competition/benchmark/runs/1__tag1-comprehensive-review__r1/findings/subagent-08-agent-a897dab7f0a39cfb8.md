# subagent agent-a897dab7f0a39cfb8

## Type: `RowIdInfo` (nested in `SqliteDataRecord`)

`src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs:20-30`

```csharp
internal class RowIdInfo
{
    public int Ordinal { get; set; }
    public string TableName { get; set; }

    public RowIdInfo(int ordinal, string tableName)
    {
        Ordinal = ordinal;
        TableName = tableName;
    }
}
```
Cache: `readonly Dictionary<string, RowIdInfo> RowIds = new Dictionary<string, RowIdInfo>();` (`SqliteDataRecord.cs:39`), keyed by `$"{blobDatabaseName}_{blobTableName}"` (`SqliteDataRecord.cs:328`), populated at `SqliteDataRecord.cs:354-355` and `:386-387`, consumed only via `rowIdForOrdinal.Ordinal` at `SqliteDataRecord.cs:402`.

### Invariants Identified

1. **"Once a rowid ordinal is resolved for a (database, table) pair, it never changes for the life of this `SqliteDataRecord`."** — the actual reason the type/cache exists. [Confidence 95] — supported by the PR's own title ("issue with multiple Blob columns") and by the diff replacing a single per-record `_rowidOrdinal` field with a per-table dictionary.
2. **`TableName` should equal the table part of the dictionary key it's stored under.** [Confidence 95] — true by construction (the value passed at `:354`/`:386` is already filtered to equal `blobTableName`, `SqliteDataRecord.cs:345-349`), but nothing in the type enforces or uses this — it's a coincidence of caller discipline, not a modeled invariant.
3. **Implicit, unmodeled invariant: "no rowid ordinal exists for this table" (WITHOUT ROWID / composite PK).** Not represented by `RowIdInfo` at all — represented instead by *absence of a dictionary entry*, which is indistinguishable from "not yet searched." [Confidence 95, verified by grep + reading `GetStream`]

### Is `TableName` ever read? 

**No.** Confirmed by `grep -rn "\.TableName\b"` across `src/` and `test/`: every hit is either the constructor/property declaration itself or unrelated `TableName` members on completely different types (`ModificationCommand`, `RelationalAnnotationNames.TableName`, `DataTable.TableName`, etc.). `RowIdInfo.TableName` is write-only, dead state that is redundant with the dictionary key itself (`blobTableName` is already known at every call site that would need it). [Confidence 95]

### Ratings

- **Encapsulation: 2/10**
  Both properties are `{ get; set; }` — fully mutable after construction, so any code with a reference to a cached `RowIdInfo` (the nested class is `internal`, i.e. assembly-wide, not `private`) can silently corrupt the cache (`entry.Ordinal = wrong` would poison every subsequent `GetStream` call for that table with no defense). No factory, no validation surface, no read-only view.

- **Invariant Expression: 2/10**
  Nothing communicates "immutable once cached." Nothing expresses that `Ordinal` must be `>= 0` and within `FieldCount`. Nothing expresses the "not found" state — that case is smuggled in as *dictionary miss*, conflating "haven't looked yet" with "looked and there is no rowid," which is exactly the ambiguity the deleted `int? _rowidOrdinal` + `-1` sentinel used to make explicit (crudely, but explicitly) via `HasValue`/`-1`. The new design has strictly less expressive power for that state than what it replaced.

- **Invariant Usefulness: 4/10**
  The core fix (scoping the cached ordinal per `(database, table)` instead of per-record) is real and useful — it fixes a genuine bug where a single blob-reading `SqliteDataRecord` reading columns from two different tables would reuse the first table's rowid ordinal for the second. But: (a) `TableName` is dead weight that adds no value, and (b) the "not found" result (composite PK / WITHOUT ROWID tables) is no longer cached at all — see below, this is a caching-completeness regression versus the old sentinel.

- **Invariant Enforcement: 1/10**
  Zero validation in the constructor (no null/empty check on `tableName`, no range check on `ordinal`). `Debug.Assert(rowIdForOrdinal!=null)` at `SqliteDataRecord.cs:393` directly contradicts a legitimate, tested, reachable outcome (see Concerns). Cache key is raw string concatenation with no collision guard. Nothing prevents inserting a stale/mismatched entry.

### Strengths
- Fixes a real correctness bug: the old single `private int? _rowidOrdinal` field (`SqliteDataRecord.cs:37` pre-diff) was shared across *all* tables a given `SqliteDataRecord` might expose blob columns for, so reading blobs from table A then table B on the same record could silently reuse table A's ordinal (or a stale `-1`) for table B. Scoping the cache per `(database, table)` is the right idea.
- The consuming code (`GetStream`) still correctly falls back to `MemoryStream`/`GetCachedBlob` when no rowid ordinal is available (`SqliteDataRecord.cs:396-398`), so the *runtime behavior* for the not-found case is still correct even though it's not cached.

### Concerns

1. **Negative-result caching lost (perf regression on the "not found" path).** [Confidence 90, file:line `SqliteDataRecord.cs:329-394`]
   When the loop completes without finding a rowid alias or single-column INTEGER PK (WITHOUT ROWID tables, composite PKs — exercised by the existing test `GetStream_works_when_composite_pk`, `test/Microsoft.Data.Sqlite.Tests/SqliteDataReaderTest.cs:516-541`), nothing is added to `RowIds`. Every subsequent `GetStream` call on any blob column of that table re-runs the full `O(FieldCount)` scan **and** re-issues the `SELECT COUNT(*) FROM pragma_table_info($table)` round-trip (`SqliteDataRecord.cs:375-381`) on *every single call*, for the life of the record. The old code, despite its cross-table bug, at least cached the negative result (`-1`) once per record. This is a genuine behavioral regression the type doesn't model or defend against.

2. **`Debug.Assert` now asserts something false on a legitimate, tested path.** [Confidence 85, `SqliteDataRecord.cs:393`]
   ```csharp
   Debug.Assert(rowIdForOrdinal!=null);
   ```
   sits between the resolution loop and the `if (rowIdForOrdinal == null)` fallback (`:396`). For composite-PK/WITHOUT-ROWID tables the loop legitimately exits with `rowIdForOrdinal == null` (that's precisely what `GetStream_works_when_composite_pk` exercises). In Debug builds this assert is false whenever that path is hit. [Inference, not executed in this environment: no `dotnet` toolchain available to run the test and confirm process-level impact] — the logical contradiction itself is verified by static reading of the code and the test; whether it manifests as a hard failure depends on Debug.Assert's configured listener/build configuration, which I did not verify by running the suite.

3. **String-concatenated composite key is collision-prone.** [Confidence 80, `SqliteDataRecord.cs:328`]
   `$"{blobDatabaseName}_{blobTableName}"` — SQLite identifiers (database aliases via `ATTACH`, table names) may themselves contain `_`. `(db="main", table="a_b")` and `(db="main_a", table="b")` both produce the key `"main_a_b"`. Narrow in practice (requires underscore-containing attached-database aliases) but entirely undefended — a proper composite key removes the risk for free.

4. **Dead field / over-broad type.** [Confidence 95, `SqliteDataRecord.cs:23`]
   `TableName` is never read (see grep above). The type carries state purely to satisfy a constructor signature that mirrors the loop's local variable, not because any invariant needs it.

5. **Style/consistency nits** (low severity): `readonly Dictionary<string, RowIdInfo> RowIds` (`SqliteDataRecord.cs:39`) breaks the file's `_camelCase` private-field convention (compare `_connection`, `_blobCache`) by using `PascalCase` with no underscore; local `rowidkey` (`:328`) likewise breaks the file's `camelCase` local convention (compare `blobDatabaseName`, `blobTableName`); stray blank line added at `SqliteDataRecord.cs:17`; `rowIdForOrdinal!=null` (`:393`) missing spaces around `!=`.

### Recommended Improvements

1. **Drop `RowIdInfo` entirely; key the cache by table and cache an `int?` ordinal (found-or-not-found), restoring negative-result caching:**
   ```csharp
   private readonly Dictionary<(string Database, string Table), int?> _rowIdOrdinals = new();
   ...
   var key = (blobDatabaseName, blobTableName);
   if (!_rowIdOrdinals.TryGetValue(key, out var rowIdOrdinal))
   {
       // existing resolution loop, assigning rowIdOrdinal = i and breaking as today
       _rowIdOrdinals[key] = rowIdOrdinal; // cache the miss too — restores old sentinel behavior, correctly scoped per table
   }
   if (rowIdOrdinal == null)
   {
       return new MemoryStream(GetCachedBlob(ordinal), false);
   }
   var rowid = GetInt64(rowIdOrdinal.Value);
   ```
   This removes the dead `TableName` field, removes the string-concatenation collision risk (tuple keys use structural equality), and fixes the caching-completeness regression — all with less code than the current `RowIdInfo` class plus its two `RowIds.Add(...)` call sites.

2. **If a named wrapper is still wanted for readability**, make it a `private readonly record struct` holding just the ordinal (e.g. `private readonly record struct RowIdCacheEntry(int? Ordinal);`), not a mutable class with a redundant `TableName`. Records give free value-based `Equals`/`ToString`, and `readonly`/positional syntax makes "immutable after construction" the default rather than something the reader has to infer.

3. **Fix or remove the `Debug.Assert` at `SqliteDataRecord.cs:393`.** Given `rowIdForOrdinal == null` is a legitimate, already-tested outcome, the assert is simply wrong and should be deleted (the `if (rowIdForOrdinal == null)` check two lines below already handles the case correctly).

4. **Minor:** rename `RowIds` → `_rowIdOrdinals` (or similar) and `rowidkey` → `rowIdKey` to match the file's existing naming conventions, once the type itself is simplified per (1).

Files/lines referenced: `/home/decaf/code/decaf-claude/competition/benchmark/repos/1/src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs:19-30,39,316-405`; test evidence at `/home/decaf/code/decaf-claude/competition/benchmark/repos/1/test/Microsoft.Data.Sqlite.Tests/SqliteDataReaderTest.cs:516-541`.
