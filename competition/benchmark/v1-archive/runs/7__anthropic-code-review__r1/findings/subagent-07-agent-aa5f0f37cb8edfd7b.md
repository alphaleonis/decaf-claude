# subagent agent-aa5f0f37cb8edfd7b

## PR Summary: #13777 - Chunked remote read: close the querier earlier

**PR Title & Author**  
"Chunked remote read: close the querier earlier" by Julien Pivotto (@roidelapluie)

**What the change does**  
This PR refactors the `remoteReadStreamedXORChunks()` function in `storage/remote/read_handler.go` by extracting the querier initialization and chunk selection logic into a new helper function `getChunkSeriesSet()`. The key insight is that by wrapping the querier operations in their own function scope with a deferred close, the querier is released earlier in the request lifecycle. This prevents resource exhaustion and out-of-memory (OOM) failures when Prometheus instances encounter broken or incomplete chunked remote read requests.

**Why**  
The author observed Prometheus instances misbehaving and running out of memory when processing broken chunked remote read requests. Closing the querier resources earlier reduces the memory footprint and prevents cascading failures.

**Files changed**  
- `storage/remote/read_handler.go` — 32 additions, 21 deletions

**Notable technical context**  
The refactoring preserves all query logic (hints construction, chunk selection) but moves it to `getChunkSeriesSet()`, which now owns the querier lifecycle entirely. The deferred close in the new function ensures cleanup happens as soon as that function returns, rather than deferring it to the end of the request stream. The change is a clean extraction with no behavioral changes to the streaming protocol itself—it's purely a resource-management improvement.
