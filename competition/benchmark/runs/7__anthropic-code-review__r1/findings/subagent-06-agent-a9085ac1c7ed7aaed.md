# subagent agent-a9085ac1c7ed7aaed

## Review of PR #13777 against AGENTS.md

Scope: `storage/remote/read_handler.go` only, as merged in d1abc3f (commit 5309112, "Chunked remote read: close the querier earlier").

### Finding 1 — Undocumented lifetime contract change; the returned `ChunkSeriesSet` is used after its producing `Querier` is closed

**File/lines:** `storage/remote/read_handler.go:239-265` (new function `getChunkSeriesSet`), consumed at `storage/remote/read_handler.go:205` onward in `remoteReadStreamedXORChunks`.

**Description:** The diff moves `querier.Close()` into a `defer` inside the new `getChunkSeriesSet` helper (lines 247-248), which returns `querier.Select(ctx, true, hints, filteredMatchers...)` (line 265) — a lazily-evaluated `ChunkSeriesSet`. Because the `defer` fires when `getChunkSeriesSet` returns, the querier (and its underlying chunk reader) is closed *before* the caller ever iterates the `ChunkSeriesSet` in `StreamChunkedReadResponses`. This bakes in an unstated assumption that iterating a `ChunkSeriesSet`/its chunk iterators remains valid after the producing `storage.Querier`/`storage.ChunkQuerier` is closed. That assumption is false for the local TSDB implementation, whose `Close()` unmaps the chunk file's mmap region (`storage/interface.go`'s `LabelQuerier.Close()` doc only says "Close releases the resources of the Querier" — it says nothing about outstanding `SeriesSet`/`ChunkSeriesSet` values). This is not speculative: it is a confirmed, real defect. The exact change was reverted in prometheus/prometheus#14515 ("I believe the iterators for the querier can access memory-mapped files, which are closed when the querier is closed") after prometheus/prometheus#14422 reported production SIGSEGV crashes with a stack trace running through `read_handler.go` → `StreamChunkedReadResponses` → `compactChunkIterator.Next` → `chunks.Reader.ChunkOrIterable` (reading a closed/unmapped chunk file), triggered right after block compaction closed the relevant chunk reader.

**Guidance violated:** "Interface contracts: when ownership or lifetime semantics (e.g. buffer reuse / lifetime) are important, document it at the interface definition, not just the implementation." (Also relevant, same defect: "Code style: follow Go Code Review Comments; state assumptions" — the new function's doc comment states *what* it does ("ensure timely release of the querier resources") but never states or justifies the load-bearing assumption that early release is safe while the returned set is still being consumed.)

### Finding 2 — No test accompanies the behavior/lifecycle change

**File/lines:** `storage/remote/read_handler.go` (whole diff — no test file touched).

**Description:** The PR is framed by its own author as a fix for observed production misbehavior ("I have seen prometheus instances misbehaving because of broken chunked remote read requests... to avoid OOM's when this happens, I propose to close the queries used by the streamed remote read requests earlier") and it changes the querier close/consume ordering in `remoteReadStreamedXORChunks`/`getChunkSeriesSet`. No test was added or modified (`read_handler_test.go`'s existing `TestStreamReadEndpoint` is untouched and exercises a test store that doesn't reproduce the resource-invalidation-on-close scenario, which is exactly why it didn't catch the regression later found in #14422).

**Guidance violated:** "Bug fixes require a test that reproduces the bug." (and, to the extent this is read as new behavior in the querier lifecycle rather than strictly a bug fix: "New behaviour or exported API changes require unit or e2e tests.")

### Not flagged (checked, no violation)
- Doc comment on `getChunkSeriesSet` exists and is grammatically fine; its lowercase start ("getChunkSeriesSet executes...") mirrors the pre-existing, untouched `filterExtLabelsFromMatchers` comment in the same file (standard Go doc convention of leading with the identifier), so it's not a new deviation introduced by this diff.
- Scope discipline: the diff is tightly confined to the querier-creation/closing refactor; no unrelated changes.
