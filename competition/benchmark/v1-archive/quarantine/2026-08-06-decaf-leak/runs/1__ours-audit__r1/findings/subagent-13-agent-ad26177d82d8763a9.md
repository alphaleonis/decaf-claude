# subagent agent-ad26177d82d8763a9

<review_analysis>
Prior code: `_rowidOrdinal=-1` set eagerly → assert always true, miss cached as -1. New code: miss never added to dict → `rowIdForOrdinal` stays null; assert now false-fires; miss re-scanned every call. TableName written, never read (only `.Ordinal` at L402). Key uses `_` join, no escaping.
</review_analysis>

## VERDICT: NEEDS_CHANGES

## Project Standards Applied
No project documentation dictating knowledge/decision-logging standards found for this file. Applying RULE 0 (knowledge preservation) and RULE 2 (structural/comprehension) only. `.NET` private-field naming convention (`_camelCase`) is a consistency-reviewer concern, noted below but out of my scope.

## Findings

### [MARKER_INVALID SHOULD]: Assert encodes a false invariant that the code immediately contradicts
- **RULE**: 0
- **Location**: `src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs:393`
- **Issue**: `Debug.Assert(rowIdForOrdinal != null)` asserts the scan always finds a rowid ordinal. It does not: when no `rowid`/single-integer-PK column is present (view, aggregate/expression column, `WITHOUT ROWID` table, joined non-table source), the loop completes leaving `rowIdForOrdinal == null`. The very next statement (L396) handles `== null` as a legitimate path. In the prior code the analogous `Debug.Assert(_rowidOrdinal.HasValue)` was trivially true because `-1` was assigned eagerly; the port silently converted a true invariant into a false one.
- **Failure Mode / Rationale**: In any Debug build, calling `GetStream`/`GetBytes`/`GetTextReader` on a blob column whose source has no usable rowid now trips the assertion — a regression exercised by ordinary queries. Worse for knowledge: a future reader sees an assert claiming "never null" three lines above a branch that treats null as normal, and cannot tell which one states the real contract. The assert must be deleted (null is valid) or replaced with the actual invariant.
- **Suggested Fix**: Remove the assert. If an invariant is still wanted, assert the loop's own postcondition instead (e.g. that a found ordinal is in range), not non-nullness.
- **Confidence**: 100
- **Pre-existing**: no
- **Actionability Check**: Fix specifies exact change: YES. Fix requires no additional decisions: YES.

### [LLM_COMPREHENSION_RISK SHOULD]: "No rowid" result silently not cached — reader cannot tell if intentional
- **RULE**: 0
- **Location**: `src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs:329-398`
- **Issue**: The old `int?` cached the miss as `-1`, so the expensive discovery ran once per (reader, table). The new dictionary only ever `.Add`s on a *hit* (L355, L387); the no-rowid path adds nothing, so `RowIds.TryGetValue` misses on every subsequent `GetStream` for that table and re-runs the full field scan plus, for INTEGER-PK candidates, the `SELECT COUNT(*) FROM pragma_table_info(...)` query. Nothing in code says whether dropping the negative-cache was deliberate. A field named `RowIds` reads as a memoization cache; a maintainer will reasonably assume misses are cached too.
- **Failure Mode / Rationale**: A future maintainer "optimizing" or "fixing" this either (a) leaves a per-row re-scan + per-row pragma query in place on a hot read path, or (b) adds miss-caching and unknowingly reverts what may have been an intentional choice — because the intent was never recorded in the one place they are editing. The knowledge ("misses are/aren't cached, and why") lives only in the author's head. This is both a comprehension gap and a real per-call performance regression versus the prior code.
- **Suggested Fix**: Decide and encode the intent: either cache the negative result (e.g. store a sentinel `RowIdInfo`/nullable entry so `TryGetValue` short-circuits misses) matching the prior `-1` behavior, or add a one-line comment stating misses are intentionally recomputed and why. State the choice in code, not only the PR.
- **Confidence**: 100
- **Pre-existing**: no
- **Actionability Check**: Fix specifies exact change: YES. Fix requires no additional decisions: NO — author must choose cache-vs-comment; both options given.

### [ASSUMPTION_UNVALIDATED SHOULD]: Rowid cache key `"{db}_{table}"` has an undocumented, unescaped collision assumption
- **RULE**: 0
- **Location**: `src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs:328`
- **Issue**: The cache key is `$"{blobDatabaseName}_{blobTableName}"` with a bare `_` separator and no escaping. `(db="a", table="b_c")` and `(db="a_b", table="c")` produce the identical key `"a_b_c"`. Nothing documents the assumption that this can't collide. This class of key reuse across two distinct tables is exactly the defect #32747/PR #32770 sets out to fix.
- **Failure Mode / Rationale**: A JOIN whose two blob-bearing sources happen to alias to a colliding db/table key string would resolve the second table's blob against the first table's cached rowid ordinal — silently reading the wrong blob, the precise failure this change targets, now in a narrower guise. The residual risk is invisible because the reason a simple `_` join was considered safe is unwritten.
- **Suggested Fix**: Use a delimiter-safe composite key (e.g. a `(string,string)` tuple / `ValueTuple` dictionary key, or escape the separator) and/or add a comment stating why db/table names cannot collide under this join.
- **Confidence**: 75
- **Pre-existing**: no
- **Actionability Check**: Fix specifies exact change: YES. Fix requires no additional decisions: YES.

### [DEAD_CODE COULD]: `RowIdInfo.TableName` is stored but never read — false context
- **RULE**: 2
- **Location**: `src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs:23-28, 354, 386`
- **Issue**: `RowIdInfo.TableName` is assigned in both constructor sites but never read anywhere (only `.Ordinal` is consumed, L402). `sqlite3_column_table_name` at L325 (`blobTableName`) is what's actually used downstream.
- **Failure Mode / Rationale**: The stored table name implies the cache validates or keys on it (e.g. guards against the very collision above). It does neither. A future maintainer debugging a wrong-table blob will trust `TableName` as a load-bearing safeguard, waste effort, or "fix" a collision by comparing it — reasoning from a field that is inert. Either wire it into key/lookup validation or drop it.
- **Suggested Fix**: Remove the `TableName` property and constructor parameter (making `RowIdInfo` an ordinal holder), or actually use it to validate the cached entry against `blobTableName` before reuse.
- **Confidence**: 100
- **Pre-existing**: no
- **Actionability Check**: Fix specifies exact change: YES. Fix requires no additional decisions: NO — remove-vs-use given.

## Reasoning
Applied RULE 0 + RULE 2. Found a false-firing assert (invalid invariant), a silent loss of negative-caching with no recorded intent, an unescaped composite key re-risking the fixed bug, and a write-only field creating false context. Verdict NEEDS_CHANGES: no unrecoverable knowledge loss, but multiple confirmed comprehension traps and one debug-build defect.

## Considered But Not Flagged
- `RowIds` field is non-private and PascalCase without `_` prefix, unlike sibling fields (`_blobCache`, `_typeCache`). Mechanical convention drift → consistency-reviewer scope, no comprehension risk.
- Core cross-table rowid fix itself (dictionary keyed per table) is sound and directly addresses #32747; not flagged.
- Absence of a code comment recording *why* the change was made (the JOIN bug) — belongs in the commit/PR/linked issue #32747, fails the not-recorded-elsewhere gate.
- `SqliteBlob(readOnly: true)` construction unchanged from prior code; no new knowledge at risk.

### Probe Requests
- None. Findings verified read-only against working tree and `HEAD~1`; no dotnet build/run required.
