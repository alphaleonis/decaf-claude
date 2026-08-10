# subagent agent-a01805fea6a8ccfb2

## Edge Case Analysis

### Pass 1: Path Walk

Traced the modified `LineBuffer::fill()` inner-read loop (`crates/searcher/src/line_buffer.rs:406-477`) and the `Core::roll()` context-window computation (`crates/searcher/src/searcher/core.rs:185-213`). Branching constructs examined: the inner `while !free_buffer().is_empty()` read loop and its `readlen == 0` break, the `newbytes.is_empty()` EOF-detection guard, the `BinaryDetection` match arms (`None`/`Quit`/`Convert`), the trailing `rfind_byte` line-terminator check plus implicit outer-loop retry, and the `max_context() == 0` / `else` branch in `roll()` (including `lines::preceding`'s `pos == 0` and `count == 0` guards). 8 candidates were raised in Pass 1 (loop non-termination under adversarial readers, contract-violating `read()` return values, spurious `Ok(0)` mid-stream, `oldend`/`self.end` arithmetic bounds, state desync across outer-loop passes, and the `before_context`-only lookback dropping the `after_context` term). All 8 were discarded in Pass 2.

### Pass 2: Completeness Re-validation

- **Inner loop termination**: `free_buffer().len() == buf.len() - self.end` shrinks monotonically each time `self.end += readlen` (readlen bounded by the slice length per the `io::Read` contract), so the loop always terminates — either the buffer fills or `read` returns 0. No adversarial `Ok(n>0)`-forever case can spin it, since free space is finite and `ensure_capacity()` is only re-invoked once per outer pass.
- **`readlen > free_buffer().len()`** (a `Read`-contract violation) would let `self.end` exceed `buf.len()`, but this trust was identical in the pre-diff single-`read()` code (`self.end += readlen` was unguarded there too) — not a regression, and disallowed by the `io::Read` invariant.
- **Spurious `Ok(0)`** (reader signals 0 without true EOF, then resumes): verified this is *better* handled than before — a mid-batch `readlen==0` no longer aborts the pass (old code checked `readlen==0` on every single `read()` call and returned terminal EOF the instant any call returned 0); the new code only treats it as EOF when `newbytes.is_empty()` (i.e., zero bytes accumulated across the *entire* pass), and otherwise the outer `loop` naturally retries `read()` on the next iteration.
- **`newbytes.is_empty()` EOF detection**: `oldend` is fixed at pass-start and `self.end` only advances on `readlen>0`, so `oldend == self.end` if and only if the very first read of the pass returned 0 — this precisely and only fires on a true no-bytes-this-pass condition. Confirmed via `cargo test -p grep-searcher --lib` (77/77 passing, including `line_buffer::tests::*` and `searcher::glue::tests::*`).
- **`oldend + i` bounds**: `i` is always `< newbytes.len()`, so `oldend + i < oldend + newbytes.len() == self.end <= buf.len()`; no OOB, unchanged from pre-diff logic.
- **Outer-loop state sync**: traced two full outer passes (partial fill → grow → EOF); `oldend`/`self.end`/`last_lineterm` update identically to the pre-diff single-read version, just batched over more `read()` calls per pass. No desync found.
- **`core.rs`: `before_context` replacing `max_context()` when `before_context==0, after_context>0`**: confirmed via `last_line_visited` update sites (`core.rs:550,580,611,641`) that after-context lines are always sunk via `sink_after_context`, which updates `last_line_visited` to their end — including the explicit `after_context_by_line(buf, buf.len())` flush at the end of both `match_by_line_fast` (line 419) and the slow-path stepper. Since `consumed = max(context_start, last_line_visited)`, `last_line_visited` alone already captures how far after-context processing reached; `context_start` (via `preceding(buf, term, 0)`) only needs to protect the buffer's trailing (possibly unterminated) partial line, which it does correctly regardless of context configuration. Confirmed against `glue.rs` context/binary tests, all passing with the updated expected byte counts.

No confirmed findings survive Pass 2.

### Positive Observations

- The rewrite correctly narrows the EOF check from "any single `read()` returned 0" to "zero bytes accumulated this pass," which is a strict improvement for readers that transiently return partial/zero reads without being at true EOF.
- The `Core::roll()` change is backed by an explicit, correct invariant (`last_line_visited` already reflects after-context sinking up to `buf.len()`), and the accompanying test-expectation updates in `glue.rs` (`byte count:262146` → `262142`) are consistent with retaining less unnecessary trailing data.

```json-findings
[]
```
