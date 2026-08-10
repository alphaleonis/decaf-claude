Below is the reviewer subagent's full report, verbatim.

---

# Code Review: searcher — fix a performance bug with `-A/--after-context`

## Context

The change comprises two commits by the ripgrep author (BurntSushi, upstream PR #3184), both targeting the same performance pathology where search time grew super-linearly with large `-A/--after-context` values:

1. **`8bf6f0a2`** (`line_buffer.rs`) — wraps `rdr.read()` in an inner loop that fills the whole free buffer before doing binary detection / line-terminator search. Fixes the stdin-specific case where `read` returns ≤64K per call and the buffer was under-filled, defeating the amortization that the capacity-growth logic assumes.
2. **`146f78f7`** (`core.rs`) — in `roll`, changes the `preceding()` line-scan count from `max_context()` to `before_context`, so the potentially expensive backward line scan retains only the lines actually needed (before-context), not `max(before, after)`.

Plus the matching CHANGELOG entry and two `glue.rs` test-expectation updates.

## Strengths

- **Correct root-cause fix, not a workaround.** The `core.rs` change is grounded in the actual data-retention requirement. I traced the after-context path: it is emitted *forward* via the persistent `after_context_left` counter (`core.rs:281-308`, `after_context_by_line`), which `roll` does not reset — only `last_line_counted`/`last_line_visited` are cleared. So after-context genuinely does not need retained backward buffer data, and retaining only `before_context` lines is sufficient. The change is sound.
- **The `before_context == 0, after_context > 0` corner case is preserved.** `roll` still enters the else-branch because its guard is `max_context() == 0`, and `preceding(buf, term, 0)` returns the start of the last line, giving the "previous line visited" reference the context-separator logic needs. The added comment documents exactly this.
- **Good test coverage already exists and passes.** `SearcherTester` runs each case through *both* the streaming line-buffer reader and the slice reader and compares — so any output divergence introduced by the fill/roll changes would fail. All 77 `grep-searcher` unit tests + doctest pass, including `context_*`, `big1`, `binary3`, `binary4`.
- **EOF/termination logic in the rewritten `fill` is correct.** `oldend` is captured before the inner loop; `newbytes.is_empty()` after the loop correctly detects "read 0 immediately" as EOF, and a partial-then-EOF read still processes the bytes and terminates on the next outer iteration.
- Clear, honest commit messages with reproduced benchmarks; CHANGELOG placed correctly under "Performance improvements."

## Issues

### Critical (Must Fix)
None.

### Important (Should Fix)

**1. Input latency regression for slow/interactive streams — `crates/searcher/src/line_buffer.rs:419-425`**

The new inner loop reads until the free buffer (64 KB by default, larger under big `-A`) is *full* or EOF:

```rust
while !self.free_buffer().is_empty() {
    let readlen = rdr.read(self.free_buffer())?;
    if readlen == 0 { break; }
    self.end += readlen;
}
```

The previous code returned from `fill()` as soon as a single `read()` produced a chunk containing a line terminator. [Inference — based on standard POSIX pipe `read()` semantics, not empirically measured here; this is expected behavior, not guaranteed] For a producer that emits complete lines but slowly with pauses (e.g. `tail -f access.log | rg ERROR`), `read` returns the available line, the loop sees remaining free space and calls `read` again, which blocks until the writer sends more. Net effect: matches are withheld until ~64 KB accumulates or the stream closes, whereas before they surfaced per newline-containing chunk.

Why it matters: it's a user-visible responsiveness change for live-filter usage. It does not affect correctness or bulk-throughput cases (`cat file | rg`, files), which is exactly where the perf win lands. Given the upstream author authored this tradeoff deliberately, it is most likely an accepted one — but it should be a conscious decision. Recommend confirming intent and, if line-latency matters, considering a bounded fill (e.g. stop the inner loop once a line terminator has been read rather than only when the buffer is full).

### Minor (Nice to Have)

**2. `--stats` "bytes searched" shifts in the binary-quit streaming edge case — `crates/searcher/src/searcher/glue.rs:740,774`**

The updated expectations (`262146 → 262142`, a single `zzz\n`) are correct and consistent: with the fuller buffer, the line-buffer reader hits the binary-quit boundary 4 bytes earlier *in reported byte count*. The slice-reader value (`262153`) and the actual match output (`0:a`) are unchanged, so this is a benign statistic shift, not a masked bug. Worth being aware that `--stats` byte counts can differ slightly for streaming reads that terminate on binary detection. No action required beyond awareness.

**3. CHANGELOG wording — `CHANGELOG.md:12`**

"Improve performance of large values with `-A/--after-context`" reads awkwardly; "Improve performance with large values of `-A/--after-context`" is clearer. Trivial.

## Recommendations

- Confirm the streaming-latency tradeoff (Issue 1) is intentional; if this is a faithful upstream port, note that upstream accepted it and no change is needed.
- No test gap for the fix itself — the dual-reader `SearcherTester` harness is the right guard and already exercises the changed paths. If you want belt-and-suspenders coverage for the *stdin*-specific pathology, an integration test asserting output equivalence for a large `-A` value across file vs. piped-stdin input would lock in the fixed behavior, but it's optional given existing coverage.

## Assessment

**Ready to merge?** With fixes — really "with confirmation." The code is correct and well-tested; there are no correctness defects. The only substantive item is confirming that the intentional input-latency change (Issue 1) is acceptable.

**Reasoning:** Both fixes address the real root cause (under-filled reads defeating amortization; over-broad backward line scanning), the after-context-forward-emission invariant that makes the `before_context`-only retention safe holds up under tracing, and the full existing dual-reader test suite passes — the sole caveat is a deliberate streaming-responsiveness tradeoff worth an explicit sign-off.
