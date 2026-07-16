# subagent agent-a58d2feeca4192100

Verified against the actual repo diff. This matches the narrative provided.

## Summary

Fixes a performance regression where searching `stdin` with large `-A/--after-context` values was pathologically slow: on Linux, `read()` calls on stdin cap out around 64K regardless of buffer size, so `LineBuffer::fill` was issuing many small reads instead of filling its buffer in one pass. The fix loops `read()` calls until the free buffer is full (or the reader is exhausted), and separately narrows `core.rs`'s backward line scan to use `before_context` instead of `max_context()` (which folds in `after_context`), since that scan is only needed to preserve `-B/--before-context` lines. Two `glue.rs` test byte-count expectations are adjusted to match the new binary-detection boundary produced by the aggregated reads.

**Type:** bug-fix (performance)
**Effort:** 1/5 — two small, targeted logic changes (~15 net lines across `line_buffer.rs` and `core.rs`) plus two test-expectation updates and a changelog entry; no new abstractions or API surface.

## Walkthrough

| File | Change | Summary |
|------|--------|---------|
| crates/searcher/src/line_buffer.rs | Modified | `fill()`'s single `read()` call replaced with an inner loop that keeps reading into the free buffer until it's full or the source returns 0, amortizing syscalls capped at 64K (e.g. on stdin) |
| crates/searcher/src/searcher/core.rs | Modified | Backward line-scan bound changed from `self.config.max_context()` to `self.config.before_context`, skipping the costly scan entirely when `-B` isn't set, with a comment explaining why |
| crates/searcher/src/searcher/glue.rs | Modified | Updates two hardcoded expected byte counts (262146 → 262142) in binary-detection tests to reflect the new aggregated-read chunk boundary |
| CHANGELOG.md | Modified | Adds a "PERF #3184" entry noting the `-A/--after-context` performance improvement |

## Related Issues & PRs

<!-- issue-linker output will be merged here — the orchestrator replaces this placeholder -->
