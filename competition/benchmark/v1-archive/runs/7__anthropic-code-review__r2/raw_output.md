Scoring returned **100/100** — this passes the ≥80 filter (step 6). All agents deduplicate to a single finding. I have the exact commit SHA (`53091126c28f518c154c365a47d617c9ee7634de`) and line numbers from the diff. Per your instructions, I am **not** posting to GitHub — here is the complete review as it would be posted, output to the terminal only.

---

## Code review output (NOT posted to GitHub)

**PR:** [prometheus/prometheus#13777](https://github.com/prometheus/prometheus/pull/13777) — "Chunked remote read: close the querier earlier" (merged; author roidelapluie)
**Change commit:** `53091126c28f518c154c365a47d617c9ee7634de`
**File reviewed:** `storage/remote/read_handler.go` (+32/−21)
**CLAUDE.md:** none exist in this repo → no CLAUDE.md findings.

### Code review

Found 1 issue:

1. **Use-after-close: the querier is closed before its lazily-iterated `ChunkSeriesSet` is streamed, causing a SIGSEGV on memory-mapped TSDB data.** The new `getChunkSeriesSet` helper runs `defer querier.Close()` and returns the result of `querier.Select(...)` — so the querier is closed the instant the helper returns, *before* `remoteReadStreamedXORChunks` hands the series set to `StreamChunkedReadResponses`. For TSDB-backed queriers, `Select()` is lazy: the series set reads index/chunk bytes from memory-mapped block files only when iterated (`Next()`/`At()`/chunk `Iterator()`), and `querier.Close()` unmaps exactly those files. Iterating after close reads unmapped memory. (bug — closing the querier at `defer querier.Close()` while the returned `chunks` is consumed later at the `StreamChunkedReadResponses(... chunks ...)` call site)

   The helper that closes the querier too early (`defer querier.Close()` at L247–251, then `return querier.Select(...)` at L265):
   https://github.com/prometheus/prometheus/blob/53091126c28f518c154c365a47d617c9ee7634de/storage/remote/read_handler.go#L239-L266

   The call site that iterates the already-orphaned `chunks` set after the querier is closed:
   https://github.com/prometheus/prometheus/blob/53091126c28f518c154c365a47d617c9ee7634de/storage/remote/read_handler.go#L204-L215

   Historical confirmation (not speculation): this exact change was later reverted in [PR #14515](https://github.com/prometheus/prometheus/pull/14515) / commit `6e89250a5d` — *"Believed to trigger segmentation faults due to memory-mapped block data still being accessed by iterators after the querier is closed."* It was reported as a production crash in [issue #14422](https://github.com/prometheus/prometheus/issues/14422) (SIGSEGV in `StreamChunkedReadResponses` → `chunks.(*Reader).ChunkOrIterable`), and a regression test (`TestBlockClosingBlockedDuringRemoteRead`) was added upstream to prevent reintroduction. The correct pattern keeps `defer querier.Close()` in the same scope as the full `StreamChunkedReadResponses` call, so the querier stays open for the entire stream.

🤖 Generated with [Claude Code](https://claude.ai/code)

---

### Review process summary

- **Steps 1–3 (Haiku):** eligibility (PR is MERGED — gate would normally stop here, but you overrode it for a terminal-only review), CLAUDE.md discovery (none found), PR summary.
- **Step 4 (5× Sonnet):** CLAUDE.md-compliance (empty, no CLAUDE.md), shallow bug scan, git-history, prior-PR-comments, and code-comment agents. Four of five independently found the **same** use-after-close bug; the fifth (CLAUDE.md) correctly reported nothing.
- **Step 5 (Haiku scoring):** the single deduplicated finding scored **100/100**, verified against the upstream revert and regression test.
- **Step 6 filter (≥80):** 1 finding survives.
- **Step 8:** not executed — nothing posted to GitHub, per your instruction.

Nothing was written to GitHub.
