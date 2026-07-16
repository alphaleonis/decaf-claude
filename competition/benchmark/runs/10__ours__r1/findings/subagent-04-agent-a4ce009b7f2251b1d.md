# subagent agent-a4ce009b7f2251b1d

## Performance Review — ripgrep PR #3185 (`-A/--after-context` stdin fix)

### Method note
Read `line_buffer.rs` (fill/roll/ensure_capacity), `searcher/core.rs::roll`, `lines.rs::preceding`, `searcher/glue.rs`, and the two upstream commit messages (which contain the author's own `bigger.txt` benchmarks) to ground the analysis. To settle question (2)/(4) empirically rather than by inspection alone, I wrote a throwaway, **untracked** example (`crates/searcher/examples/binary_quit_bench.rs`, deleted after use — `git status --porcelain` confirms the tree is clean) that drives the *current* `Searcher` public API with a synthetic `Read` that (a) forces the internal `LineBuffer` to grow past its default 64KB capacity via one long unterminated "warm-up" line, then (b) places a `Quit`-mode binary byte (`NUL`) as the very first byte of the next chunk, with abundant further non-NUL data available afterward. This isolates exactly how much the code over-reads past a detectable binary byte once the buffer has already grown.

Results:
| warm-up (forces buffer to) | bytes read past the NUL before search stopped |
|---|---|
| ~500 KB → buffer grows to ~590 KB | 89,823 bytes |
| ~8,000,000 bytes → buffer grows to ~15.9 MB | 7,925,247 bytes |

For comparison, the pre-diff code (one `read()` call per `fill()` outer-iteration, immediately followed by the binary check) bounds this waste to at most one `read()` call's worth — ≤64KB on stdin per the PR's own diagnosis ("`read` on `stdin` never seems to fill more than 64K"). The new code's waste scales with buffer capacity at the time, confirmed directly by the two data points above (~18x growth in warm-up → ~88x growth in wasted bytes, consistent with the doubling `ensure_capacity` schedule).

Questions (1) and (3) from the brief were also traced through the code and are *not* regressions — see "Considered But Not Flagged."

```json
[
  {
    "file": "crates/searcher/src/line_buffer.rs",
    "line": 419,
    "severity": "Medium",
    "category": "performance",
    "issue": "[PERF_HOT_PATH] The new inner `while !self.free_buffer().is_empty()` loop unconditionally drains the entire free buffer (via repeated `read()` calls) before the Quit-mode binary-detection check at line 442 ever runs. Once the LineBuffer's backing `Vec<u8>` has grown large — via a prior long/unterminated line, or via large `-A`/`-B` context forcing `ensure_capacity` doublings earlier in the stream — a binary byte that is the very first byte of the next chunk is not detected until up to the *entire* current buffer capacity has been read. Empirically confirmed: after forcing buffer growth to ~15.9MB, the search read 7,925,247 bytes past a NUL byte before stopping (vs. bounded to <=64KB in the pre-diff single-read-per-fill code, since that code checked for the binary byte after every individual read()).",
    "fix": "Check for the Quit byte (or run rfind_byte for the line terminator) after each individual `read()` inside the inner loop, not just once after the loop drains free_buffer — e.g. move the `BinaryDetection::Quit` check into the inner while loop over the newly-read slice for each read call, breaking out and truncating `self.end`/`self.last_lineterm` as soon as the byte is seen, so worst-case over-read stays bounded by one `read()` call regardless of how large the buffer has grown.",
    "confidence": 75,
    "pre_existing": false
  }
]
```

## Considered But Not Flagged

- **`-B/--before-context` performance (question 1)**: `core.rs::roll` now passes `self.config.before_context` instead of `self.config.max_context()` to `lines::preceding`. `max_context() = cmp::max(before_context, after_context)` (confirmed in `searcher/mod.rs:213-215`). For `-B`-only usage (`after_context == 0`), `max_context() == before_context`, so the value passed to `preceding()` is byte-for-byte identical before and after this diff — no regression, confirmed by code inspection. For combined `-A`+`-B`, `before_context <= max_context()` always, so the new code can only do equal or less work than before, never more. The author's own commit (`d4b77a8`) benchmarks on `bigger.txt` show `-B99999` already at ~5s post-fix vs. GNU grep's ~105s, reinforcing this is a pure win with no `-B` downside. Anchor 100 (verifiable from code + author's own numbers), suppressed only because it's a non-finding (confirms soundness, not a defect).
- **`rfind_byte` over larger `newbytes` per fill (question 3)**: `rfind_byte` scans backward from the end and stops at the first match. For typical text (short lines), the scan distance is bounded by "distance to the last line terminator," independent of whether the surrounding chunk is 64KB or several MB — so batching doesn't increase total bytes scanned by `rfind_byte` in the common case. For the pathological "no terminator anywhere in this chunk" case, the total bytes scanned across all `fill()` outer-iterations telescopes to O(total buffer content) in *both* the old and new code (each `rfind_byte` call only rescans the newly-appended portion, `newbytes`, not the whole buffer). Net effect of batching here is reduced call/iteration count (fewer redundant match-on-`self.config.binary` + fixed setup costs per amortized byte), matching the PR's own stated goal — not a new cost. Anchor 75+, dismissed as it's the intended amortization win, not a defect.
- **Peak memory growth schedule for pathological no-terminator input (question 4, memory dimension)**: `ensure_capacity`'s doubling logic (`len * 2` for `BufferAllocation::Eager`, capped for `BufferAllocation::Error(limit)`) is unchanged by this diff and is invoked identically (once per outer-loop iteration, gated on `free_buffer().is_empty()`) in both old and new code. The growth trajectory to consume a given total amount of un-terminated data is therefore the same regardless of how many `read()` syscalls it takes to fill each doubling step — confirmed by inspection; the diff changes read-call cadence, not the capacity-growth trigger. No new memory-exhaustion regression beyond the pre-existing (and unchanged) `BufferAllocation::Eager` unbounded-growth behavior for adversarial no-newline streams. Anchor 50 (pre-existing behavior, not amplified by this diff) — not reported per pre-existing/Critical-only rule.

### Probe Requests
None outstanding — the empirical measurement needed to settle question (2)/(4) was already run via an untracked scratch example (`crates/searcher/examples/binary_quit_bench.rs`), which was deleted afterward; `git status --porcelain` shows a clean tree with no tracked-file modifications.

### Files referenced
- `/home/decaf/code/decaf-claude/competition/benchmark/repos/10/crates/searcher/src/line_buffer.rs` (lines 406-477: `fill()`; 485-498: `roll()`; 500-527: `ensure_capacity()`)
- `/home/decaf/code/decaf-claude/competition/benchmark/repos/10/crates/searcher/src/searcher/core.rs` (lines 185-213: `roll()`)
- `/home/decaf/code/decaf-claude/competition/benchmark/repos/10/crates/searcher/src/searcher/mod.rs` (lines 213-215: `max_context()`)
- `/home/decaf/code/decaf-claude/competition/benchmark/repos/10/crates/searcher/src/searcher/glue.rs` (lines 58-93: `ReadByLine::fill`)
- `/home/decaf/code/decaf-claude/competition/benchmark/repos/10/crates/searcher/src/lines.rs` (lines 157-197: `preceding`/`preceding_by_pos`)
