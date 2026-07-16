# subagent agent-af16184fec83ae180

I've fully examined the diff (all 4 changed files) and traced the flagged security surfaces. Let me record my verification reasoning before concluding.

**Memory-safety / overflow analysis of `line_buffer.rs::fill`:**
- `self.end += readlen`: `readlen` comes from `rdr.read(self.free_buffer())`, and `free_buffer()` = `&mut self.buf[self.end..]` (len = `buf.len() - end`). Per the `io::Read` contract `readlen <= free_buffer().len()`, so `end + readlen <= buf.len()` always. `buf.len()` is a real `Vec` length (≤ `isize::MAX`), so no `usize` overflow. The only way to exceed is a `Read` impl violating the std contract — the readers are ripgrep's own File/Stdin/decompression wrappers (not attacker-supplied trait objects), and this assumption was identical in the pre-diff code. Not a new issue.
- `&mut self.buf[oldend..self.end]`: `oldend` is captured before the inner loop; `self.end` only increases; both ≤ `buf.len()`. In-bounds. `oldend + i` (binary detection) has `i < newbytes.len()`, so `oldend + i < self.end`. No OOB, no overflow in the `as u64` casts.

**Allocation-limit / DoS analysis (the central question):**
- The inner `while !self.free_buffer().is_empty()` loop only *fills already-allocated free space* — it performs zero allocation. Growth happens exclusively in `ensure_capacity()` at the top of the outer `loop`, which under `BufferAllocation::Error(limit)` caps growth via `n = min(len*2, limit - used)` and returns `alloc_error` when the limit is hit. A line longer than the limit still errors out on the next outer iteration exactly as before. The batched read cannot bypass the limit.
- Inner loop termination: each non-break iteration increases `self.end` by `readlen ≥ 1`, shrinking `free_buffer()`; it exits on full buffer or `read()==0`. No infinite loop.

**Other surfaces:** No `unsafe` blocks added (confirmed — the diff removes a `.as_bytes_mut()` bstr adapter call; `free_buffer()` already returns `&mut [u8]`). `core.rs` change swaps `max_context()` → `before_context` for `preceding()`; `before_context ≤ max_context`, so `context_start` moves later/equal and preceding-retention shrinks to the actually-needed count — after-context bytes are forward in the stream, not in the discarded preceding region, so no byte-offset corruption. `glue.rs` edits are test-expectation updates for the new binary-detection batch size. No secrets, auth, injection, or crypto surface.

One non-security note (out of scope): the inner batched-read loop keeps reading until the buffer is full or EOF, so for a slow/interactive `stdin` it may block on a `read()` after a complete line rather than returning immediately — a latency/interactivity behavior change, not a resource-exhaustion or memory-safety vulnerability (buffer stays bounded by the allocation limit).

No security vulnerabilities at Medium or higher.

NONE
