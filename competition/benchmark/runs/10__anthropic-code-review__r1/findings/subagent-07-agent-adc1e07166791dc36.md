# subagent agent-adc1e07166791dc36

I have completed my system model extraction and design evaluation. Here is my report.

## System Model

The changeset touches ripgrep's streaming search pipeline in `grep-searcher`:

- **`LineBuffer::fill`** (line_buffer.rs) — refills the buffer from an `io::Read`. Now wraps `read` in an inner loop (`while !free_buffer().is_empty()`) that reads until the free buffer is full or EOF before doing binary detection / line-terminator scanning and returning.
- **`Core::roll`** (core.rs) — decides how many leading bytes to drop when rolling the buffer between fills, via `consumed = max(context_start, last_line_visited)`. The change reduces the `lines::preceding` lookback count from `max_context()` (`max(before,after)`) to `before_context`.
- **Contract boundary**: `SinkFinish::byte_count` ("total number of bytes searched") is the public observable affected by binary-detection timing.

Roll's correctness for the after-context case now rests entirely on the invariant that unemitted after-context always lies at byte offsets `>= last_line_visited` (so `max(context_start, last_line_visited)` never drops it). `after_context_left` (core.rs:33) is separate state; `ensure_capacity` guarantees non-empty free space via the assert at line_buffer.rs:525.

## Findings

```json
[
  {
    "file": "crates/searcher/src/searcher/core.rs",
    "line": 204,
    "severity": "Medium",
    "category": "design",
    "issue": "[EVOLUTION_READINESS] Reducing the roll lookback from max_context() to before_context makes buffer-roll correctness depend on an implicit, unguarded invariant: that unemitted after-context always lies at offsets >= last_line_visited. `consumed = max(context_start, last_line_visited)` now preserves pending after-context ONLY because last_line_visited is a lower bound on 'bytes still needed'. The previous max_context() lookback kept max(before,after) trailing lines unconditionally, which masked any divergence between after-context bookkeeping and last_line_visited. The added comment explains the perf motivation (skip costly preceding() for large N) but does not state the safety invariant this optimization now relies on.",
    "fix": "Document the invariant explicitly at the roll site (unemitted after-context is always beyond last_line_visited, therefore never dropped by max(context_start, last_line_visited)) and add a debug_assert coupling it to after-context state (e.g. that when after_context_left > 0 the retained tail starts at last_line_visited), so a future edit that advances last_line_visited past a line whose after-context is still pending fails loudly instead of silently dropping across-boundary after-context lines.",
    "confidence": 50,
    "pre_existing": false
  },
  {
    "file": "crates/searcher/src/line_buffer.rs",
    "line": 419,
    "severity": "Medium",
    "category": "design",
    "issue": "[API_CONTRACT] The new inner read-until-full loop changes fill's effective behavior from 'read and return once a usable line is available' to 'block until the free buffer is full or EOF, then return'. For a blocking/interactive/slow reader (pipe, tty, socket, tail -f style), fill now withholds all data until a full buffer accumulates (DEFAULT 64KB, and substantially larger when -A/--after-context grows buffer capacity), where previously it returned promptly after the first read that yielded a line terminator. This is an undocumented change to the latency/availability semantics of an io::Read-consuming API. The fill doc comment (~389-405) still only describes EOF/return semantics and never mentions the fill-until-full buffering, so a grep-searcher consumer feeding a streaming reader gets delayed results with no contract to warn them.",
    "fix": "Document in the fill doc comment that it now reads until the free buffer is full or EOF (results are only surfaced per buffer-full boundary, whose size scales with context settings), so consumers on streaming/interactive readers understand the buffering/latency behavior. If low-latency streaming is a supported use case, expose it as a deliberate, documented mode rather than an implicit consequence of the perf fix.",
    "confidence": 50,
    "pre_existing": false
  }
]
```

## Considered But Not Flagged

- **`byte_count` change 262146 → 262142 (angle 3, glue.rs:740,774)**: Not flagged. `SinkFinish::byte_count` is documented as "the total number of bytes searched" (sink.rs:346). Because the fuller buffer lets binary detection truncate at the binary byte before searching, fewer bytes genuinely are searched — the value still satisfies its documented meaning. This count near binary data is already explicitly mode-dependent and unstable (the same tests assert line-buffered=262142 vs slice=262153, an 11-byte pre-existing divergence the comments call out). Consumers therefore already cannot treat exact byte_count as a cross-mode contract when binary data is present, and the 4-byte shift is a benign, arguably-more-correct implementation-detail move, not a contract violation.

- **Inner-fill-loop resilience to zero-length `free_buffer()` (angle 4, line_buffer.rs:416-425)**: Not flagged. `ensure_capacity()` either grows the buffer and asserts non-empty free space (line 525) or returns `Err` at the allocation limit (line 517). Even if a future edit made it return `Ok(())` with zero free space, the loop degrades gracefully: `while !free_buffer().is_empty()` skips the read, `newbytes` is empty, and the `newbytes.is_empty()` branch (line 432) returns as if at EOF — no infinite loop. The coupling to the post-condition is guarded by the existing assert, so evolution readiness here is adequate.

- **Reader over-consumption past a binary byte under `Quit` detection**: Not flagged. The inner loop may read past the binary byte before `find_byte` truncates, but the reader is consumed either way once the search stops; not observable and not a design concern.

- **fill doc comment "If EOF is reached... false; otherwise true" (angle 1, return semantics)**: Not a contradiction. The return/EOF semantics remain accurate under the new implementation; the gap is the missing documentation of blocking-until-full behavior, folded into the API_CONTRACT finding above rather than reported as a separate doc/code mismatch.

Both flagged findings are introduced by this PR and are design/robustness observations, not correctness defects — the current code is correct and tests pass; the concern is the removal of the conservative `max_context` safety margin (finding 1) and an undocumented latency-contract shift (finding 2). Per the anchor-50 confidence gate, both are reported for consolidation but neither is high-confidence.
