# subagent agent-a631d51976f8ac052

# Code Review

**Reviewer**: broad-reviewer
**Date**: 2026-07-16
**Scope**: `crates/searcher/src/line_buffer.rs` (`LineBuffer::fill`), `crates/searcher/src/searcher/core.rs` (`Core::roll`), `crates/searcher/src/searcher/glue.rs` (golden-test constants), `CHANGELOG.md` — PR BurntSushi/ripgrep#3185

## Summary

| Severity | Count |
|----------|-------|
| 🔴 Critical | 1 |
| 🟠 High | 0 |
| 🟡 Medium | 1 |
| 🟢 Low | 0 |

**Verdict**: CRITICAL_ISSUES

## Project Standards Applied

No project-specific `CLAUDE.md`/standards file found in this repository; Category 3 (Project Conformance) is skipped. Knowledge Preservation, Production Reliability, and Structural Quality categories applied.

---

## Findings

### 🔴 Critical: `fill()`'s inner read loop defeats `--line-buffered` / streaming stdin (blocks until buffer full or EOF)

| | |
|---|---|
| **File** | `crates/searcher/src/line_buffer.rs:414-437` |
| **Category** | DATA_LOSS (silent output-withholding) / KNOWLEDGE_LOSS (undocumented trade-off) |
| **Confidence** | 100 (anchor) — externally verified, see below |
| **Pre-existing** | no — introduced by this diff |

**Issue:** The new inner loop

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

keeps calling `read()` until the *entire* free buffer (default 64 KiB, growing) is full or the reader hits true EOF, before any binary detection, line-terminator search, or return to the caller happens. For a blocking pipe/stdin source, a `read()` call that has no data currently available blocks. So once one short `read()` returns a complete line (e.g. a single `journalctl -f` log line, a few hundred bytes), the loop immediately issues another `read()` that blocks waiting for *more* data — even though a complete, matchable line is already sitting in the buffer. Nothing is handed to `Core`/`Sink` (and therefore never flushed to output) until either ~64 KiB has accumulated or the upstream process closes its end. For `tail -f`/`journalctl -f`-style pipelines — the exact use case the `--line-buffered` flag exists for (`crates/core/flags/defs.rs:3565`: `tail -f something.log | rg foo --line-buffered | rg bar`) — this means output never appears at all as long as the source keeps streaming below the buffer threshold, i.e. the flag becomes silently non-functional.

