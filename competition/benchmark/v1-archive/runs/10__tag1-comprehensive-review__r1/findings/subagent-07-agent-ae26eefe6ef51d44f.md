# subagent agent-ae26eefe6ef51d44f

I've now verified the key facts:

- `DEFAULT_BUFFER_CAPACITY = 64 KB`, which equals the stdin read-chunk ceiling. So in the default (no large-context) case, one 64K read fills the buffer and the new inner `while` loop exits after a single read — behavior is unchanged. The batched multi-read only engages when the buffer has grown past 64K (i.e., exactly the large `-A`/`-B` case the PR targets).
- Binary Quit offset (`binary_byte_offset = absolute_byte_offset + end`) reports the *first* binary byte's absolute position; `find_byte` returns the first occurrence whether scanning one chunk or a batched span, so the reported offset is invariant (the tests confirm: offsets 262153/262149 unchanged; only the internal "byte count" statistic shifts by 4, which the test comments already acknowledge as reader-granularity-dependent).
- Error-mid-fill leaves `end` advanced past un-scanned bytes, but a `fill()` error aborts the whole search and the buffer is discarded — the transient inconsistency is never re-observed.
- The `preceding(buf, term, before_context)` change is safe: after-context retention is guaranteed by `last_line_visited` (set to `range.end()` after each visited range at core.rs:550/580/611/641) and the `max(context_start, last_line_visited)` floor — the `preceding()` scan only ever governed *before*-context retention. Passing `after_context` there was pure over-retention, not a correctness requirement. The `max_context()==0` guard is unchanged, preserving the context-separator case.

Both scoped contracts (LineBuffer state machine invariants, `fill()`/`Core::roll()` API stability, downstream-sink observable behavior for finite inputs) are preserved. The only behavioral delta is latency for the niche large-context + live-stream combination, which is the PR's deliberate, accepted amortization tradeoff — not a defect. No Medium-or-higher architectural findings.

NONE
