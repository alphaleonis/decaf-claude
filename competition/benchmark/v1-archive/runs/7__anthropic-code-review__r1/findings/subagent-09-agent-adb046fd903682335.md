# subagent agent-adb046fd903682335

Based on my verification, I can now score this issue with full confidence.

**Score: 100**

**Justification:**

This is absolutely a real and critical bug. The evidence is definitive and multi-faceted:

1. **Code Pattern Confirmed**: The helper `getChunkSeriesSet` (lines 242-266) closes the querier via defer immediately upon returning, before the returned `ChunkSeriesSet` is consumed. The caller then passes this lazy-evaluated set to `StreamChunkedReadResponses`, which immediately begins iterating with `for ss.Next()` — accessing memory-mapped chunk data from the now-closed querier.

2. **Production Crash Confirmed**: Issue #14422 documents a SIGSEGV crash occurring in production immediately after PR #13777 was merged, with the stack trace showing the crash in `StreamChunkedReadResponses` → chunk reader trying to access unmapped memory at `/app/storage/remote/codec.go:246`.

3. **Explicit Revert with Rationale**: PR #14515 explicitly reverts PR #13777, with the description: "I believe the iterators for the querier can access memory-mapped files, which are closed when the querier is closed." This directly confirms the root cause matches the code issue.

4. **Backport to Stable**: PR #14523 backports the fix to the 2.53 release branch, indicating production severity.

5. **Regression Test Added**: PR #14599 adds a reproducer test for issue #14422 to prevent future regressions of this specific pattern.

The bug happens frequently in practice—any remote read request hitting memory-mapped TSDB blocks will crash. The issue is not a nitpick; it's a production-breaking use-after-free that manifests as SIGSEGV when iterating lazy chunk data from a closed querier.
