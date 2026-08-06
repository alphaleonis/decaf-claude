# subagent agent-a420f6b9694acd0c9

## PHASE 1: CONTEXT DISCOVERY

Project documentation present. Reading full SqliteDataRecord.cs to understand the GetStream implementation and dictionary key strategy.

**Key facts:**
- Original bug: Single `_rowidOrdinal` was cached globally, causing wrong rowid when SELECT joined multiple tables with BLOB columns
- Fix: Replace with `Dictionary<string, RowIdInfo>` keyed by database+table combination
- Dictionary key: `$"{blobDatabaseName}_{blobTableName}"`

---

## PHASE 2: CODE ANALYSIS

### Issue Found: String Concatenation Key Collision Vulnerability

**Lines 328, 329, 355, 387**

The dictionary key is constructed by naive string concatenation: `$"{blobDatabaseName}_{blobTableName}"`. This creates a collision vulnerability when database or table names contain underscores.

**Concrete collision example:**
- BLOB column from database "foo_bar", table "baz" → key becomes "foo_bar_baz"
- BLOB column from database "foo", table "bar_baz" → key becomes "foo_bar_baz"

In a single query result set with both columns, calling `GetStream()` on the second column would retrieve the *cached* rowid from the first column via the colliding key, causing it to access BLOB data from the wrong table.

**Proof:**
```csharp
// Line 328: key construction
string rowidkey = $"{blobDatabaseName}_{blobTableName}";

// Line 329: lookup
if (!RowIds.TryGetValue(rowidkey, out rowIdForOrdinal))
{
    // ... find and cache rowid ...
    RowIds.Add(rowidkey, rowIdForOrdinal);  // Line 355/387
}
```

With underscore-separated concatenation, two distinct (database, table) pairs can produce the same key string.

**Why introduced by this change:** The original code used a single cached ordinal with no key. This change introduces a keyed cache, and the key design is vulnerable.

**Impact:** Silent BLOB data corruption—returning bytes from the wrong table without error.

---

## Considered But Not Flagged

None — this is the only defect identified in the changed lines.

---

```json
[
  {
    "file": "src/Microsoft.Data.Sqlite.Core/SqliteDataRecord.cs",
    "line": 328,
    "severity": "High",
    "category": "logic",
    "issue": "[BUG_LOGIC] Dictionary key collision from naive string concatenation of database and table names containing underscores",
    "fix": "Use a separator guaranteed not to appear in identifiers (e.g., '\\0') or a composite key type: string rowidkey = $\"{blobDatabaseName}\\0{blobTableName}\"; or better: var rowidkey = (blobDatabaseName, blobTableName); (requires Dictionary<(string, string), RowIdInfo>)",
    "confidence": 65,
    "pre_existing": false
  }
]
```
