# subagent agent-a5ed265a3c14b23d0

Based on my verification of the upstream repository's history and the test reproducer, I can now score this issue with high confidence.

**Key findings:**

1. **Revert commit 6e89250a5d** exists and explicitly states: "Believed to trigger segmentation faults due to memory-mapped block data still being accessed by iterators after the querier is closed."

2. **Test reproducer (commit ab2475c426)** was added to catch this regression: `TestBlockClosingBlockedDuringRemoteRead()` verifies that queriers remain open while remote reads are streaming.

3. **The bug is real:** The code at lines 242-266 (the `getChunkSeriesSet()` function) closes the querier via `defer` immediately after `querier.Select()` returns. However, `ChunkSeriesSet` is a lazy iterator that isn't consumed until `StreamChunkedReadResponses()` iterates over it (lines 210-218) — *after* the querier is already closed. For TSDB-backed queriers using memory-mapped files, accessing unmapped memory causes SIGSEGV.

4. **The upstream fix** (revert) simply moves the `defer querier.Close()` back into the scope of `remoteReadStreamedXORChunks()` so the querier stays open during the entire streaming operation.

**100**

This is a confirmed use-after-close bug causing production segmentation faults, as documented by the revert commit message and regression test in the upstream repository.
