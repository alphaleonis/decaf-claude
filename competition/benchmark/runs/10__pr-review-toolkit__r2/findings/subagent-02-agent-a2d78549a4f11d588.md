# subagent agent-a2d78549a4f11d588

## Code Review: ripgrep PR #3185 — fix slow `stdin` search with large `-A/--after-context`

### What I reviewed
- `crates/searcher/src/line_buffer.rs` — the new inner read loop in `fill()` (lines 416-477)
- `crates/searcher/src/searcher/core.rs` — `roll()` changing `max_context()` → `before_context` (lines 185-213)
- `crates/searcher/src/searcher/glue.rs` — updated byte-count expectations in `binary3`/`binary4` (lines 740, 774)
- `CHANGELOG.md` entry
- Supporting context: `lines::preceding`, `Config::max_context`, the `roll`/`consume` flow in `glue.rs`, `after_context_by_line`, and the `DecodeReaderBytes` wrapper in `searcher/mod.rs`

### Verdict: No high-confidence issues. The changes are correct.

I verified correctness both by reasoning and empirically (all 77 `grep-searcher` tests pass; I additionally built `rg` and ran differential tests).

### Verification details

**1. `line_buffer.rs` inner read loop (lines 419-437) — correct.**
- `oldend` is captured before the inner loop and all offset math (binary Quit `self.end = oldend + i` line 444, Convert `oldend + i` line 462, `last_lineterm = oldend + i + 1` line 471) is consistent with `newbytes = &buf[oldend..self.end]` covering the whole batch read this iteration. Doing `find_byte`/`rfind_byte`/`replace_bytes` over the full batch yields the same first-occurrence/last-terminator result as the old per-read checks.
- EOF: a first read of 0 leaves `newbytes` empty → the `newbytes.is_empty()` branch (line 432) sets `last_lineterm = self.end` and returns, matching old semantics.
- Long lines: if the inner loop fills the buffer (`free_buffer` empty) with no terminator, the outer `loop` re-enters `ensure_capacity()` and grows — the `BufferAllocation::Error` limit tests (`buffer_limited_capacity1/2/3`, `big_error_*`) still pass.
- Removing `.as_bytes_mut()` is a no-op (`free_buffer()` already returns `&mut [u8]`); read-error propagation via `?` is unchanged in effect (search aborts on error).

**2. `core.rs` roll `before_context` (line 202) — correct.** After-context does not require keeping lines across the roll: `match_by_line_fast` flushes after-context greedily up to `buf.len()` (line 419) before the next `roll`, and the remainder is carried in `after_context_left` state. Whenever after-context is still pending at roll time, `last_line_visited == buf.len()`, so `consumed = max(context_start, last_line_visited)` is unaffected by whether `context_start` used `before_context` or `max_context`. The reduced count only matters when there is no pending after-context, where `before_context` lines is exactly what a future match needs. The `max_context()==0` guard (line 186) means the no-context binary tests are untouched. Confirmed empirically: `rg` output is byte-identical to GNU grep for `-A999`, `-B999`, `-C999`, `-A99999`, `-B99999`, and identical between file and stdin input for `-A/-B/-C` up to `999999`.

**3. `glue.rs` test changes (262146 → 262142) — correct and consistent.** I confirmed causation empirically in an isolated worktree: reverting `core.rs` alone leaves the tests passing (guard short-circuits), while reverting the `line_buffer.rs` inner loop makes `binary3`/`binary4` produce the old `262146`. The mechanism: `search_reader` wraps input in `DecodeReaderBytesBuilder` with an 8 KB decode buffer (`searcher/mod.rs:333`), so the wrapped reader returns 8 KB chunks even for in-memory input. The old `fill` returned after the first chunk that contained a line terminator (under-filling the 64 KB line buffer); the new loop amortizes reads to fill the buffer. This shifts the buffer boundary at which binary data is detected, changing only the reported "bytes searched" by one 4-byte non-matching line. Both versions emit the same match (`0:a`) and the same binary offset (`262153`) — no match is lost. This is the exact amortization behavior the PR intends, and it is also the root of the performance fix.

### Minor observation (below reporting threshold, not a defect)
- `CHANGELOG.md:11-12` [Unverified/low-confidence]: the entry links `[PERF #3184](.../pull/3184)`, but #3184 is the issue this fixes and #3185 is the PR (other entries in the section link the PR number, e.g. PERF #2865 → pull/2865). GitHub redirects `/pull/3184` to the issue, so the link resolves; this is a trivial cosmetic inconsistency at most, and matches how ripgrep sometimes references the tracking number. Not worth changing on its own.

No CLAUDE.md convention violations apply to these files (Rust crate, American spelling preserved, comments explain the why without change-history narration).
