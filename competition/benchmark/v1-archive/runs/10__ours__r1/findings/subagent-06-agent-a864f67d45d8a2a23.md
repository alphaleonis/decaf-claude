# subagent agent-a864f67d45d8a2a23

## Rust Reviewer Findings — ripgrep PR #3185 (`-A/--after-context` streaming perf fix)

```json
[
  {
    "file": "crates/searcher/src/line_buffer.rs",
    "line": 419,
    "severity": "High",
    "category": "other",
    "issue": "[RUST_IO_CONTRACT] The new inner `while !self.free_buffer().is_empty() { rdr.read(...) }` loop insists on filling the entire free buffer (default 64 KB, `DEFAULT_BUFFER_CAPACITY`) or hitting real EOF before `fill()` ever checks the newly-read bytes for a line terminator. The pre-existing outer loop already re-read until a newline appeared in the bytes from a single `read()` call, so for line-buffered producers (a pipe writer that flushes per line, `tail -f file | rg -A5 pat`, or a human typing into a TTY piped to rg) each `read()` naturally returned right after a `\\n` and `fill()` returned immediately. With the new inner loop, that same single short read no longer causes an early return: `fill()` keeps calling `read()` until 64 KB has accumulated or the stream is closed, so no match is reported until then. No TTY/interactive special-casing exists anywhere in the crate (`grep -rn is_terminal|isatty` in crates/core and crates/searcher returns nothing), so this applies uniformly to any slow/interactive stdin producer.",
    "fix": "Break the inner loop as soon as a line terminator has appeared in the bytes read so far (or otherwise cap the amount of forced batching), rather than always draining `free_buffer()` to empty; e.g. check `newbytes.rfind_byte(lineterm)` after each inner `read()` and break early once found, keeping the full-buffer read only as a throughput optimization for the no-newline-yet case (which is what actually caused the `-A` slowdown described in #3184).",
    "confidence": 75,
    "pre_existing": false
  }
]
```

## Considered But Not Flagged

- **`self.end += readlen` overflow** — `self.end` is bounded by `self.buf.len()` (usize, effectively unbounded on 64-bit); `ensure_capacity()` guarantees `free_buffer()` is non-empty before each inner `read()`, and a well-behaved `Read` impl never returns `readlen > buf.len()` for the slice it was given. No overflow/panic on any conforming reader. (25 — would require a contract-violating `Read` impl, and that risk is identical to the pre-existing code, not introduced here.)
- **`&mut self.buf[oldend..self.end]` panic from `oldend > self.end`** — `oldend` is captured before the inner loop and `self.end` only ever increases inside it (`self.end += readlen`), so `oldend <= self.end` always holds; empty range is handled explicitly via the new `if newbytes.is_empty()` branch. No panic path. (0)
- **Binary `Quit` truncation (`self.end = oldend + i`) then re-slicing** — the function `return`s immediately after truncation (`return Ok(self.pos < self.end)`), so there's no subsequent re-indexing against the stale, larger range in the same call. Next `fill()` call starts a fresh `roll()`/`ensure_capacity()` cycle against the truncated `self.end`. Safe. (0)
- **Repeated `self.free_buffer()` calls / aliasing** — each call produces a fresh `&mut self.buf[self.end..]` borrow; prior borrows are not retained across iterations (readlen is copied out before the next call), so no aliasing or stale-slice reuse. Standard reborrow pattern. (0)
- **`buf.len() - consumed` in `core.rs::roll()`** — switching the third arg of `lines::preceding` from `max_context()` to `before_context` only changes which (smaller-or-equal) offset `preceding()` returns; `preceding()` is bounded to `0..=bytes.len()` regardless of `count`, and `last_line_visited` is a pre-existing invariant already bounded by buffer length. The `max(...)` and subsequent subtraction are unchanged code paths, not newly introduced by this diff — no new underflow risk. (25, pre-existing pattern, not modified in a risk-increasing way)
- **`.as_bytes_mut()` removal on `rdr.read(self.free_buffer())`** — confirmed via `grep -rn as_bytes_mut crates/searcher/src/` (no hits) that `free_buffer()` already returns `&mut [u8]` directly (`fn free_buffer(&mut self) -> &mut [u8]`, line_buffer.rs:367-369); passing it straight to `read()` is the correct, non-redundant call. No type or behavior difference. (0)
- **`Err(Interrupted)` propagation via `?`** — unchanged from the prior single-`read()` version; `rdr.read(...)?` still forwards any `io::Error` including `Interrupted` to the caller exactly as before. Not a regression introduced by this diff. (0)
- **`unsafe`/lock/async findings** — none of the changed code contains `unsafe` blocks, lock acquisitions, or async/await constructs; those categories are not applicable to this diff.

### Probe Requests
- Manually verify the streaming-latency regression: `mkfifo /tmp/f; (rg -N 'x' /tmp/f &) ; printf 'xline\n' > /tmp/f` (or `python3 -c "import time,sys; [ (sys.stdout.write('xline\n'), sys.stdout.flush(), time.sleep(2)) for _ in range(3)]" | rg -A2 x`) and observe whether output appears immediately per line or is delayed until ~64 KB has been written / the pipe closes — this would empirically confirm or refute the finding above without modifying tracked files.
