# subagent agent-a880df2aa1bdb50cc

## Verdict: CONFIRMED (recommend High severity)

### Mechanism verification

I traced the code directly rather than relying on memory of `read()` semantics in the abstract:

**`crates/searcher/src/line_buffer.rs:406-477`** — the inner loop at 419-425:
```rust
while !self.free_buffer().is_empty() {
    let readlen = rdr.read(self.free_buffer())?;
    if readlen == 0 { break; }
    self.end += readlen;
}
```
has no check for a line terminator inside it. Binary detection and the `rfind_byte(lineterm)` search (which is the only path that can `return Ok(true)` early) happen only *after* this inner loop exits — i.e., only once `free_buffer()` is exhausted (buffer physically full, default 64KB, larger with big `-A/-B/-C`) or `read()` returns `0` (true EOF).

On a blocking pipe (the standard case for `tail -f log | rg ...`), `read()` returns `>=1` as soon as *any* data is available and blocks (does not return `0`) when the pipe is momentarily empty but not closed. So: producer writes one matching line, first `read()` returns that data, `self.end` advances, `free_buffer()` is still non-empty (buffer is 64KB, line is small) → loop continues → second `read()` call blocks indefinitely (until more data arrives or the pipe closes). The already-buffered complete line is never handed back to the caller during this block. This is exactly the claimed mechanism, and it's the direct, intended effect of the change — the commit's own message says "We fix this by putting `read` into an inner loop that ensures our buffer gets filled up," confirming the prior behavior read once per outer iteration.

I confirmed this isn't merely a theoretical/internal-buffer concern by checking how `fill()` is consumed: **`crates/searcher/src/searcher/glue.rs:38-51,58-88`** (`ReadByLine::run`/`fill`) shows the entire line-matching/emit cycle (`self.core.match_by_line(...)`) is gated behind a single `self.rdr.fill()` call returning — so if `fill()` blocks inside the inner loop, no output is produced at all until it returns. I also confirmed stdin goes through this exact non-mmap `ReadByLine` path (`crates/core/search.rs:258-259`, `search_reader`), not a bulk-mmap path, so this is live for the `tail -f | rg` scenario, not just files.

### Adversarial check: does this matter, or is it out of scope for ripgrep?

I looked for evidence ripgrep considers this a non-goal. I found the opposite: **`crates/core/flags/defs.rs:3535-3580`**, the `--line-buffered` flag's own documentation explicitly names this exact use case:
```
tail -f something.log | rg foo --line-buffered | rg bar
```
"whenever a matching line is found, it will be flushed to stdout immediately." `--line-buffered` only controls *output* flush timing (`crates/cli/src/wtr.rs`), not input-read batching — it cannot compensate for `fill()` blocking before a match is even found. So this change directly undermines a use case ripgrep documents and explicitly supports via a dedicated flag. That's strong evidence this is in-scope and a genuine regression, not an accepted trade-off.

I also checked the unit tests at the bottom of `line_buffer.rs` (`buffer_basics1..4`, etc.) — all use `&[u8]` byte-slice readers, whose `Read` impl never partially-reads-then-blocks (it either returns everything available or `0`). No test exercises a slow/blocking producer, so nothing in the test suite guards against or contradicts this behavior.

### Conclusion

The finding survives refutation attempt on all fronts: mechanism is real and independently re-derivable from `Read`/pipe semantics, citation is accurate (406-477, inner loop 419-425), attribution is correct per the commit's own description of the prior single-read behavior, and impact is corroborated by the searcher's gating structure and by ripgrep's own documented `--line-buffered` streaming use case, which this change silently breaks for slow producers with no compensating check or documentation update. Given it breaks a *documented* feature (not just a hypothetical edge case) and no test coverage exists for this path, I'd calibrate severity toward **High** rather than Medium — the delay isn't bounded at "a few seconds" for a genuinely low-throughput producer, it's unbounded until ~64KB (or more, with large `-A/-B/-C`) accumulates or the pipe closes.

```json
{
  "finding": "fill() inner read-loop blocks until buffer full/EOF instead of returning after first usable read",
  "verdict": "confirmed",
  "reason": "Traced the inner loop at line_buffer.rs:419-425: it has no line-terminator check and only exits when free_buffer() is exhausted or read() returns 0, so on a blocking pipe (tail -f) a partial read followed by producer idle causes the next read() call to block, withholding an already-buffered complete line. Confirmed this gates all output via glue.rs ReadByLine::fill/run, confirmed stdin uses this exact non-mmap path via core/search.rs, and confirmed ripgrep's own --line-buffered docs (defs.rs:3556-3569) name `tail -f log | rg foo --line-buffered` as a supported use case that this change undermines regardless of the flag (which only affects output flush, not input read batching). No test covers a blocking/partial-read producer.",
  "corrections": {
    "pre_existing": false
  }
}
```
