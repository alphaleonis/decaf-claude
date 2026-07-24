Review complete. Report written to **`.decaf/tag1-review-32770.md`**

> Note: that path already contained a report from an earlier run of this same command (I did not create it). Per your `--output-file` instruction I overwrote it with this run's report; the old version was untracked in git, so it is not recoverable from history.

---

## Review Findings — dotnet/efcore PR #32770

**Overall Risk: High** · 0 Critical / **3 High** / **3 Medium** / **3 Low** · 10 agents, 0 failures, ~35 raw findings deduplicated to 9

*(Reviewed as local diff `9e69b85^..HEAD` — the PR is MERGED upstream and local HEAD is exactly its squash commit, so no worktree checkout was needed. `--local`: nothing was posted anywhere.)*

### High (3)
1. **Debug.Assert fires on legitimate paths** — `Debug.Assert(rowIdForOrdinal!=null)` (`SqliteDataRecord.cs:393`) was trivially true before (`-1` sentinel pre-seeded); now it genuinely fails whenever no rowid is found — a designed, handled outcome (`MemoryStream` fallback 3 lines later). The pre-existing tests `GetStream_works` and `GetStream_works_when_composite_pk` hit exactly this path, so Debug-build test runs fail/crash. [Inference — `dotnet` unavailable, statically traced; flagged by 7 agents, conf 92]
2. **Negative caching lost** — `RowIds.Add` only runs on success, so tables with no usable rowid re-run the full column scan + a `pragma_table_info` SQL round trip on **every** `GetStream` call — per chunk in the standard chunked-`GetBytes` pattern (`SqliteDataRecord.cs:329-394`; 7 agents, conf 88).
3. **Self-joins still broken** — SQLite reports origin table, not alias, so `T a1 JOIN T a2` shares one cache key and the second alias silently gets the first alias's rowid → wrong row's blob. Pre-existing, but it's the exact bug class this PR claims to fix, and untested (`SqliteDataRecord.cs:325-328`; 3 agents, conf 81).

### Medium (3)
4. **Cache-key collision** — `$"{db}_{table}"` with `_` as delimiter: `(main, A_B)` ≡ `(main_A, B)` → silent wrong-row blob data. Use a `(string?, string?)` tuple key (`:328`; 6 agents).
5. **`RowIdInfo` type design** — `TableName` is write-only dead state, mutable public setters, type reduces to an `int`; can't represent "scanned, not found" (`:20-30`; 5 agents).
6. **Test gaps/hygiene** — no `Assert.IsType<SqliteBlob>` (a regression to the non-streaming fallback passes green), `Console.WriteLine` debris, unasserted ID reads, missing self-join/ATTACH/multi-row/fallback-join scenarios (test:149-184; 4 agents).

### Low (3)
7. `RowIds` breaks `private _camelCase` + lazy-allocation conventions of every sibling cache (`:39`).
8. Comments narrate history ("this was failing. now should be fixed") or misdescribe code; new cache design entirely undocumented.
9. Style nits: stray blank line (`:17`), `!=` spacing (`:393`), `rowidkey` casing (`:328`).

**One change resolves findings 2, 4, 5, 7** (and makes 1 moot): a lazily-allocated `private Dictionary<(string? db, string? table), int?>? _rowIdOrdinals` with `null` = "scanned, no rowid", plus deleting the assert.

### Run notes
- **Skipped:** silent-failure-hunter (no error-handling patterns in diff), issue-linker (`--local`), CVE check (no dependency manifests), static analyzers (none installed).
- **Diff tier:** small (72 lines, 2 files) · confidence filter ≥75 · 9 suppression rules loaded, 0 matched · claude-mem unavailable (no history/store).
- **Token utilization:** agents total ~521k tokens ≈ **~$9.35** est. (Opus: architecture 37k / security 39k / adversarial 53k; Sonnet: 7 agents ~392k). Opus tool budgets respected (2, 2, 6 of 25); code-reviewer used 27 tools ⚠. Orchestrator cost: see `/cost` — tip: running the orchestrator on Sonnet is ~5× cheaper.

⚠ **Address the High findings before relying on this change in Debug builds** — full details, remediations, and the consolidated fix are in `.decaf/tag1-review-32770.md`.
