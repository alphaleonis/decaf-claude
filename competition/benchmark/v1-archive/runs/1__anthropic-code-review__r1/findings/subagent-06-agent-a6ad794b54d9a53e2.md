# subagent agent-a6ad794b54d9a53e2

## Findings

I traced the file history using `gh api repos/dotnet/efcore/commits ... -f path=...`, which revealed that PR #32770 (the PR under review, `HEAD` in this checkout) was **merged, then reverted three days later, then permanently replaced by a follow‑up PR (#33111) that fixed the exact defect the revert was caused by**. That defect is still present in the merged code under review.

### Issue 1 — `Debug.Assert(rowIdForOrdinal!=null)` asserts a false invariant; this is precisely why PR #32770 was reverted, and the code under review still has the bug

- **File:** `src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs`
- **Line:** 393 — `Debug.Assert(rowIdForOrdinal!=null);`
- **Description:** The assert claims a matching rowid/single-column-PK column is always found by the preceding loop, but three lines later the code explicitly handles the case where it isn't (`if (rowIdForOrdinal == null) return new MemoryStream(GetCachedBlob(ordinal), false);`). The assert directly contradicts the fallback branch right below it, and fires on ordinary, common inputs: any blob-typed value with no backing table (e.g. a bare `SELECT 'test';`) or any table with a composite primary key and no literal `rowid` alias selected — both are legitimate cases the surrounding code was written to handle, not error states.
- **Prior-PR evidence (root cause / conventions):**
  - PR **#23590** ("Handle composite keys in `SqliteDataReader.GetStream()`", fixes #23554) is the PR that established that the rowid ordinal can legitimately remain **unset** for composite‑PK tables, and added the still-present regression test `GetStream_works_when_composite_pk` (now at lines 516–541 in `test/Microsoft.Data.Sqlite.Tests/SqliteDataReaderTest.cs`), which asserts a `MemoryStream` (not `SqliteBlob`) is returned in exactly that scenario. Running that pre-existing test against #32770's merged code hits `Debug.Assert(rowIdForOrdinal!=null)` in a Debug build, since `Id1`/`Id2` are a composite PK and no rowid alias is selected.
  - PR **#32770 itself**: reviewer **ErikEJ** left an inline review comment on this exact line (`original_line: 393`, path `src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs`): **"Re-add Assert"**. The author had apparently commented the assert out while testing, and complied with the request without investigating why it had been removed: **"Puppy error, sorry. Commented for initial checks and later committed. Not intentional. Sorry again! I readded, relaunched the tests and finally committed."** That "readd" is exactly the line now under review.
  - Issue **#32944** ("Assertion failure in SQLite following Blob column PR", filed right after #32770 merged): **"These failures started showing up after #32770."** with a full stack trace: `Process terminated. Assertion failed. at Microsoft.Data.Sqlite.SqliteDataRecord.GetStream(Int32 ordinal) ... line 393 ... at Microsoft.Data.Sqlite.Tests.SqliteDataReaderTest.GetFieldValue_of_TextReader_works()` — triggered by the most basic possible case, `SELECT 'test';` (no backing table at all).
  - PR **#32945**: **"This reverts commit 9e69b85b90e0d490fa46dbf25ffac0c3f7747455 from #32770 due to test failures. See issue #32944."** — the original PR was fully reverted because of this line.
  - PR **#33111** (the replacement PR that superseded #32770 and is the version actually retained in `main`) contains an extra commit whose diff comments out this exact assert:
    ```
    -                Debug.Assert(rowIdForOrdinal!=null);
    +                //Debug.Assert(rowIdForOrdinal!=null);
    +                //debug assertion no more needed:
    +                //rowIdForOrdinal == null => matching rowid not found, MemoryStream returned
    +                //rowIdForOrdinal != null => matching rowid found, SqliteBlob returned
    ```
- **Reason flagged:** prior PR feedback / prior-PR incident — this is not a hypothetical style nit; it is a documented, real defect (reviewer request → reintroduced bug → crash report → full revert → fix-by-removal in the successor PR) tied to this exact line, and the code as merged in the PR under review still contains it unaddressed.

No other findings met the bar (recurring maintainer feedback that #32770 violates, or feedback on #32770 left unaddressed). Other review-thread items on #32770 and earlier PRs (e.g., ajcvickers asking "Any reason not to use a value tuple for this?" re: `RowIdInfo`, or bricelam's self-dismissed musings on `#23590` about loop break ordering / an unlikely composite-key edge case: *"the chances... is so low that it'll probably never matter"*) were style preferences or explicitly non-actionable asides, not enforced conventions, so per the task instructions they are not reported.
