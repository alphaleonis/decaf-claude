# subagent agent-aaaed5b271da5e62a

**75**

The issue identifies a real, latent correctness bug. Line 328 constructs a cache key via naive string concatenation (`$"{blobDatabaseName}_{blobTableName}"`) without escaping or delimiters, which creates collision vulnerability: databases named "main_users" with table "x" and database "main" with table "users_x" both yield key "main_users_x". When a collision occurs, the cached RowIdInfo ordinal for the wrong table is reused at line 402 (`var rowid = GetInt64(rowIdForOrdinal.Ordinal)`), causing GetStream to read the wrong result column or open SqliteBlob with a bogus rowid—classic data corruption. The scenario requires ATTACH'd databases with underscores and specific table-naming patterns, which is plausible in production systems; SQLite imposes no restrictions on underscore characters in identifiers. This is exactly the class of multiple-blob-column bug this PR was meant to fix, and senior engineers would flag it as a correctness defect.
