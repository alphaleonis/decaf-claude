# subagent agent-a77d31d1d2d97e916

## Review scope

Diff reviewed: `git diff de2567a4...d4b77a8d` (PR #3185), covering:
- `crates/searcher/src/line_buffer.rs` — `LineBuffer::fill` inner read-loop rewrite
- `crates/searcher/src/searcher/core.rs` — `Core::roll` retention computed from `before_context` instead of `max_context()`
- `crates/searcher/src/searcher/glue.rs` — two binary-detection test expectations updated
- `CHANGELOG.md` — entry addition

I also checked `origin/master` for any later commits touching these files, since this is a real upstream repo and the actual outcome of this exact code is knowable rather than merely inferable.

## Critical (90-100)

**`LineBuffer::fill`'s new inner read-loop blocks until the buffer is full, defeating streaming/line-buffered stdin reads — confidence 97**

`crates/searcher/src/line_buffer.rs:417-425`:
```rust
let oldend = self.end;
while !self.free_buffer().is_empty() {
    let readlen = rdr.read(self.free_buffer())?;
    if readlen == 0 {
        break;
    }
    self.end += readlen;
}
```
Per `io::Read`'s contract, a short read (fewer bytes than requested) does **not** mean EOF — only a `0`-byte read does. This loop treats any non-EOF read as "keep going," so on a live pipe/terminal that has already delivered a complete line (e.g. `tail -f | rg foo`, or literal interactive typing into stdin), the second call to `rdr.read()` inside this loop will **block waiting for more bytes** rather than letting `fill()` return with the line(s) already available. The buffer only gets handed off for searching once it is completely full (default 64 KiB, larger under `-A`) or the stream hits true EOF. This is a direct behavioral regression for any consumer expecting incremental/real-time output from stdin, and specifically breaks `--line-buffered`.

This is not speculative: the actual ripgrep repository contains a follow-up commit on `origin/master`, `d47663b1` ("searcher: fix regression with `--line-buffered` flag", fixing issue #3194), which **reverts exactly this hunk** while keeping the `core.rs` before_context change. The commit message states directly:

> "So the 'fix' was to put `read` in a loop and keep calling it until the caller provided buffer was full or until the stream was exhausted. ... But of course, in retrospect, this change is clearly contrary to how `--line-buffered` works. We specifically do _not_ want to wait around until the buffer is full."

So as merged at `d4b77a8d`, this PR introduces a confirmed regression that had to be reverted in a subsequent commit. The `newbytes.is_empty()` EOF-return branch (`line_buffer.rs:432-437`) is otherwise fine and is correctly *kept* by the later fix — only the inner `while` read loop is the problem.

Fix (already applied upstream in `d47663b1`): revert to a single `rdr.read(self.free_buffer())` call per outer-loop iteration; rely on the outer `loop { ensure_capacity(); ... }` to re-attempt reads when no line terminator was found yet. Rejected alternative: keep the amortizing inner loop but cap it by a byte budget or add a "stop after first successful read of any size" flag — unnecessary complexity when the simple revert already satisfies both #3184 and #3194 per upstream's own conclusion.

## No issues found in the following (checked, not just assumed)

- `crates/searcher/src/searcher/core.rs:186-206` — switching `Core::roll`'s backward-retention computation from `max_context()` to `before_context` is correct. After-context emission is driven forward through `after_context_left` (a persistent `Core` field, unaffected by buffer rolls), not by backward buffer retention, so lines needed for after-context are never at risk of being dropped by this change. `lines::preceding(buf, term, 0)` (the `before_context == 0` path) degenerates to "retain only the trailing partial line," matching intended minimal-retention behavior.
- `oldend`/`self.end` bookkeeping in `fill()` — no off-by-one; `oldend` is captured once per outer-loop iteration before any inner reads, and `newbytes` correctly spans everything read in that iteration regardless of how many inner reads occurred.
- `glue.rs` byte-count expectation changes (262146→262142, both occurrences) — consistent, mechanical fallout of the buffering change and already match the merged upstream test values; not a bug.

## Output

One critical finding above (confidence 97). No other findings meet the ≥80 confidence bar.
