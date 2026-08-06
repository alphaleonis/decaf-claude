# subagent agent-a704884ea5794b33a

## Performance Review — ripgrep PR #3185 (fix slow `-A/--after-context` on stdin)

Read in full: `crates/searcher/src/line_buffer.rs` (`fill` L406-477, `roll` L485-498, `ensure_capacity` L504-527), `crates/searcher/src/searcher/core.rs` (`Core::roll` L185-213, `count_lines` L661-671), `crates/searcher/src/lines.rs` (`preceding`/`preceding_by_pos` L157-197), `crates/searcher/src/searcher/glue.rs` (`ReadByLine::fill`/`run` L38-88). Also read both upstream commits (`8c6595c`, `d4b77a8`) for the authors' own benchmark evidence.

### Does the fix achieve its goal?

Yes, verified two ways:

- **`Core::roll` (core.rs L198-202):** `preceding(buf, term, before_context)` replaces `preceding(buf, term, max_context())`. Since `before_context ≤ max_context()` always, this call can only do less-or-equal work than before — strictly cost-reducing, no new worst case. For the reported bug's repro (`-A` only, `before_context == 0`), `preceding` now returns essentially "start of the last line," so each roll retains O(1) bytes instead of O(after_context) bytes. `LineBuffer::roll`'s `copy_within` memmove (line_buffer.rs L494) is bounded by that retained size, so it drops from O(N) to O(1) per roll. This matches the authors' own numbers in commit `d4b77a8`: `maxmem` stays ~30MB flat as `-A` grows from 999 to 999999, and wall-clock stays ~2s instead of climbing to 6.6s — confirms the O(N²)-ish blowup is gone.
- **`fill`'s inner read loop (line_buffer.rs L419-425):** batches multiple `rdr.read()` calls into one outer `fill()` iteration. For stdin, a single `read()` caps at ~64K (per the author's own measurement, noted in commit `8c6595c`), so previously a buffer grown past 64K (by `-A`/`-B` needing more retained context) was filled only 64K at a time even though `ensure_capacity`'s doubling strategy assumed much larger amortized reads — defeating the amortization the buffer-growth strategy was designed around. Batching reads before the newline/binary scan restores that amortization. Confirmed by the author's benchmarks in `8c6595c` (`-A999999` stdin: 6.9s → 2.0s after this half of the fix alone).

No `ensure_capacity`-interaction issue: the inner loop only drains the free space that `ensure_capacity()` already established: it does not call `ensure_capacity()` again itself, so it cannot trigger extra/uncontrolled doubling beyond what the outer loop would already have done. No extra syscall at EOF (loop breaks immediately on `readlen == 0`). `free_buffer()` is O(1) slicing, negligible at any scale.

### New cost introduced by this diff

```json
[
  {
    "file": "crates/searcher/src/line_buffer.rs",
    "line": 419,
    "severity": "Medium",
    "category": "performance",
    "issue": "[PERF_HOT_PATH] fill()'s new inner read loop only returns to the caller (and thus only lets Core emit matched/context lines) once the entire free buffer is filled or EOF is hit, instead of after every individual read() as before. For a slow/streaming stdin producer (e.g. `tail -f log | rg -A5 err`, `journalctl -f | rg ...`), each read() on a pipe blocks until at least one byte arrives, so the loop keeps re-entering read() and accumulating small chunks until the free buffer (64KB default, or several MB when grown by a large -A/-B/-C) is completely full — output can be delayed by up to that many bytes' worth of wall-clock time versus near-immediate emission previously. At the scale of a low-throughput live log (bytes trickling in far slower than 64KB/interval), this can mean minutes of apparent 'no output' where the old code emitted matches after the very next line arrived.",
    "fix": "If sub-buffer streaming responsiveness is a design goal, bound the inner loop so it stops and lets the caller check for a lineterm as soon as *any* new line terminator appears in the bytes read so far, rather than only after free_buffer() is exhausted or EOF — e.g. break out early once `self.buf[oldend..self.end]` contains the line_term byte, falling back to the fill-loop only when no terminator is found yet (mirrors the old single-read behavior's responsiveness while still batching when a large read is genuinely available in one go).",
    "confidence": 75,
    "pre_existing": false
  }
]
```

## Considered But Not Flagged

- **`Core::roll`'s `preceding()` cost for `-B`/`-C`-heavy input** — when `before_context` is itself huge, `preceding()` and `LineBuffer::roll`'s memmove legitimately scan/copy O(before_context) bytes per roll; this is inherent to correctly supporting large before-context (you must retain those bytes to look backward) and is not worsened by this diff — the old code already paid at least this much (via `max_context() ≥ before_context`). Not a regression.
- **`ensure_capacity` doubling (`BufferAllocation::Eager`)** — unaffected by the diff; the inner read loop never calls it again mid-fill, so it can't trigger more/larger allocations than the old code eventually would have via repeated outer-loop iterations. Anchor 0 (no new cost).
- **Extra syscalls at true EOF** — none; the inner loop exits on the same `readlen == 0` check that ended the old single-read path.
- **Regular-file (non-stdin, non-pipe) searches** — `read()` on files typically fills the requested buffer in one call (noted directly in the author's commit message and consistent with `mmap.rs` not applying to stdin), so the inner loop degenerates to exactly one `read()` call, identical to pre-diff behavior. No new cost on the file-search hot path, which is ripgrep's primary use case. Anchor 0.
- **`count_lines` (core.rs L661-671)** — bounded by `consumed`, which the fix makes smaller (or equal), not larger. No new cost.

## Probe Requests

None run (analysis was conclusive from code + the authors' own before/after benchmark output in the git history). If empirical confirmation of the streaming-latency finding above is wanted, a reviewer with execution budget could nominate:
- `mkfifo /tmp/slowpipe && (while true; do echo match; sleep 5; done > /tmp/slowpipe &) && timeout 20 target/release/rg match -A2 < /tmp/slowpipe` — pre- vs post-diff, observing whether/when the first match line is printed, to empirically confirm the buffer-fill-gated latency described above.
