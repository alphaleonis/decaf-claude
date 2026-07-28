# subagent agent-a6e397cebc1ddaf50

I have enough to complete the review. Let me consolidate my analysis.

Key facts I verified from the code:
- The test reader is always `haystack.as_bytes()` — a `&[u8]` (testutil.rs:696) — whose `Read::read` fills the destination buffer in a single call whenever data remains. It never returns short reads.
- `binary3`/`binary4` use `before_context == after_context == 0`, so `max_context() == 0`, which routes `core.rs roll()` through the unchanged `buf.len()` branch (core.rs:186-187), not the changed branch (core.rs:198-205).
- Max `after_context` anywhere in the searcher unit tests is 3 (glue.rs:1231), and in integration tests `-A` maxes at 2 (tests/regression.rs:1024), all on tiny inputs. Nothing exceeds the 64 KB buffer capacity.
- The binary offset assertions (262153 / 262149) are unchanged; only the byte counts moved 262146 → 262142.

Here is my report.

---

## Test Review: PR #3185 test changes (`crates/searcher/src/searcher/glue.rs`)

### Summary
| Severity | Count |
|----------|-------|
| CRITICAL | 0     |
| HIGH     | 1     |
| MEDIUM   | 1     |
| LOW      | 0     |

### Assessment of the two updated assertions (`glue.rs:740`, `glue.rs:774`) — NOT a false positive

The task's first question: are `byte count:262146 → 262142` still meaningful, or were they mechanically bumped to green?

Conclusion: **they remain meaningful assertions; this is not a bug-encoding change.**

