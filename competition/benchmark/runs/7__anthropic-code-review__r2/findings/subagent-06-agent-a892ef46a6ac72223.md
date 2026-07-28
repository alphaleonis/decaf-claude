# subagent agent-a892ef46a6ac72223

## PR #13777 Summary

**Title:** Chunked remote read: close the querier earlier  
**Author:** roidelapluie (Julien Pivotto)

### Problem & Approach
The PR addresses Prometheus instances misbehaving due to broken chunked remote read requests. The solution closes querier resources earlier to avoid out-of-memory (OOM) errors during streaming operations.

### Key Change
Refactors `remoteReadStreamedXORChunks()` by extracting querier management into a new helper function `getChunkSeriesSet()`. This ensures the querier resource is released immediately after the `Select()` call returns, rather than remaining open throughout the streaming response transmission.

**Before:** Querier created → deferred close at end of function → Select() called and result streamed  
**After:** Querier created → Select() called → querier closed → result passed to streaming handler

### Files Changed
| File | Change |
|------|--------|
| `storage/remote/read_handler.go` | Extracted querier initialization and hints setup into new `getChunkSeriesSet()` helper function; simplified `remoteReadStreamedXORChunks()` to call the helper |

### Overall Size
- **Additions:** 32 lines
- **Deletions:** 21 lines  
- **Changed files:** 1

### Notable Behavioral Change
Querier resources are released earlier in the request lifecycle — before streaming begins rather than after it completes. This prevents resource accumulation during broken or slow remote read requests, mitigating OOM risk.
