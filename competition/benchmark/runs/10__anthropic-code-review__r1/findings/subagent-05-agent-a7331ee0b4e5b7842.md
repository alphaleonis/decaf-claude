# subagent agent-a7331ee0b4e5b7842

Analysis complete. I traced all six scenarios against the code, callers (`glue.rs` `run`/`fill`), `roll()` semantics, and `preceding()`.

Depth: standard — ~25 executable lines changed (fill() single-read → inner fill-loop; roll() `max_context()` → `before_context`), no auth/payment/data-mutation domain, but subtle buffer/IO with output-correctness and binary-detection impact, so I ran assumption + composition + abuse techniques plus a cascade attempt on `roll()`.

```json
[
  {
    "file": "crates/searcher/src/line_buffer.rs",
    "line": 419,
    "severity": "High",
    "category": "performance",
    "issue": "[ADV_ABUSE] Low-rate interactive stream (tail -f | rg ERROR) yields one complete line then read() blocks -> new inner loop keeps calling read() until the buffer is FULL (never checks for a line terminator between reads) -> fill() does not return, so no match is emitted until 64KB (or, with large -A, several MB) has accumulated or the stream closes -> live-follow output stalls indefinitely on a slow producer.",
    "fix": "Break out of the inner read loop once at least one line terminator is present in the newly read bytes (or after the first non-zero read), instead of only when free_buffer() is empty or read()==0 — i.e. keep the amortization for bulk/file reads but return promptly once a complete line is available so interactive streams stay line-latent.",
    "confidence": 75,
    "pre_existing": false
  }
]
```

Mechanics (forward): reader delivers `line1\n` (e.g. 12 bytes) → inner `while !free_buffer().is_empty()` appends them, `end=12`, free still ~65524 bytes → loops → `read()` blocks (producer idle, write end open) → nothing emitted. Backward check: for output to appear, `fill()` must return; it returns only after the `while` exits (buffer full or `read()==0`) then finds a lineterm — both require the buffer to fill or the stream to close, neither of which a slow producer does. Paths converge. The old code checked for a terminator after each read and could return early; this is the regression, and it is amplified by large `-A` (the very flag this PR optimizes) because the buffer grows, raising the accumulation threshold from 64KB into the megabytes. I rate it High (stuck live-monitoring workflow, output correct-but-delayed) but flag it as very likely a deliberate batch-throughput tradeoff the author accepted — the maintainer should confirm intent.

## Considered But Not Flagged

- **Scenario 1 (transient `Ok(0)` then more data):** Falls apart — old single-read code also treated the first `Ok(0)` in a `fill()` as EOF, and the new code is if anything more tolerant (it processes bytes read before the `Ok(0)` and can return a complete line). Any misbehavior (emitting a partial line as complete) requires a reader that returns `Ok(0)` then more data, a `Read`-contract violation, and is identical to old behavior. Not a regression.

- **Scenario 3 (EOF exactly at full buffer, no trailing newline, size = multiple of buffer):** Traced end-to-end. When the buffer fills with no lineterm, the outer loop re-enters `ensure_capacity` (grows), the next inner read returns `Ok(0)`, `newbytes` is empty → `last_lineterm = self.end`, returns `Ok(buffer non-empty)`. `last_lineterm == end == pos-relative buffer end`. No off-by-one in `last_lineterm`/`buffer()`.

- **Scenario 4 (binary Quit truncation `self.end = oldend + i`, 262146→262142):** The truncation keeps *all* bytes before the first binary byte (`[oldend, oldend+i)`); bytes before `oldend` were processed in prior fills. No searchable byte is dropped and `binary_byte_offset` is identical (262153 in both old/new). The 4-byte `byte count` delta (262142 vs 262146) is a `--stats` accounting artifact of where the *last* buffer boundary landed before quitting — not a dropped byte and not a lost match. `absolute_byte_offset + (oldend+i)` / `+ end` offset math is correct because `pos==0` after roll. Benign test update.

- **Scenario 5 (roll uses `before_context` not `max_context()`):** This is the actual fix, and it is correct. After-context is not protected by the `preceding()` count — it is protected by the `consumed = max(context_start, last_line_visited)` floor. `fill()` (glue.rs:59) asserts the buffer is fully processed before `roll()`, and `match_by_line_slow`/`_fast` emit after-context for every *complete* line (advancing `last_line_visited`) before `pos` reaches buffer end; only the trailing partial line remains, and its start equals `last_line_visited`, so `consumed` never exceeds it. Using `before_context` (≤ `max_context`) only reduces over-retention of front bytes for future before-context — the performance bug being fixed. Constructed `-A 5`/`-B 0` match-near-buffer-end cases: partial after-context line always retained. No candidate revert-probe found; no `### Probe Requests`.

- **Scenario 6 (`self.end += readlen` overflow):** Requires a `Read` impl that reports `readlen > free_buffer().len()` (contract violation); would panic on the `buf[oldend..self.end]` slice rather than corrupt. Identical exposure to the old single-read code (not newly worse — each inner read still gets a shrinking `free_buffer()`), and unreachable with ripgrep's real readers (File/Stdin/decompressors). Anchor 25, not reported.
