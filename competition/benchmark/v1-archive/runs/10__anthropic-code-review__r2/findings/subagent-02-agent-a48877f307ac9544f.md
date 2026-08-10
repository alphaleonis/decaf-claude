# subagent agent-a48877f307ac9544f

## Summary

**What the PR does:** This PR fixes a critical performance regression where searching `stdin` with large `-A/--after-context` values became exponentially slower than searching the same data from a regular file. The root cause was that `read()` calls on stdin appear to return no more than ~64KB even when larger buffers are available, causing poor amortization of buffer capacity growth when large after-context values force reallocation. The fix wraps the read call in an inner loop to fill the buffer properly, and optimizes the before-context path to skip expensive line-finding when not needed.

---

## Files Changed

| File | Changes |
|------|---------|
| `CHANGELOG.md` | +2, -0 |
| `crates/searcher/src/line_buffer.rs` | +13, -8 |
| `crates/searcher/src/searcher/core.rs` | +5, -1 |
| `crates/searcher/src/searcher/glue.rs` | +2, -2 |

---

## Key Code Changes

1. **`line_buffer.rs`** — Core fix: Wrapped `rdr.read()` in a while loop that continues reading from stdin until the free buffer is full or EOF is reached, ensuring proper amortization. Previously a single read call could return only 64KB even when more space was available.

2. **`searcher/core.rs`** — Optimization: When computing context_start (preceding lines), use `self.config.before_context` instead of `self.config.max_context()` so the expensive line-finding step is skipped entirely when `-B/--before-context` is not set (i.e., when only `-A` is used).

3. **`searcher/glue.rs`** — Test updates: Adjusted expected byte counts in two binary detection tests to reflect the new read behavior (262146 → 262142, 262146 → 262142).
