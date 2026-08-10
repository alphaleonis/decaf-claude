# subagent agent-a6fbaae9c0202cfa9

## Review: PR #3185 (BurntSushi/ripgrep) — shallow bug scan

I traced both changed functions line-by-line against the pre-PR code, cross-referenced the real upstream commits this PR corresponds to (`8c6595c2` for `line_buffer.rs`, `d4b77a8d` for `core.rs`, both already present in this repo's history), ran the existing `grep-searcher` test suite (77/77 pass, unchanged), and additionally wrote and ran a throwaway test with a custom `Read` impl that returns only 1 byte per `read()` call across ~35KB of input to specifically stress the new inner loop (verified: correct round-trip data, no infinite loop, and the reads amortize into <20 outer-loop passes instead of one per byte — confirming the intended fix actually works). That temporary test was reverted; `git status`/`git diff` confirm the working tree is clean.

**Conclusion: no solid, large/impactful bugs found in either changed file.**

Details of what I checked:

### `crates/searcher/src/line_buffer.rs` `fill()` (lines 406-477)
- **Termination**: bounded by either `rdr.read()` returning `0` (real EOF) or `ensure_capacity()` returning `Err` once the configured allocation limit is hit (`BufferAllocation::Error(limit)`); with `BufferAllocation::Eager` it can only grow unboundedly on a truly infinite line with no terminator — but that's pre-existing behavior of the old code too, not introduced here.
- **EOF handling**: the inner `while !self.free_buffer().is_empty()` loop never calls `read()` on an empty slice (avoids a spurious/ambiguous `Ok(0)`), and `if newbytes.is_empty()` correctly detects "made zero progress this whole outer pass," matching the old `readlen == 0` early-return exactly (`Ok(!self.buffer().is_empty())` preserved verbatim).
- **Buffer-full handling**: inner loop exits cleanly when `free_buffer()` becomes empty; outer loop's `ensure_capacity()` on the next pass correctly grows (or errors) before resuming reads. Traced against `buffer_limited_capacity1` (an existing test for the "not enough room to confirm EOF" edge case) — still passes.
- **Roll/consume**: `roll()` itself is untouched by this diff.
- **Binary detection (`Quit`/`Convert`)**: now runs over a potentially multi-read `newbytes` span instead of a single read's worth, but `find_byte`/`rfind_byte`/`replace_bytes` operate correctly over an arbitrarily-sized slice — truncation of `self.end` back to the first sentinel byte is unaffected by how many `read()` calls contributed to that span.
- Minor (non-bug) observation: with `BinaryDetection::Quit` combined with a large buffer (e.g. huge `-A`), the new code will fill the *entire* currently-allocated buffer before the first binary-byte check, whereas before this only happened for regular files (whose single `read()` already tends to fill the buffer) and not for stdin. This is the intended consequence of unifying stdin with file-read behavior, not a functional defect — same eventual detection offset, no data leaks past the sentinel byte, tests confirm the offset math (the `binary3`/`binary4` byte-count updates in `glue.rs`).

### `crates/searcher/src/searcher/core.rs` `roll()` (lines 185-213): `max_context()` → `before_context`
- `before_context_by_line` (line 245) already short-circuits (`return Ok(true)`) when `before_context == 0`, so it never needs the extra retained lines that `max_context()` (`= max(before_context, after_context)`) used to preserve.
- The context-separator logic (`sink_break_context`/`is_gap`, line 650) only depends on whether *any* data was retained across the roll (`last_line_visited` is unconditionally reset to `0`), not on the magnitude of `context_start`. Since `lines::preceding(buf, term, N)` for non-empty `buf` is always `< buf.len()` for any `N ≥ 0`, the "was anything retained" boolean is identical whether `context_start` comes from `before_context` or `max_context()`.
- For the exact scenario the surrounding comment calls out (after-context pending across a roll boundary), `last_line_visited` is already `== buf.len()` by construction (all in-buffer after-context lines get sunk before `roll()` runs), so it dominates `max(context_start, last_line_visited)` regardless of which count is used — i.e., that scenario was never actually sensitive to `context_start`'s value in the first place.
- Net effect: `consumed` (new) ≥ `consumed` (old), i.e. strictly retains less-or-equal data when `before_context == 0 < after_context`, which is exactly the perf win intended and does not remove data that any downstream consumer (before-context lookback, separator logic, after-context counter) still needs.

I did not find a concrete input/state that produces wrong output, a hang, or a panic from this diff.
