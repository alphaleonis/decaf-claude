# Comprehensive Review — prometheus/prometheus PR #13777

_"Chunked remote read: close the querier earlier" · base `main` (merge-base `312e3fd728`) · head `53091126c2` · 1 file, +32/−21 · TIER=small · mode: `--local` (nothing posted)_

> Note: PR #13777 is **MERGED** (it is the most recent merge in this checkout, `d1abc3f255`). This review is of the diff as submitted; the `getChunkSeriesSet` code below is still present unchanged at the checked-out `HEAD` (no later fix in this history).

## Summary

Extracts the `ChunkQuerier` creation and `Select()` call out of `remoteReadStreamedXORChunks` into a new helper, `getChunkSeriesSet`. Because the `defer querier.Close()` now lives inside the helper instead of the outer streaming function, the querier is closed as soon as the `ChunkSeriesSet` is obtained, rather than being held open for the lifetime of the entire chunked-response write. The author reports this is a response to Prometheus instances misbehaving (OOMs) on broken chunked remote-read requests, where the querier previously stayed open for the full duration of the write.

**Type:** Bugfix (mechanical extract-method refactor with an intended resource-lifetime change)
**Effort:** 2/5 — single-file, +32/−21, no new tests or API-surface change

## Walkthrough

| File | Change | Summary |
|------|--------|---------|
| storage/remote/read_handler.go | Modified | Extracted querier creation/`Select()` into new `getChunkSeriesSet` helper so the `ChunkQuerier` is `defer`-closed immediately on return from the helper instead of at the end of `remoteReadStreamedXORChunks`, releasing querier resources earlier during chunked remote-read streaming |

---

## Review Findings

**Overall Risk:** Critical — based on worst severity found

Nine review agents ran; eight of the nine findings-producing agents independently converged on the same core defect (the ninth, pr-summarizer, is descriptive only). Confidence on the core finding ranged 80–90 across independent code traces.

### Critical (1)

- **[code-reviewer · adversarial · edge-case · silent-failure · architecture · security · blind-hunter · comment-analyzer]** **Use-after-close / use-after-free race: the chunk querier is closed before its returned `ChunkSeriesSet` is streamed.** — `storage/remote/read_handler.go:247` (deferred `Close`) vs. lazy read in `storage/remote/codec.go:235`
  - `getChunkSeriesSet`'s `defer querier.Close()` (`read_handler.go:247`) fires when the helper **returns** — i.e. right after `return querier.Select(...)` at line 265, and **before** the caller (`read_handler.go:205`) hands the still-unconsumed set to `StreamChunkedReadResponses`. That function reads chunk bytes **lazily during iteration** (`ss.Next()` → `series.Iterator()` → `chk.Chunk.Bytes()`, `codec.go:235–266`) — after the querier is already closed.
  - Verified TSDB evidence chain (read directly in the worktree, not recalled):
    - `blockChunkQuerier.Select` returns `NewBlockChunkSeriesSet(...)` holding the block's `ChunkReader`; chunks are pulled on demand via `populateWithDelChunkSeriesIterator` (`tsdb/querier.go:174–196, 877–914`).
    - For persistent blocks the chunk bytes are a **zero-copy view into the mmap'd segment** (`tsdb/chunks/chunks.go` `Reader.ChunkOrIterable` → `sgmBytes.Range(...)`); only the head's *active* in-memory chunk is copied (`ChunkWithCopy`).
    - `blockChunkReader.Close()` only does `pendingReaders.Done()` (`tsdb/block.go:567–569`); `Block.Close()` does `pendingReaders.Wait()` **then** munmaps (`tsdb/block.go:377–390`). `pendingReaders` is the sole guard keeping the mmap alive.
    - Compaction/retention delete blocks via `Block.Close()` from `DB.reloadBlocks`/`deleteBlocks` (`tsdb/db.go:1472,1662`), running periodically alongside query serving.
    - On the head path, `headChunkReader.Close()` releases the isolation watermark (`isoState.Close()`, `tsdb/head_read.go:318–323`) that `WaitForPendingReadersInTimeRange` blocks on during truncation (`tsdb/head.go:1117,1141–1158`). The code even documents this contract: _"any truncation that comes after will wait on this querier if it overlaps ... won't run into a race later"_ (`tsdb/db.go:2022–2024`).
  - **Impact:** By dropping the reader reference before streaming, a concurrent compaction/retention/head-truncation can munmap the chunk segment while `StreamChunkedReadResponses` is still reading it. **[Inference — expected from mmap/munmap semantics, not empirically reproduced]** the likely manifestations are a fatal `SIGSEGV`/`SIGBUS` that Go's `recover()` cannot catch (crashing the whole Prometheus process — a remotely-triggerable DoS on a network-facing endpoint), or silently corrupted chunk bytes returned to the remote-read client. The underlying race (early `pendingReaders.Done()` racing `Block.Close()`) is **verified from the code**; only the crash-vs-corruption outcome is inference. A slow/broken client — the exact scenario the PR cites — maximizes the overlap window, so the change can trade a bounded, observable OOM for an unbounded, unobservable use-after-free.
  - **Internal-consistency signal:** the sibling non-streamed path `remoteReadSamples` (`read_handler.go:137–140`) fully consumes the series set *before* its deferred `Close()` — this streamed path now violates the pattern its own neighbor still follows.
  - **Remediation:** Do not release the querier before the returned `ChunkSeriesSet` is fully consumed. Either (a) revert to a handler-scoped `defer querier.Close()` that runs after `StreamChunkedReadResponses` completes (matching pre-PR behavior and the sibling `remoteReadSamples` path), or (b) if early release is a hard requirement, wrap the returned set so `Close()` fires only when iteration is exhausted, or materialize/deep-copy chunk bytes out of mmap before `Close()`. Address the original OOM concern via `ctx` timeout/cancellation of stuck streams rather than by dropping the mmap guard early.
  - **Rejected alternative (per governance):** copy every chunk's bytes out of mmap inside `getChunkSeriesSet` before `Close()` — rejected as the primary fix because it reintroduces the large allocation (OOM) the PR set out to avoid.
  - **Strongest counter-argument (per governance):** this is a race requiring streaming to overlap the moment compaction/retention deletes the specific block(s) being read; that window can be narrow, which is presumably why it passed upstream review. But compaction and head truncation are routine, First-Law priority applies to crash/data-corruption risk in a production monitoring system, and the PR's own motivation (slow/broken reads) directly widens the window — so it should not be dismissed as theoretical.
  - **Confidence:** 90 (highest across 8 agents; range 80–90).

