# subagent agent-a99db62522e13335b

## Test Review: `SqliteDataReaderTest.GetBytes_works_streaming_join` (test/Microsoft.Data.Sqlite.Tests/SqliteDataReaderTest.cs)

### Verification of regression-guard validity (static reasoning)

Traced both code paths by hand against `src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs` and `SqliteBlob.cs`:

- **With the fix** (per-`{db}_{table}` dictionary): first `GetBytes(1,…)` resolves and caches `A`'s rowid ordinal (0, value `AID=1`), returns `X'01020304'`[1..2] = `[0x02,0x03]` — matches. Second `GetBytes(3,…)` misses the cache for key `main_B`, re-scans, finds `B`'s own rowid alias (ordinal 2, value `BID=1000`), opens `SqliteBlob(main, B, VALUE, rowid=1000)`, returns `X'05060708'`[1..2] = `[0x06,0x07]` — matches.
- **Without the fix** (single `_rowidOrdinal` field): first call sets `_rowidOrdinal=0` (table `A`'s rowid ordinal). Second call skips the scan entirely (already has a value) and reuses ordinal 0 — i.e., `GetInt64(0)=1` (that's `A.ID`, not `B.ID`) — then calls `SqliteBlob(main, "B", "VALUE", rowid=1, readOnly)`. Table `B` has no row with rowid `1` (its only row has `ID=1000`), so `sqlite3_blob_open` returns a non-OK result code and `SqliteException.ThrowExceptionForRC` throws before the second `Assert.Equal` is ever reached.

So the test does fail (via an uncaught `SqliteException`, not merely a wrong-value assertion) on the pre-fix code, and passes with the fix. It is a genuine, working regression guard for issue #32747 — not a false positive.

### Summary
| Severity | Count |
|----------|-------|
| CRITICAL | 0     |
| HIGH     | 0     |
| MEDIUM   | 1     |
| LOW      | 2     |

### MEDIUM Issues

#### 1. No coverage of the no-rowid fallback path in combination with the fix's changed caching in `SqliteDataReaderTest.cs`

**Problem:** The production fix changed more than "which ordinal is cached" — it also changed how the negative case is handled. Previously `_rowidOrdinal` was set to the sentinel `-1` and permanently cached once a table was found to have no single-rowid alias (e.g., composite PK). After the fix, when no rowid is found, `rowIdForOrdinal` stays `null` and is **never added to `RowIds`**, so every subsequent `GetStream` call for that column re-runs the full column-metadata scan. This is a real behavioral difference the PR's own diff introduces, but no test (new or existing) exercises the no-rowid fallback path *inside a JOIN* to confirm per-table caching and the fallback interact correctly (e.g., a join where one side has a composite PK / no rowid alias and the other has a normal rowid). The existing `GetStream_works_when_composite_pk` test is single-table, unmodified by this PR, and only calls `GetStream` once, so it can't reveal the repeated-rescans-on-every-call behavior change either.

**Confidence:** 50 — the gap is real and traceable to the diff, but its practical impact (perf-only vs. correctness) can't be fully confirmed from the test file alone.

**Pre-existing:** no — this absence is created by this change (the dictionary-based caching and its interaction with the no-rowid branch are new).

**Suggested addition:** A join test where one joined table has a composite primary key (no single rowid alias) and the other has a normal rowid, asserting the rowid-backed column still returns correct bytes and the composite-pk column still falls back to `MemoryStream`/full-row buffering, exercised across multiple `GetStream`/`GetBytes` calls on the same reader.

---

### LOW Issues

#### 2. Leftover debug `Console.WriteLine` in `SqliteDataReaderTest.cs:159` (test as added, join test body)

**Problem:** `Console.WriteLine($"A.ID={reader.GetInt32(0)} B.ID={reader.GetInt32(2)}");` is debug scaffolding left in the committed test. It doesn't assert anything and adds noise to test output; no sibling test in this file does this.

**Confidence:** 100

**Pre-existing:** no

**Current Code:**
```csharp
//reading fields that does not involve blobs should be ok
Console.WriteLine($"A.ID={reader.GetInt32(0)} B.ID={reader.GetInt32(2)}");
```

**Suggested Fix:**
```csharp
// reading fields that do not involve blobs should still work
Assert.Equal(1, reader.GetInt32(0));
Assert.Equal(1000, reader.GetInt32(2));
```
(Turns the "should be ok" comment into an actual, checked assertion instead of a print statement — also adds minor extra coverage for the non-blob columns.)

#### 3. Informal, changelog-style comment in `SqliteDataReaderTest.cs:170`

**Problem:** `//this was failing. now should be fixed` narrates the bug-fix history rather than documenting current intended behavior; it also doesn't explain *why* (per-table rowid caching), which is the useful information for a future reader.

**Confidence:** 100

**Pre-existing:** no

**Current Code:**
```csharp
reader.GetBytes(3, 1, bbuff, 0, bbuff.Length);  //this was failing. now should be fixed
```

**Suggested Fix:**
```csharp
// B's blob must resolve B's own rowid (ID=1000), not A's cached rowid ordinal (see #32747).
reader.GetBytes(3, 1, bbuff, 0, bbuff.Length);
```

---

### Probe Requests

#### 1. `GetBytes_works_streaming_join` in `test/Microsoft.Data.Sqlite.Tests/SqliteDataReaderTest.cs`
**Remove:** `src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs` — in `GetStream`, neutralize the per-table cache key so it collapses back to a single shared key, e.g. change
```csharp
string rowidkey = $"{blobDatabaseName}_{blobTableName}";
```
to
```csharp
string rowidkey = "single";
```
(this reproduces the pre-fix "one cached rowid ordinal for the whole reader" bug without needing to hand-revert the full dictionary refactor).

**Expect:** `GetBytes_works_streaming_join` fails — either a `SqliteException` thrown from `SqliteBlob`'s constructor on the second `GetBytes(3, …)` call (rowid `1` doesn't exist in table `B`), or, if it happens not to throw, `Assert.Equal([0x06, 0x07], bbuff)` fails because the wrong row's bytes are read.

**Relates to:** confidence check on the regression guard (confirms the static trace above).

### Recommendations

1. Remove the `Console.WriteLine` and either drop the "reading non-blob fields" line entirely or replace it with real assertions.
2. Reword the inline comment to explain the invariant being verified (per-table rowid resolution), not the bug-fix timeline.
3. Consider adding a join test that mixes a rowid-bearing table with a composite-PK (no-rowid) table to cover the fallback path's interaction with the new per-table cache, since this PR changed that path's caching semantics (negative result no longer cached).
