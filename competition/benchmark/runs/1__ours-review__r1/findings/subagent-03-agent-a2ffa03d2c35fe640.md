# subagent agent-a2ffa03d2c35fe640

## Findings

```json
[
  {
    "file": "src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs",
    "line": 397,
    "severity": "Critical",
    "category": "prior-feedback",
    "issue": "[PRIOR_REGRESSION] Re-added `Debug.Assert(rowIdForOrdinal != null)` (per ErikEJ's 'Re-add Assert' request, ack'd by francopettinari as a 'puppy error') was restored verbatim into a control flow it no longer matches, reintroducing a spurious-failure defect the surrounding code was written to avoid — thread: ErikEJ on SqliteDataRecord.cs ('Re-add Assert').",
    "fix": "Either guard the assert to only fire when a rowid column genuinely should exist (mirroring the pre-refactor sentinel semantics), or remove/relax it since `if (rowIdForOrdinal == null)` immediately below is the intended, legitimate no-rowid path (e.g. WITHOUT ROWID tables, views) and must not be treated as an invariant violation.",
    "confidence": 100,
    "pre_existing": false
  }
]
```

### Detail

Before this PR, `_rowidOrdinal` was a nullable `int` seeded with sentinel `-1` before the search loop, so `Debug.Assert(_rowidOrdinal.HasValue)` was trivially true regardless of whether a rowid column was actually found — it could never fire on a legitimate "no rowid" case (e.g., a view or a `WITHOUT ROWID` table joined into the query), because the subsequent branch checked `_rowidOrdinal.Value < 0` to route to the cached-blob fallback.

The refactor to `Dictionary<string, RowIdInfo> RowIds` dropped that sentinel: `rowIdForOrdinal` now starts `null` via `TryGetValue`'s `out` default and is only set if a rowid or single-PK column is actually found in the loop. When ErikEJ's requested assert was re-added as `Debug.Assert(rowIdForOrdinal != null)`, it now sits directly on a path where `rowIdForOrdinal` can legitimately still be `null` after the loop — exactly the case the next line (`if (rowIdForOrdinal == null) { return new MemoryStream(...); }`) is written to accommodate. In Debug builds, hitting a table/view with a blob column but no rowid (the same "no rowid" case the code explicitly handles two lines later) will now trip the assert, whereas it never could before this PR.

This is a case where the literal review request ("re-add the assert") was honored, but the interaction with the untracked structural change (single nullable field → per-table dictionary) silently undid the safety property the original assert-with-sentinel design relied on — the "done and then undone" pattern this review type is meant to catch.

## Considered But Not Flagged

- **ajcvickers on `RowIdInfo` value-tuple suggestion** (SqliteDataRecord.cs:20) — francopettinari replied "It was only for readability," a reasoned decline; `RowIdInfo` remains a class in the final diff, consistent with the stated intent. Not flagged (anchor 0).
- **ErikEJ "Re-add Assert" — literal presence** — the assert line itself is present in the final diff (`git show HEAD` confirms `Debug.Assert(rowIdForOrdinal!=null);`), so the surface-level request was fulfilled; only the semantic correctness of that re-addition is flagged above, not its absence.
