# subagent agent-a87ddd8e263aa1ac1

```json
{
  "finding": "LineBuffer::fill()'s new inner read loop withholds output until buffer full/EOF, breaking --line-buffered / streaming stdin",
  "verdict": "confirmed",
  "reason": "Read crates/searcher/src/line_buffer.rs directly: the inner loop at line 419 (`while !self.free_buffer().is_empty() { let readlen = rdr.read(self.free_buffer())?; if readlen == 0 { break; } self.end += readlen; }`) only exits when free_buffer() (buf[self.end..], the full remaining capacity per line 367-369) is exhausted or read() returns 0. The line-terminator scan (`newbytes.rfind_byte`, line 470) happens only after that loop exits, so a read() that returns a single complete line does not cause fill() to return -- it loops back and issues another blocking read(). Traced the call chain: ReadByLine::run (glue.rs:38-46) calls self.fill() once per iteration, which calls rdr.fill() -> LineBuffer::fill() exactly once, then processes core.match_by_line(self.rdr.buffer()) only after fill() returns. So a match found by an early short read is genuinely withheld until the loop condition is satisfied. Verified --line-buffered exists and is documented in crates/core/flags/defs.rs:3556-3568 explicitly for `tail -f something.log | rg foo --line-buffered | rg bar` streaming pipelines, which this defeats. Also confirmed via git history: HEAD (d4b77a8) only touches core.rs (the kept 'roll' change), and the inner-loop code was introduced whole-cloth in commit 8c6595c (line_buffer.rs added as new file with this exact loop) -- matching the claimed real ripgrep regression/revert (issue #3194, commit d47663b) described in the corroborating context, which I independently re-derived from the code rather than merely trusting.",
  "corrections": {
    "line": 419,
    "pre_existing": false
  }
}
```
