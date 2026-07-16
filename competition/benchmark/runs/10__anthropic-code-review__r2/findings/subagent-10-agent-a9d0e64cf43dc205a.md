# subagent agent-a9d0e64cf43dc205a

I've completed my system-model extraction and design evaluation. My analysis directly traced the two changes through the streaming search pipeline (`search_reader` → `ReadByLine::fill` → `LineBuffer::fill`/`roll`; and `Core::roll` → after-context emission). Here is my report.

---

## System Model (reference frame)

- **Boundary / contract under review**: `LineBuffer::fill()` is the read-boundary between an arbitrary `io::Read` and the line-oriented search core. Its public entry is `Searcher::search_reader` (mod.rs:727), a published API of the `grep-searcher` crate. `Core::roll()` is the window-advance boundary that decides how many already-searched bytes to discard vs. retain as before-context.
- **Data flow**: `ReadByLine::run` loops `fill()` → `match_by_line(buffer)`. Before each refill, `Core::roll(buf)` computes `consumed`; `rdr.consume(consumed)` discards it; `rdr.fill()` rolls retained bytes to the front and reads more.
- **Concurrency**: none — single-threaded streaming. No shared mutable state.
- **Carried state across windows**: `after_context_left` (counter) + forward `last_line_visited`; both reset per roll (`last_line_visited=0`), with pending after-context re-emitted from newly-read data.

## Findings

```json
[
  {
    "file": "crates/searcher/src/line_buffer.rs",
    "line": 419,
    "severity": "Medium",
    "category": "design",
    "issue": "[API_CONTRACT] fill() now drains reads until the free buffer is full (or EOF) instead of returning after the first read that yields a complete line. This silently changes the blocking/latency contract of the public streaming path (Searcher::search_reader) for interactive/slow readers: fill() blocks waiting to accumulate ~64KB (or buffer-capacity) of input rather than surfacing a complete line as soon as it arrives.",
    "fix": "If prompt streaming of an interactive reader is a supported use case, gate the drain loop so it only over-reads when amortization is actually needed (e.g. when a large context window has forced buffer growth), or break out of the inner loop once a line terminator has been observed in the accumulated bytes. Otherwise, document on fill() that it deliberately blocks to fill the buffer and is not intended for line-at-a-time interactive streaming, so consumers of search_reader understand the latency tradeoff.",
    "confidence": 75,
    "pre_existing": false
  }
]
```

### Detail on the finding (design questions asked)

**Q1 — Is the `fill()` EOF contract preserved exactly, and does latency/blocking change?**

- *EOF correctness*: **Preserved.** The old code returned EOF the instant a single `read()==0`. The new code breaks the inner drain loop on `read()==0`, then keys EOF off `newbytes.is_empty()`. A final partial line (bytes read, then `0`, no terminator) is still surfaced: the outer loop re-enters, the inner `while` immediately reads `0` again (free buffer still non-empty), `newbytes` is empty, and it sets `last_lineterm = self.end` and returns `Ok(!buffer().is_empty())` — identical terminal behavior to the old code. Binary `Quit`/`Convert` offsets are computed relative to `oldend` (the end before the drain) with `pos==0`, so accumulating across multiple reads does not shift `binary_byte_offset`. Verified consistent with all 20+ `buffer_*` unit tests.
- *Latency/blocking*: **Changed, and this is the finding.** For a reader that delivers a complete line then would block (a slow pipe, `tail -f`, any incremental producer), the old code returned `Ok(true)` after the terminator was seen; the new inner `while` loops and calls `read()` again, which blocks until more input arrives or the writer closes. Concrete consequence via public `search_reader`: `slow_producer | rg pattern` no longer emits matches promptly — output is withheld until ~64KB accumulates or the stream closes. For an unbounded stream that stays under a buffer's worth of new data for a long time, ripgrep can appear hung despite matches existing. The mechanism is certain from the code; the *impact* depends on whether the reader is interactive, hence Medium/75 rather than higher. It is plausibly an intentional tradeoff (the commit targets stdin throughput), but it is an unstated behavioral-contract change on a public API and worth surfacing.

**Q2 — Is "after-context needs no preserved preceding lines" a true system property?**

**Yes, sound.** After-context is always emitted *forward* from an already-found match, and pending state is carried by the `after_context_left` counter plus forward progress, not by retaining backward lines. I traced both `match_by_line_fast` (trailing `after_context_by_line(buf, buf.len())`, core.rs:419) and `match_by_line_slow` (inline `sink_after_context`, core.rs:369): whenever a window ends with `after_context_left > 0`, emission has advanced `last_line_visited` to `buf.len()`, so `consumed = max(context_start, last_line_visited)` collapses to `buf.len()` and nothing owed is discarded. When `after_context_left` has hit `0`, no after-context is owed and discarding lines beyond the `before_context` tail is correct. The retained region therefore only ever serves before-context for matches in newly-read data, for which exactly `before_context` preceding lines suffice. The `max(context_start, last_line_visited)` guard still protects unemitted after-context. The `before_context==0 && after_context>0` separator case is also preserved: `preceding(…, 0)` retains the last line so `sink_break_context`'s `is_gap` reference survives the roll. Corroborated by the passing context test suite in glue.rs.

**Q3 — Any stale contract in the `fill()` doc-comment?**

**No stale statement found.** The doc comments (line_buffer.rs:243–256 and 389–405) describe discarding consumed bytes, refilling from the reader, and `false`=EOF/`true`=more — all still accurate. They never promised "reads once" or "returns after bounded data," so nothing is falsified. The *omission* of the new "blocks to fill the buffer" behavior is the documentation gap noted in the fix above (its rationale lives only in the commit message).

## Considered But Not Flagged

- **`roll()` max_context → before_context change (core.rs:198–205)** — Verified correct, not a defect (see Q2). This is the actual performance fix: retaining `max(before, after)` preceding lines forced the buffer to hold and recopy up to `-A` lines every roll; retaining only `before_context` is provably sufficient.
- **EOF / `last_lineterm` / `binary_byte_offset` invariants** — Preserved exactly (see Q1); offsets computed from `oldend` with `pos==0` are unaffected by multi-read accumulation.
- **Extra `read()==0` call at EOF in the new code** — Harmless (one additional no-op syscall on a reader already at EOF); no correctness impact.
- **`Error(limit)` allocation semantics** — Unchanged: the drain loop fills free space, then `ensure_capacity` errors when a full buffer has no terminator, matching the "can't tell if at EOF" behavior asserted by `buffer_limited_capacity1`.
- **Missing inline rationale for the drain loop** — A comment explaining *why* reads are drained (read-amortization for large `-A`) would aid maintainers, but that is knowledge-reviewer scope, not design.
- **`SliceByLine`/`MultiLine` paths** — Do not call `roll()`; only the streaming `ReadByLine` path is affected, consistent with the stdin-focused intent.

Relevant files: `/home/decaf/code/decaf-claude/competition/benchmark/repos/10/crates/searcher/src/line_buffer.rs` (fill drain loop 416–477, doc 389–405), `/home/decaf/code/decaf-claude/competition/benchmark/repos/10/crates/searcher/src/searcher/core.rs` (roll 185–213), `/home/decaf/code/decaf-claude/competition/benchmark/repos/10/crates/searcher/src/searcher/glue.rs` (ReadByLine 38–94), `/home/decaf/code/decaf-claude/competition/benchmark/repos/10/crates/searcher/src/searcher/mod.rs` (search_reader 727, max_context 213).
