# subagent agent-af6804e2793cb527f

I have verified all three points of the finding against the actual code.

**1. Mechanism is real.** In the current `fill()` (line 416 `loop`), the new inner loop at line 419 `while !self.free_buffer().is_empty()` keeps calling `rdr.read(self.free_buffer())` until the free buffer is empty (buffer full) or a read returns 0 (EOF). Only *after* that inner loop exits does the code check for a line terminator (`newbytes.rfind_byte(self.config.lineterm)` at line 470) and return `Ok(true)`. The old code, per the diff hunk, did a single `rdr.read(...)` per outer-loop iteration and returned as soon as that one read produced a terminator. So the new code will call `read()` again after a complete line has already been read — and on a slow/still-open pipe that next `read()` blocks. The blocking behavior change is genuine.

**2. Buffer capacity confirmed.** `DEFAULT_BUFFER_CAPACITY = 64 * (1 << 10)` (64 KB, line 6), and the buffer is allocated at that fixed size up front (`buf: vec![0; self.config.capacity]`, line 124). It does not start small and grow for the common case, so "delayed until ~64 KB accumulates or the stream closes" is accurately characterized.

**3. Reachable via the public streaming API.** `Searcher::search_reader` (mod.rs:727) takes the non-multiline branch (line 760-763) for ordinary line-by-line search, constructing `LineBufferReader::new(decoder, line_buffer)` and driving it via `ReadByLine`. `LineBufferReader::fill()` (line 256-257) calls `self.line_buffer.fill(&mut self.rdr)`, reaching the changed code. The only short-circuit (binary `Quit` at line 410) requires binary detection enabled *and* binary already seen — it does not apply to a normal interactive text pipe.

Attribution: introduced by commit `8c6595c` (one of the two commits under review), not pre-existing. Cited line 419 is exactly the inner `while !self.free_buffer().is_empty()` loop. Whether this latency-for-throughput amortization is an acceptable tradeoff (the author made it deliberately) is out of scope; the behavior change itself is real.

```json
{
  "finding": "#unknown",
  "verdict": "confirmed",
  "reason": "The new inner loop at line_buffer.rs:419 keeps calling rdr.read() until the free buffer (64KB fixed default) fills or EOF, and only checks for a line terminator afterward; the old code returned Ok(true) after a single read that found a terminator. This blocking/latency change is reachable via the public search_reader streaming path (non-multiline ReadByLine -> LineBufferReader::fill) with no short-circuit for a normal text pipe.",
  "corrections": {
    "line": 419,
    "pre_existing": false
  }
}
```