### High (1)

- **[adversarial]** **No test exercises the changed lifetime invariant or the concurrent-truncation race.** — `storage/remote/read_handler.go:242`
  - The change alters a resource-lifetime invariant with zero added test coverage. No test (a) iterates the returned `ChunkSeriesSet` after the querier is closed, or (b) runs a chunked remote read concurrently with head truncation / block deletion. Existing remote-read tests use small in-memory fixtures with no concurrent compaction, so they never enter the unsafe window — passing tests are false assurance and CI is blind to this exact regression.
  - **Remediation:** Add a TSDB-level regression test: open a chunk querier over head + a persistent block, obtain the `ChunkSeriesSet`, close the querier, force truncation/deletion, then iterate and assert no read of freed memory (or assert the querier stays open for the streaming duration). A `read_handler`-layer mock won't reproduce mmap munmap — the test must run against real TSDB internals.
  - **Confidence:** 85.

### Medium (3)

- **[comment-analyzer · adversarial]** **The new `getChunkSeriesSet` docstring is misleading — it sells early close as pure benefit and omits the load-bearing lifetime invariant.** — `storage/remote/read_handler.go:239`
  - The comment says the helper exists _"to ensure timely release of the querier resources"_ but never states that the returned `ChunkSeriesSet` is consumed **after** the querier is closed, nor that this is only (arguably) safe under an mmap-lifetime assumption the diff does not establish. As written it invites a future maintainer to treat close-before-stream as a safe, intentional pattern to copy. (adversarial rated this High/82; consolidated to Medium as a standalone documentation defect coupled to the Critical.)
  - **Remediation:** If the code pattern is kept, document the exact invariant and the copy/pin that keeps bytes alive; if the code is unsafe and removed, remove the comment with it. Prefer stating the caller-facing contract over the refactor rationale (contract comments resist rot).
  - **Confidence:** 82.

- **[architecture]** **The change depends on an undocumented storage-interface contract: "a `ChunkSeriesSet` remains valid after its querier is `Close`d."** — `storage/interface.go:436`
  - `ChunkSeriesSet.At()` only promises iterability "after `Next` is called"; `LabelQuerier.Close` is documented as "releases the resources of the Querier," and the sibling `LabelValues` explicitly warns its results are "not safe to use beyond the lifetime of the querier." Post-`Close` iteration is therefore an undocumented implementation detail of today's block reader (`Close` ≠ immediate munmap). Any future `ChunkQuerier` that frees eagerly on `Close` breaks remote read with no compile-time signal.
  - **Remediation:** Do not rely on unspecified behavior. Either amend the `ChunkSeriesSet`/`ChunkQuerier` interface docs to define the set-vs-`Close` lifetime and make TSDB honor it, or keep the querier alive until consumption completes.
  - **Confidence:** 78.

