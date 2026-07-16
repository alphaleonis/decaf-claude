# subagent agent-afffff54456b87e60

I have verified both fix mechanisms against the issue, confirmed the streaming/binary path applies, and validated the supporting definitions. No probes needed (pre-flight gate already PASS). Here is my report.

---

```json
[]
```

No spec-compliance findings. The changeset faithfully and completely addresses the symptom reported in issue #3184, and stays strictly in scope.

## Spec provenance

Source: **linked** (GitHub issue #3184, "Fixes #3184"). Full-strength review. This is a **performance Bug**, not a functional contract — findings are framed as coverage of the reported symptom (superlinear slowdown with large `-A` on a stream), and I did not invent functional requirements the issue does not state.

## Requirement Coverage Matrix

| Req | Description (expected behavior from #3184) | Status | Evidence |
|-----|--------------------------------------------|--------|----------|
| R1 | Runtime should be roughly **invariant to N** (the `-A` value) when searching a stream, not superlinear | **Covered** | Two independent fixes, both on the streaming path. (a) `line_buffer.rs:416-425` — inner `while !self.free_buffer().is_empty()` read loop packs the entire (context-sized) free buffer per `fill()` instead of one ~64K `read`, amortizing the stdin ≤64K reads and cutting the number of rolls. (b) `core.rs:198-202` — `lines::preceding(...)` now passes `before_context` instead of `max_context()`; with `preceding` cost ∝ count (`lines.rs:157-159` backward line scan), the O(after_context) backward scan per roll is eliminated when `before_context == 0` (the `-A`-only case). Commit `d4b77a8` benchmarks show ~2.0s flat from `-A999` through `-A999999`. |
| R2 | "It should be faster" — remove the excessive slowdown | **Covered** | Same two changes; faster and flat across all N. |
| R3 | Fix must apply to the **binary-detection** scenario ("binary file matches" in the repro) | **Covered** | The stdin path is `ReadByLine` (`glue.rs:38-88`), which calls the changed `core.roll` (`glue.rs:63`) and the changed `LineBuffer::fill` (`glue.rs:65`) on every iteration before any binary quit (`glue.rs:76,90`; early-return in `line_buffer.rs:410-412`). Both perf fixes execute during the reads/rolls that precede the binary byte, so the pathological cost is removed for the binary case too. Golden `byte_count` in `binary3`/`binary4` shifted 262146→262142 (one `zzz\n` line) as a consequence of the new batched read boundary; the reported binary offsets (262153 / 262149) and match output (`0:a`) are unchanged, so behavior remains correct. `cargo test -p grep-searcher` = 77 passed. |
| R4 | Comparison: GNU grep stays ~5.5s flat across N (parity as an aspiration) | **Partial — acceptable** | ripgrep-on-stdin remains somewhat slower than file/mmap and slightly slower than GNU grep in absolute terms. This is **not** the issue's stated expected behavior (which is invariance to N, achieved), it is an explicitly-acknowledged residual ("I'm satisfied at this point"), and treating parity as a requirement would be inventing one the issue does not make. Documented below, not flagged. |

## Considered But Not Flagged

- **Residual stdin vs. file/GNU-grep gap (R4).** The `-A` superlinearity — the actual reported defect — is resolved; the remaining constant-factor slowness of stdin is a separate, author-acknowledged observation, not a spec requirement. Flagging it would invent a parity requirement the issue never states. No finding.
- **`binary3`/`binary4` golden `byte_count` 262146 → 262142.** A benign, expected consequence of the amortized read loop changing where the buffer boundary falls when binary data is detected. This is an internal `SinkFinish` "bytes searched" statistic, not user-visible match output; offsets and matches are unchanged and tests pass. Correct test maintenance, not a deviation. No finding.
- **`roll` change from `max_context()` to `before_context` — correctness.** Not a deviation: `preceding` computes the *before*-context that must be retained behind `pos` when rolling; after-context is forward-looking and sunk as lines are visited, so `max_context()` was over-conservative, not required. `max(context_start, last_line_visited)` still preserves the "previous line visited" needed for the context separator when `before_context == 0 && after_context > 0` (verified against the retained comment and the `preceding` count-0 semantics in `lines.rs:152-153`). Context-related tests pass. No finding.
- **Scope check.** The diff touches only searcher buffering (`line_buffer.rs`, `core.rs`), one consequent test golden update (`glue.rs`), and one CHANGELOG line (`CHANGELOG.md`, PERF #3184). No unrelated changes, no scope creep, nothing in the reported problem left unaddressed. No finding.

Relevant files: `/home/decaf/code/decaf-claude/competition/benchmark/repos/10/crates/searcher/src/line_buffer.rs` (fill loop 406-477), `/home/decaf/code/decaf-claude/competition/benchmark/repos/10/crates/searcher/src/searcher/core.rs` (roll 185-213), `/home/decaf/code/decaf-claude/competition/benchmark/repos/10/crates/searcher/src/searcher/glue.rs` (ReadByLine 38-94; binary3/binary4 723-788).
