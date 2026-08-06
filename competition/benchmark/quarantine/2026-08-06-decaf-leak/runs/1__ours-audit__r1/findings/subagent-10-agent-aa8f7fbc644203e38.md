# subagent agent-aa8f7fbc644203e38

I have a complete picture. Let me produce the review.

## System Model

`SqliteDataRecord` is an internal, per-reader (per-`sqlite3_stmt`), single-threaded value reader. `GetStream(ordinal)` returns a stream over a blob column. To build a streaming `SqliteBlob` it must locate the rowid ordinal *for the blob's own table*; if it can't, it falls back to materializing the blob into a `MemoryStream`. The change replaces a single per-record cache (`int? _rowidOrdinal`, using `-1` as a "no rowid" sentinel) with a `Dictionary<string, RowIdInfo>` keyed per `(database, table)`. Relevant model elements: the **cache identity key**, the **RowIdInfo data model**, the **"no rowid found" contract** (assert + fallback branch), and the **negative-result caching semantics**.

Findings below.

```json
[
  {
    "file": "src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs",
    "line": 393,
    "severity": "High",
    "category": "design",
    "issue": "[API_CONTRACT] The invariant asserted here contradicts the code two lines below it. `Debug.Assert(rowIdForOrdinal != null)` now encodes 'a rowid ordinal is always found', but line 396 explicitly handles `rowIdForOrdinal == null` as a legitimate fallback (blob column from a table/view with no single-column integer PK, an expression, or a subquery). In the old design `_rowidOrdinal` was initialized to -1 before the scan, so `Debug.Assert(_rowidOrdinal.HasValue)` always held; the meaning of the assertion silently changed from 'the scan ran' to 'a rowid exists'. In Debug builds (which is what the EF Core test suite and consumers' debug sessions run) this assertion now fires on a path the code otherwise handles gracefully, aborting instead of falling back to the in-memory blob.",
    "fix": "Remove the assertion, or move it after the null-fallback branch, or restore an explicit 'searched but none found' sentinel so the assertion means 'the search completed' rather than 'a rowid exists'. The null case is a designed, reachable outcome and must not trip a debug assertion.",
    "confidence": 100,
    "pre_existing": false
  },
  {
    "file": "src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs",
    "line": 396,
    "severity": "Medium",
    "category": "design",
    "issue": "[EVOLUTION_READINESS] Negative-result caching semantics regressed relative to the design being replaced. The old code memoized the 'no rowid' result (`_rowidOrdinal = -1`) so the expensive scan ran once per record. The new code only calls `RowIds.Add(...)` on the two success paths (lines 355, 387); when no rowid is found nothing is stored, so `RowIds.TryGetValue` misses on every subsequent `GetStream` for that (db, table). For a reader iterating many rows over a blob column whose table has no usable rowid, each access re-runs the full FieldCount scan plus, potentially, a `SELECT COUNT(*) FROM pragma_table_info(...)` query. The per-table dictionary models presence but not absence, an asymmetry the prior single-slot cache did not have.",
    "fix": "Cache the negative outcome too — e.g. store a sentinel RowIdInfo (or make the dictionary value nullable and add the key with a null/negative marker) so 'this table has no rowid ordinal' is memoized like every positive result.",
    "confidence": 75,
    "pre_existing": false
  },
  {
    "file": "src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs",
    "line": 328,
    "severity": "Medium",
    "category": "design",
    "issue": "[DATA_MODEL] The cache identity key `$\"{blobDatabaseName}_{blobTableName}\"` is an ambiguous encoding of a (database, table) pair. Because `_` is both the separator and a legal character in SQLite schema (attach) and table names, distinct pairs collide: db `a` + table `b_c` and db `a_b` + table `c` both produce key `a_b_c`. Two colliding tables that each expose a blob column in one JOIN would share a single cached rowid ordinal — reintroducing exactly the wrong-rowid / `no such rowid` failure class this PR set out to fix, only under specific-but-legal naming.",
    "fix": "Key the dictionary on a composite identity that cannot be flattened ambiguously — a `(string db, string table)` ValueTuple, a small equatable struct, or a nested dictionary — instead of a delimiter-joined string.",
    "confidence": 50,
    "pre_existing": false
  },
  {
    "file": "src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs",
    "line": 23,
    "severity": "Low",
    "category": "design",
    "issue": "[DATA_MODEL] `RowIdInfo.TableName` is dead model state: it is written at construction (lines 28, 354, 386) but never read anywhere (only `.Ordinal` is consumed, line 402). The stated intent was to carry table information alongside the ordinal, but nothing uses it — the type carries a field that neither participates in the cache key nor validates the ordinal against the requesting table. This misleads future maintainers into believing per-entry table validation exists when it does not, and adds a mutable public setter to boot.",
    "fix": "Either remove `TableName` and reduce the cache value to the ordinal (`Dictionary<string, int>`), or actually use it — e.g. assert/validate the cached entry's table matches the requested `blobTableName` to defend against the key-collision risk above.",
    "confidence": 100,
    "pre_existing": false
  }
]
```

## Considered But Not Flagged

- **Concurrency of the new `Dictionary`**: `SqliteDataRecord` is documented internal, per-reader, and not thread-safe; no new shared-state or cross-thread access is introduced. Replacing a nullable int with a dictionary does not change the concurrency model. Sound — not flagged.

- **Cache not cleared on `Read()` advancing rows**: the cached value is a *column ordinal* (schema/statement metadata), which is stable across rows of the same statement — same lifetime assumption as the prior `_rowidOrdinal`. Correct by design.

- **`RowIds` field naming/visibility drift** (`readonly Dictionary<...> RowIds` — no explicit `private`, PascalCase, no `_` prefix, unlike every sibling field `_blobCache`/`_typeCache`/…): real convention drift, but this is consistency-reviewer scope (unwritten naming conventions), not a system-design defect. Noted, not flagged as a design finding.

- **Mutable public getters/setters on `RowIdInfo`**: minor encapsulation weakness on an internal nested type with a single writer; folded into the DATA_MODEL finding on `TableName` rather than raised separately.

### Probe Requests
None required — all findings are verifiable from the source and git history already read. (No dotnet SDK available and none needed.)