- The load-bearing property of `binary3`/`binary4` is *binary detection at the correct offset*. That is asserted by `binary offset:262153` / `binary offset:262149`, and **both are unchanged**. The `\x00` in `a\x00a\n` sits at absolute offset 262153 (`2 + 4·65536 + 2 + 4 + 1`), and 262149 in `binary4`. Those assertions still pin binary detection to the exact right byte.
- The `byte count` is a secondary *characterization* value: how many bytes the incremental (line-buffer) reader consumed before the binary-quit terminated the search. The comment at `glue.rs:736-739` already documents why it is strictly less than the slice reader's 262153 ("detect binary in the current buffer before searching it").
- The new value 262142 is a clean line boundary — it is the start offset of the *last* `zzz\n` line inside the 65536-line block (`2 + 4·65535 = 262142`); the old 262146 was the start of the `a\n` immediately after the block. The difference is exactly one 4-byte line. A shift of one line in a read-amortization characterization value, with the semantic binary offset held constant, is the signature of a legitimate behavior-tracking update, not a masked regression. [Inference — I could not hand-derive 262142 from first principles for a `&[u8]` reader; see Probe Request #1, which exists precisely to confirm the assertion still guards the fill change.]

One caveat worth recording: the `byte count` portion of these assertions is a brittle whitebox value coupled to internal buffering mechanics. That brittleness is **pre-existing** (the assertion was equally brittle at 262146) and is not introduced by this PR, so I am not filing it as a defect.

---

### HIGH Issues

#### 1. No regression test for the `roll()` `before_context`/`max_context` change — large `-A/--after-context` across a buffer roll — `glue.rs` (test module, no test added)

**Problem:** The headline production fix (`core.rs:198-205`, `roll()` now preserves `before_context` preceding lines instead of `max_context()`) is the change that actually fixes the reported exponential slowdown (#3184) and, more importantly, changes *which bytes are retained across a buffer roll*. That is directly observable behavior (before/after-context line output), yet **no test exercises it**:

- `binary3`/`binary4` run `before_context = after_context = 0`, so `max_context() == 0` routes through the *unchanged* `roll()` branch (`core.rs:186-187`). They do not touch the modified branch at all.
- The largest `after_context` in the entire searcher unit suite is 3 (`glue.rs:1231`), on SHERLOCK-sized inputs — orders of magnitude below the 64 KB buffer capacity, so the buffer never grows and never rolls with meaningful context. Integration tests top out at `-A2` (`tests/regression.rs:1024`).

**Failure scenario:** A future change to context retention (or a subtle off-by-one in `lines::preceding(buf, term, before_context)`) that drops, duplicates, or misorders after-context lines when a match's after-context window spans a buffer roll with a large `-A` on a stream would produce no failing test. The maintainer describes this as a "crazy subtle bug"; the fix ships with zero guarding assertions.

**Confidence:** 75

**Pre-existing:** no (this is a coverage gap for behavior this changeset introduces)

**Suggested Fix:** Add a `search_reader` test with a haystack larger than `DEFAULT_BUFFER_CAPACITY`, a single match early in the stream, and an `after_context` large enough that the after-context window spans at least one buffer roll (e.g. a few thousand lines), asserting the full, exact context output. A companion large-`before_context` case guards the retained-context side of the branch.

---

### MEDIUM Issues

#### 2. No test exercises the `fill()` multi-read drain / a reader returning <64 KB per `read()` — `glue.rs` / `line_buffer.rs` (no test added)

**Problem:** The other production change (`line_buffer.rs:419-425`) wraps `read()` in an inner `while !self.free_buffer().is_empty()` loop so that binary detection (`:442-452`) and the last-line-terminator scan (`:470`) operate on the *combined* result of several reads. The entire point of the fix is the case where a single `read()` returns fewer bytes than the free buffer (the observed stdin behavior). **No test drives such a reader.** Every reader path uses `haystack.as_bytes()` (`testutil.rs:696`), and `<&[u8] as Read>::read` fills the destination in one call — so the inner loop always executes exactly one iteration, and binary detection is never exercised across a read boundary within a single `fill()`.

**Failure scenario:** A stream whose `read()` returns short chunks with a NUL landing in the *second* chunk of one `fill()` (or a line terminator only in a later chunk) could regress the computed `binary_byte_offset` or `last_lineterm` with no failing test. This is the exact interaction the PR targets, and it is untested. (Partly mitigated: `binary3`/`binary4` structurally exercise the `fill()` code path via `&[u8]`, so a gross breakage would likely move their byte counts — but the multi-read-per-fill behavior itself is uncovered.)

**Confidence:** 75

**Pre-existing:** no

**Suggested Fix:** Add a `Read` wrapper that caps each `read()` at, say, 17 or 8192 bytes and drive `binary3`/`binary4`-style inputs (plus a large-`-A` input) through it, asserting identical output to the `&[u8]` path. This is the only way to cover the amortized-read loop and cross-read binary detection.

---

### Probe Requests

Never run these myself — nominated for the orchestrator to run in isolation.

#### 1. `binary3` + `binary4` in `crates/searcher/src/searcher/glue.rs`
**Remove:** In `crates/searcher/src/line_buffer.rs` `fill()`, replace the inner loop at lines 419-425 (`while !self.free_buffer().is_empty() { let readlen = rdr.read(self.free_buffer())?; if readlen == 0 { break; } self.end += readlen; }`) with a single read: `self.end += rdr.read(self.free_buffer())?;`
**Expect:** If the updated `byte count:262142` genuinely reflects the multi-read drain, `binary3`/`binary4` should FAIL and report `byte count:262146`. If they still PASS with 262142, the assertions do **not** actually distinguish the new `fill()` behavior for the `&[u8]` reader — i.e., the value tracks something other than the drain change, and the two updated expectations are not a guard of this PR's production change.
**Relates to:** confidence check on whether the two updated assertions are meaningful guards (see Assessment section).

#### 2. Full searcher unit suite (`cargo test -p grep-searcher`)
**Remove:** In `crates/searcher/src/searcher/core.rs` line 201, revert `self.config.before_context` back to `self.config.max_context()`.
**Expect:** The suite STILL passes with no failing test, demonstrating that no existing test guards the `roll()` `before_context` change.
**Relates to:** Finding #1 (substantiates the coverage gap).

---

### Recommendations

1. Do not treat the two `glue.rs` byte-count edits as a defect — the semantically important binary-offset assertions are intact, and the edits faithfully track new behavior. Confirm via Probe #1 that they still guard the fill change.
2. Add the large-`-A`-across-a-roll test (Finding #1) — this is the single most valuable missing test; it guards the actual `#3184` fix, whose regression would otherwise be silent.
3. Add a short-read `Read` wrapper and route the binary/large-`-A` cases through it (Finding #2) to cover the amortized-read loop and cross-read binary detection.
