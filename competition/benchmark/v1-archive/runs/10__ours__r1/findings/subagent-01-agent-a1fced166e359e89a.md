# subagent agent-a1fced166e359e89a

```json
[
  {
    "file": "crates/searcher/src/line_buffer.rs",
    "line": 419,
    "severity": "High",
    "category": "performance",
    "issue": "[BUG_LOGIC] LineBuffer::fill()'s inner read loop no longer returns as soon as a complete line is available. It now keeps calling `rdr.read()` (line 420) until the free buffer is completely full or the reader signals true EOF (`readlen == 0`), and only *after* that inner `while` loop exits does it scan the accumulated bytes for a line terminator (line 470) or invoke binary detection. The original code checked for a line terminator after every single physical `read()` call and returned immediately once found.",
    "fix": "Move the line-terminator (and binary-detection) check inside the inner loop, keyed off each newly-read chunk, and `break`/return as soon as a terminator is found -- only keep looping to accumulate more data when the most recent read did not yet produce a usable line. That preserves the amortization win for large -A while still returning promptly when a line is already available from a single small read.",
    "confidence": 75,
    "pre_existing": false
  }
]
```

## Considered But Not Flagged

- **`crates/searcher/src/searcher/core.rs` `roll()`: `before_context` vs `max_context()` for `context_start` (lines 198-206).** Traced this rigorously through both `match_by_line_fast` and `match_by_line_slow` (and their `after_context_by_line`/`sink_after_context` helpers). Whenever `after_context_left > 0` at the moment `roll()` runs, `last_line_visited` is provably already equal to `buf.len()` (every remaining line in `buf` must have been routed through the after-context sink to keep `after_context_left > 0` non-decremented-to-zero, or the buffer would have ended exactly at the point it hit zero). Since `consumed = max(context_start, last_line_visited)`, and `context_start` (computed from either `before_context` or `max_context()`) can never exceed `buf.len()`, the choice between the two is moot in every case where after-context is actually pending — `last_line_visited` always dominates. The `before_context`-only computation only changes the result when `after_context_left == 0`, where no after-context lines are owed at all and only before-context lookback matters. So this change is a genuine no-op for correctness and a real win for the reported perf bug (avoids an O(after_context) `lines::preceding` backward scan on every roll when `before_context == 0`). No pending after-context lines are dropped at a buffer boundary.
- **`glue.rs` golden-test byte-count changes (262146 → 262142) in `binary3`/`binary4`.** Consistent with binary detection now running over a larger accumulated read chunk before searching (as documented in the adjacent test comments), and already validated by the passing `cargo test -p grep-searcher` gate (77/77). Not independently re-derived byte-for-byte, but no reason to doubt it given the gate result and the mechanism matches the stated cause.
- **`line_buffer.rs` EOF / "read returns 0 then more" progress guarantees.** Traced the inner-loop/outer-loop interaction for: immediate EOF on first read, EOF encountered mid-fill after some data was already read this pass, and the "one extra doomed read to confirm EOF" pattern. In all cases `self.end` only monotonically increases within `buf.len()` bounds and the loop provably terminates; behavior matches the original at the point of final `Ok`/`Err` return. No infinite-loop or missed-EOF risk found.
- **Binary `Quit`/`Convert` interaction with multi-read `newbytes`.** Detection now runs once over a potentially much larger accumulated chunk (spanning several physical reads) instead of per 64KB read, meaning more bytes can be speculatively over-read past a `Quit` binary byte before being truncated via `self.end = oldend + i`. This is a latency/waste side-effect of the same batching change as the main finding above, not a separate correctness bug (the truncation and offset math are unchanged and correctly bound `self.end`/`last_lineterm`/`binary_byte_offset`).
- No project `CLAUDE.md` or equivalent convention doc exists in the target repo (`repos/10`), so no `CONVENTION_VIOLATION` checks were applicable.