**Why Critical (dual-path, and independently confirmed against upstream ground truth):**
- Forward: inner loop only stops on full-buffer-or-EOF (X) → a slow/streaming reader blocks on a redundant `read()` after a line is already available (Y) → the match is withheld from the sink indefinitely, defeating `--line-buffered`'s entire purpose (Z).
- Backward: for output to be silently withheld (Z), `fill()` must not return once a full line is available (Y), which requires the loop's exit condition to be buffer-full-or-EOF rather than "any bytes read" (X) — which is exactly what the code does.
- This is not speculative: I fetched the real upstream ripgrep repository (`https://github.com/BurntSushi/ripgrep`) and confirmed that exactly 5 days after this PR merged (commit `d4b77a8`, matching this repo's HEAD), BurntSushi authored commit `d47663b1b454` — *"searcher: fix regression with `--line-buffered` flag"* — which **reverts precisely this hunk** (`git diff` of that commit removes the inner `while !self.free_buffer().is_empty()` loop and restores the single `read()` call), while explicitly keeping the `core.rs` `roll()`/`before_context` fix. The commit message states: *"this change is clearly contrary to how `--line-buffered` works. We specifically do _not_ want to wait around until the buffer is full."* It fixes issue `#3194`, *"Line buffering appears broken in 15.0.0,"* whose reporter demonstrates precisely this: `journalctl -n5 -f | rg --no-config --line-buffered 'Oct'` produces **no output** because stdin never closes and the buffer never fills, whereas `journalctl -n5000 -f | ...` does produce output once enough backlog fills the buffer once.
- The revert also reverted the `glue.rs` byte-count constants (`262142` → back to `262146`) and the `CHANGELOG.md` entry, exactly matching the three files touched by this diff.

**Fix:** Revert the inner-loop change and go back to one `read()` call per outer-loop iteration, returning to the caller as soon as any complete line is found (the `core.rs` `roll()`/`before_context` fix is independent and should be kept — it was *not* reverted upstream):

```rust
self.roll();
assert_eq!(self.pos, 0);
loop {
    self.ensure_capacity()?;
    let readlen = rdr.read(self.free_buffer())?;
    if readlen == 0 {
        self.last_lineterm = self.end;
        return Ok(!self.buffer().is_empty());
    }
    let oldend = self.end;
    self.end += readlen;
    let newbytes = &mut self.buf[oldend..self.end];
    // ... binary detection / lineterm search unchanged ...
}
```

**Actionability Check:**
- [x] Fix specifies exact change (drop the inner `while` loop; restore single-read-per-iteration semantics)
- [x] Fix requires no additional decisions — this is the actual fix BurntSushi shipped upstream

### Probe Requests

- **Test file**: `crates/searcher/src/line_buffer.rs` tests module (or a new integration test in `crates/searcher/tests/`)
- **Proposed test**: construct a custom `io::Read` that, on the first call, returns a small chunk containing one full line + terminator, and on the second call blocks/panics if called (to simulate "no more data available yet"). Call `LineBuffer::fill()` and assert it returns `Ok(true)` after only the first `read()` call.
- **Production line to remove for the probe** (already identified, not executed): `crates/searcher/src/line_buffer.rs:419-425`, the `while !self.free_buffer().is_empty() { ... }` loop — replacing it with a single `read()` call.
- **Expected result**: with the current code, `fill()` calls `read()` a second time (violating the test's "must not be called again" expectation / would block on a real pipe); with the loop removed, `fill()` returns after the first `read()`.

---

### 🟡 Medium: No regression test exercises `fill()`'s incremental/streaming return behavior

| | |
|---|---|
| **File** | `crates/searcher/src/line_buffer.rs` (test module, not shown in diff) |
| **Category** | TESTING_VIOLATION / test-coverage gap |
| **Confidence** | 75 (anchor) |
| **Pre-existing** | no — gap is specific to the new inner-loop behavior introduced here |

**Issue:** All existing `grep-searcher` unit tests (77 passing, including the `binary3`/`binary4` golden tests touched by this diff) operate on fully-materialized byte slices/readers and only assert final aggregate output (byte counts, binary offsets, matched lines). None of them model a reader that yields data incrementally over multiple `read()` calls and assert *when* `fill()` returns relative to that timing. That is precisely the dimension the Critical finding above breaks, and it is exactly why the regression shipped in ripgrep 15.0.0 undetected by CI and was only caught by a live user running `journalctl -f | rg --line-buffered` in production (issue #3194).

**Fix:** Add a test using a `Read` impl that returns bytes in controlled small chunks (with an assertion/panic if `read()` is invoked more times than expected for one `fill()` call), verifying `fill()` returns as soon as one complete line is available rather than waiting to fill the whole buffer.

**Actionability Check:**
- [x] Fix specifies exact change (add an incremental-reader unit test in `line_buffer.rs`'s `#[cfg(test)] mod tests`)
- [x] Fix requires no additional decisions

---

## Considered But Not Flagged

- **Binary-detection read-ahead (byte-count shift 262146 → 262142, `glue.rs`)**: this is a real, intentional behavior change (binary detection and the last-lineterm scan now run over a full accumulated read rather than per single `read()` call), but it is explicitly documented in the updated test comments, validated by the golden-test updates, and — unlike the streaming-return issue — does not have a "hang/never return" failure mode; it only shifts *which* bytes get reported as searched at a buffer boundary. Confidence that this is a correctness bug: 0 (matches upstream's kept behavior; only the `--line-buffered`-breaking inner loop was reverted, not this).
- **`Core::roll`'s `consumed = max(context_start, self.last_line_visited)` clamp**: this line and its surrounding logic are pre-existing (unchanged by the diff) — only the argument to `lines::preceding` changed from `self.config.max_context()` to `self.config.before_context`. Verified that after-context correctness does not depend on retained buffer bytes: `after_context_left` is a counter on `Core` that survives `roll()` unmodified and is consumed against freshly-read buffer content on the next fill, not via backward scanning into retained bytes. This matches the new code comment's rationale and is corroborated by the fact that upstream kept this exact change when it reverted the sibling `line_buffer.rs` fix five days later (commit `d47663b1b454` only touches `line_buffer.rs`/`glue.rs`, not `core.rs`).
- **Extra harmless `read()` call after EOF in `fill()`'s outer loop**: if the inner `while` loop breaks due to EOF (`readlen == 0`) after a partial (non-buffer-filling) read that itself contains no line terminator, the outer `loop` will re-enter and issue one more `read()` call on the already-exhausted reader before finalizing. This is a single extra syscall in a narrow edge case (unterminated final line + EOF hit mid-buffer) — real but negligible impact (anchor 50, Low severity), not worth a standalone finding given the Critical finding above already covers the loop's core design flaw.
- **Progress/termination of the inner `while` loop in general**: verified safe — `self.end` strictly increases on every non-zero read, so the loop terminates once `free_buffer()` empties or a conformant `Read` impl signals EOF via `Ok(0)`. No infinite-loop risk beyond what already existed for non-conformant `Read` implementations in the pre-diff code.

## Positive Observations

- The `Core::roll` optimization (`core.rs:198-202`) is a well-targeted, correctly-reasoned fix: it recognizes that after-context lines are satisfied via the persistent `after_context_left` counter rather than backward buffer scanning, so `lines::preceding` only needs `before_context`, not `max_context()`. This is confirmed correct by the fact that upstream ripgrep kept this exact change even after reverting its sibling fix for a real regression — independent third-party validation that this half of the PR is sound.
- The new doc comment on `Core::roll` clearly explains *why* only `before_context` is needed, which is good knowledge preservation for that half of the change.
- The `binary3`/`binary4` golden-test updates are accompanied by explanatory comments describing why the Read-based searcher's byte count differs from the Slice-based searcher's, which is good practice for keeping intentional test-value changes understandable.
