# subagent agent-a44e12ff9370fd694

Based on my analysis of the code and the git diff, I can now confirm the finding:

**Verification of claims:**

1. **Not-found path adds nothing to `RowIds`**: ✓ Confirmed. Lines 355 and 387 (where entries are added to `RowIds`) are inside conditional blocks that `break` when a rowid is found. If no rowid is found, neither executes, leaving the dictionary unchanged.

2. **Old code memoized negatives via `-1` sentinel**: ✓ Confirmed. The diff shows the old code had `_rowidOrdinal = -1;` executed on every first call within the `if (!_rowidOrdinal.HasValue)` block, setting a value either to `-1` (not found) or to `i` (found). Subsequent calls skipped the scan because `HasValue` was true.

3. **New code regression is real**: ✓ Confirmed. On the same record, if `GetStream` is called twice for a blob column with no usable rowid:
   - **First call**: Cache miss → scan runs → nothing added to `RowIds` → returns `MemoryStream`
   - **Second call**: Cache miss again (key never added) → scan runs again → full O(FieldCount) re-execution plus potentially a `pragma_table_info` query

4. **Severity assessment**: Medium is appropriate. The regression occurs only when (a) a blob column lacks a usable rowid and (b) `GetStream` is called multiple times on the same column/row. While not common, it's plausible in streaming scenarios.

The architectural change from a per-record boolean sentinel to a per-table dictionary inadvertently removed the negative caching layer. The suggested fix—adding a sentinel entry `RowIds[key] = new RowIdInfo(-1, ...)` when the scan completes without finding a rowid—correctly mirrors the old behavior.

```json
{
  "finding": "Negative rowid lookup result not memoized",
  "verdict": "confirmed",
  "reason": "The not-found path (lines 330–391) never adds an entry to the RowIds dictionary when no rowid is found; entries are added only on lines 355 and 387 within break conditions. Unlike the old code's _rowidOrdinal = -1 sentinel, subsequent GetStream calls for the same blob column will trigger cache-miss on line 329 and re-execute the full O(FieldCount) scan. The regression is real for repeated access patterns on the same record.",
  "corrections": {}
}
```