- **[adversarial]** **Observability regression: an observable, semi-recoverable OOM is replaced by an unobservable crash-or-corruption.** — `storage/remote/read_handler.go:205`
  - The OOM this PR targets is observable (memory metrics, `OOMKilled`) and operator-mitigable. The new failure mode is a fatal `SIGBUS` (no metric, no log, not `recover()`-able, whole process down) or silent byte corruption (no signal at all), with no counter, defensive check, or degradation path. This is a facet of the Critical rather than an independent defect, but it materially raises the operational cost of the failure. `recover()` cannot handle SIGBUS from munmap, so there is no safe degradation once the mode is created — the only correct handling is to not create it.
  - **Confidence:** 78.

### Architectural Insights

The core problem is an **ownership inversion**, not style. Before this change the querier and the streamed `ChunkSeriesSet` had coincident lifetimes — the handler-scoped `defer querier.Close()` fired only after streaming drained the set, and that coincidence was load-bearing: it is the mechanism by which the block-reader `pendingReaders` refcount (and the head's isolation watermark) transitively keeps mmap'd chunk segments valid for the full duration bytes are read from them. `getChunkSeriesSet` severs that; the returned set now outlives its backing resources, with nothing in the type system or interface contract signaling it. The extraction boundary itself is clean — the defect is entirely in *when* `Close` runs relative to consumption. The stated goal (let a wedged stream stop pinning block resources) is real and correctly diagnosed; the chosen remedy trades a bounded, self-healing memory-pressure problem for an unbounded use-after-free.

### Security Analysis

The change touches the remote-read streamed-chunks handler — a network-facing surface. It introduces a memory-safety hazard (use-after-free against mmap'd chunk data) reachable by a normal remote-read request whose streaming overlaps routine compaction/retention; a slow-reading client (remotely influenceable) widens the race window even though the block-close trigger runs on Prometheus's own schedule. No auth, injection, secret, crypto, or deserialization concerns were introduced — the error path (`ErrChunkSeriesSet(err)` + caller `chunks.Err()`) is preserved and sound, and no prompt-injection attempt was present in the diff, commit, or PR body.

### Adversarial Analysis

Most critical gap: closing the querier before the set is streamed simultaneously releases **both** the block `pendingReaders` guard and the head's `WaitForPendingReadersInTimeRange` isolation watermark while chunk bytes are still read lazily from mmap. The counter-argument that some higher layer serializes reads against compaction/truncation was checked and fails: `Select()` is lazy and truncation/deletion run on independent background goroutines gated only by the reader registration this PR releases early.

### Positive Observations

- Error propagation is preserved and correct: `ChunkQuerier()` creation failure returns `storage.ErrChunkSeriesSet(err)`, the caller checks `chunks.Err()`, and `errors.As(err, &httpErr)` still resolves — behavior matches the old `return err` (verified by code-reviewer, silent-failure, edge-case, security, architecture, blind-hunter).
- No double-close or leaked-querier path: the creation-error branch returns before the `defer` is registered; the happy path registers exactly one `defer querier.Close()`.
- Hints construction was moved **verbatim**; `sortSeries=true`, warnings/annotations handling, and the outer error handling are unchanged — the diff stays reviewable.
- The problem the PR diagnoses (broken/slow chunked remote reads pinning querier resources → head growth → OOM) is real and correctly identified; only the remedy is unsafe.

### Recommended Actions

1. **Do not close the querier before the `ChunkSeriesSet` is fully consumed** (the Critical). Simplest safe fix: restore a handler-scoped `defer querier.Close()` after `StreamChunkedReadResponses`, matching pre-PR behavior and the sibling `remoteReadSamples` path.
2. If early release is genuinely required, wrap the returned set to close the querier on iteration-exhaustion, and/or define the `ChunkSeriesSet`-vs-`Close` lifetime contract at the `storage/interface.go` level and make TSDB honor it before relying on it in a consumer.
3. Address the original OOM concern via `ctx` timeout/cancellation of stuck streams, not by releasing the mmap guard early.
4. Add a TSDB-level regression test for iterate-after-close under concurrent truncation/deletion (the High).
5. Fix the `getChunkSeriesSet` docstring to state the real lifetime contract (or remove it with the code).

---

### Review metadata

- **Agents run (9):** pr-summarizer, code-reviewer, architecture-reviewer, security-reviewer, adversarial-general, blind-hunter, edge-case-hunter, silent-failure-hunter, comment-analyzer.
- **Agents skipped:** pr-test-analyzer (no test files in diff), type-design-analyzer (no type definitions in diff), issue-linker (`--local` + `--pr` mode).
- **Deterministic checks:** CVE/dependency check skipped (no manifest files changed); static analyzers (golangci-lint, semgrep, trufflehog, etc.) not installed — silently skipped.
- **Confidence filter:** ≥75 (default); 0 findings dropped below threshold.
- **Suppression / novelty:** no suppression rules matched; no prior-review history.
- **Mode:** `--local` — nothing was posted to GitHub.
