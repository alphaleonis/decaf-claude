# subagent agent-af7dd0177ea7a1046

I have everything needed. Here is my type-design analysis.

---

## Type: `LineBuffer` (`crates/searcher/src/line_buffer.rs:293`)

### Invariants identified
From the field docs (`line_buffer.rs:299-322`) and `roll`/`fill` behavior, the type carries these invariants over `buf`, `pos`, `last_lineterm`, `end`:

- **Ordering:** `0 ≤ pos ≤ last_lineterm ≤ end ≤ buf.len()` (stated across the doc comments at :301, :306-310).
- **Region semantics:** `buffer()` = `buf[pos..last_lineterm]` is *complete, searchable* lines; `buf[last_lineterm..end]` is a *partial line*; `free_buffer()` = `buf[end..]` is *uninitialized free space*; `buf[pos..end]` is all live data.
- **`end` is the sole write cursor** — the amount of real data read equals `end` (post-roll), and every read must advance `end` by exactly the byte count written.
- **Post-roll normalization:** after `roll()`, `pos == 0` and `last_lineterm == end` (:483-484, asserted partially at :415).
- **Binary byte never observable to callers** (:57-63) — enforced by clamping `end`/`last_lineterm` at the detected offset (:444-452).

### How the change interacts with the invariants
The new inner loop (`line_buffer.rs:419-425`) is invariant-preserving and, notably, *depends on the type design being correct*:

- `free_buffer()` (`:367`) is recomputed as `&mut self.buf[self.end..]` on every access. Because `end` is the single source of truth and the slice is derived fresh each iteration, `self.end += readlen` between reads correctly advances the write cursor and the next `free_buffer()` reflects it. Holding a cached slice across iterations would both break this and be rejected by the borrow checker — so the "method returns a freshly-sliced `&mut [u8]`" design is exactly what makes the new loop safe.
- `oldend` is captured once (`:418`) and `newbytes = &mut self.buf[oldend..self.end]` (`:431`) spans the *entire* batch read by the loop, so binary detection and the `rfind_byte` line-terminator scan operate over all new bytes — same semantics as the old single-read version, just a larger batch.
- The EOF branch moved from "a single `read` returned 0" to "the batch produced zero bytes" (`newbytes.is_empty()`, `:432`). Semantics are equivalent: a mid-loop `read == 0` breaks (`:421-423`), the already-read bytes are processed, and EOF is reported on the *next* `fill` when the loop reads 0 immediately — preserving the amortized behavior. `ensure_capacity()` (`:417`, guaranteeing `free_buffer()` is non-empty, asserted at :525) means the loop body always runs at least once, matching the old "read exactly once" guarantee.

I traced the `BufferAllocation::Error` paths against the existing tests (`buffer_limited_capacity1/2/3`, `:710-780`): the loop fills until `free_buffer()` is empty, then re-enters the outer `loop` → `ensure_capacity()` errors at the limit, so the error semantics those tests pin are preserved.

**Verdict: the change respects the invariants.** No violation is introduced.

### Ratings
- **Encapsulation**: 7/10
  All fields are private; `LineBuffer` is not usable directly — callers go through `LineBufferReader` (`:208`, doc at :291-292), and `Config` is fixed at construction. The free/used regions are only reachable through `buffer()`/`free_buffer()` accessors. The weakness: every internal method can freely mutate the three raw `usize` cursors, so the invariants are only as safe as each method's hand-written arithmetic.

- **Invariant Expression**: 4/10
  The ordering and region invariants live *entirely in prose* (`:299-310`). `pos`, `last_lineterm`, `end` are three interchangeable bare `usize`s; nothing in the type says "these are monotonically ordered offsets into `buf`." A reader must reconstruct the `pos ≤ last_lineterm ≤ end` contract from comments to know the new loop is correct. This is the design weakness the PR leans on hardest: the whole correctness argument for the inner loop is "`end` is advanced by exactly `readlen` and stays ≤ `buf.len()` because `free_buffer()` bounds it" — true, but unexpressed in the types.

- **Invariant Usefulness**: 8/10
  The invariants are real and load-bearing: the partial-line region (`last_lineterm..end`) is what lets the searcher hand out only complete lines, and the "binary byte never observable" guarantee is a genuine API contract. These prevent concrete bugs (emitting incomplete lines, leaking a NUL past a `Quit`).

- **Invariant Enforcement**: 5/10
  Construction (`:121-131`) and `clear()` (`:335`) establish a valid all-zero state; `consume()` asserts its precondition (`:374`); `fill` asserts `pos == 0` after `roll` (`:415`); `ensure_capacity` asserts free space is non-empty (`:525`). But there is **no assertion of the core ordering invariant** (`pos ≤ last_lineterm ≤ end ≤ buf.len()`) after `fill` or `roll`. The new loop maintains it by careful manual bookkeeping only. A cheap `debug_assert!(self.pos <= self.last_lineterm && self.last_lineterm <= self.end && self.end <= self.buf.len())` at the end of `fill`/`roll` would have turned the entire correctness argument into a checked postcondition.

### On `free_buffer()`'s return type (`&mut [u8]` vs a wrapper)
Currently `free_buffer(&mut self) -> &mut [u8]` (`:367-369`); no `as_bytes_mut()` remains anywhere in the crate (grep-confirmed). I **cannot verify** the exact pre-PR signature from this checkout — the parent commit isn't present (the two PR commits are synthetic roots), so `git` shows the file as wholly new and I can't diff the old `fill` line. [Unverified] as to whether the return type literally changed vs. an `as_bytes_mut()` call simply being dropped.

From a type-design standpoint the current `&mut [u8]` is the right, minimal choice: `io::Read::read` consumes `&mut [u8]`, and the free region has *no invariant beyond* "it is `buf[end..]`" — which the method already enforces by slicing fresh from `end` on every call. A wrapper newtype would protect nothing here and would obstruct the loop (you'd need to unwrap it to call `read`). If anything, the mild wart is that `free_buffer()` is invoked twice per loop iteration (`:419` condition + `:420` read), each a bounds-checked reslice; harmless, and not worth a type change.

---

## Type: `Config` — the `before_context` / `after_context` / `max_context()` set (`crates/searcher/src/searcher/mod.rs:151`)

### Invariants identified
- `before_context` (`:159`) and `after_context` (`:157`) are independent line counts, default `0` (`:192-193`), written only by the builder (`:399-417`); zeroed together when `passthru` is set (`:318-319`).
- `max_context()` = `cmp::max(before_context, after_context)` (`:213-215`) — a *derived, direction-agnostic* "is any context needed / how wide a window in the worst direction" quantity.

### The design weakness the PR exposes
This is the crux. The change at `core.rs:201` swaps `self.config.max_context()` for `self.config.before_context` inside `Core::roll` (`core.rs:185-213`). The bug it fixes is precisely a **type-design failure**: `before_context`, `after_context`, and `max_context()` are all bare `usize`, mutually substitutable at every call site, and the compiler cannot tell you when you've grabbed the wrong one.

`Core::roll` is the worst-case demonstration — it legitimately needs *two different* members in adjacent lines, and the type system offers zero help distinguishing them:

- **`core.rs:186`** — `if self.config.max_context() == 0` is the correct gate ("does *either* direction need context?"). It must be `max_context()`, because an after-context-only run (`-A`, `before_context == 0`) still has to enter the retention branch to preserve unvisited lines via `last_line_visited`.
- **`core.rs:198-202`** — `lines::preceding(buf, line_term, self.config.before_context)` must be `before_context`, because `preceding()` (`lines.rs:157`) walks *backward* N lines; only *before*-context needs preceding lines retained. After-context lines are *following* lines, retained through `last_line_visited` (`core.rs:204`), not through this computation.

Using `max_context()` here (the original code) over-retained `max(before, after)` preceding lines. With a large `-A` and no `-B`, that pulled a huge preceding window into the retained region on every roll, which the buffer then re-scanned — the exponential-looking slowdown the commit fixes. I confirmed the direction: `preceding()` returns a *smaller* offset for a *larger* count (`lines.rs:181-194`), so `max_context() ≥ before_context` ⟹ the old `context_start` was ≤ the new one ⟹ the fix now retains *fewer* bytes. Correct and safe.

The point for type design: **nothing at the call site makes before-vs-after-vs-max legible or checkable.** All three are `usize`; the intended one is encoded only in the identifier and, now, the explanatory comment the PR added (`core.rs:192-197`). A newtype wouldn't help distinguish before from after (both would be the same wrapper), so the leverage here is naming/encapsulation, not a stronger type. The mistake sat latent because the two values coincide whenever `before_context == after_context` (the common `-C`/symmetric case) — the design let a wrong-member bug hide behind a frequently-true coincidence.

### Ratings
- **Encapsulation**: 8/10
  Fields are private, written only by the builder, read through methods; `Config` is documented as write-once-by-builder (`:148-150`). Clean.

- **Invariant Expression**: 3/10
  Three semantically distinct line-count quantities share one type and are interchangeable everywhere. The critical distinction — "preceding-line retention must use `before_context`; the any-context gate must use `max_context()`" — is expressed only in a comment added by this very PR (`core.rs:192-197`), i.e. it had *no* expression before the bug forced one. `max_context()`'s name doesn't convey "direction-agnostic; do not use where a specific direction is meant."

- **Invariant Usefulness**: 6/10
  The underlying values are genuinely useful, and `max_context()` is a real convenience for the "any context at all?" question (used correctly at `core.rs:186` and `:403`). But as an abstraction it actively invites the before/after/max mix-up, so its safety value is low even though the numbers it produces are right.

- **Invariant Enforcement**: 3/10
  There is no mechanism preventing the wrong member from being used — both spellings compile and the wrong one merely runs slower (or, in a different call, would return wrong output). The defect persisted precisely because nothing enforced the distinction; only a hand-review or a performance report catches it.

### Recommendation (scoped, non-over-engineered)
Don't introduce newtypes — they can't separate before from after and would add friction across the builder. Instead, make the intent enforceable-by-reading at the one place both are needed:

- Move the roll-retention policy into a single named `Config` (or `Core`) method — e.g. a `Config::preceding_context()`/`retained_lines()` that returns `before_context` with a doc comment stating *why* it is not `max_context()` — so `Core::roll` calls one intention-revealing method instead of independently choosing a raw field. That localizes the before-vs-max decision to one documented spot rather than leaving it as an unguarded field pick at the call site.
- At minimum, add a doc line to `max_context()` (`mod.rs:213`) stating it is only for "is any context needed / worst-direction window size" and must not be used where a *specific* direction is required. The PR's new comment at `core.rs:192-197` is good; hoisting that guidance onto the method definition is where future call sites will actually see it.

---

## Bottom line
The existing designs made the two changes **safe in practice but under-guarded in principle.**

- `LineBuffer`'s change is correct and its `free_buffer()`-returns-fresh-`&mut [u8]` design is what makes the new inner read loop sound — but the invariants it relies on (`pos ≤ last_lineterm ≤ end ≤ len`) live only in comments, with no postcondition assertion. Expression (4) and enforcement (5) are the soft spots; a one-line `debug_assert!` after `fill`/`roll` would close most of the gap.
- `Config`'s before/after/max trio is the design that *caused* the bug this PR fixes: three interchangeable `usize`s with the correct choice knowable only by name. The fix is right, but the type still can't stop the next call site from reaching for `max_context()` where `before_context` is meant. Expression (3) and enforcement (3) are genuinely weak here, and the fix is naming/encapsulation, not a heavier type.

Relevant files: `/home/decaf/code/decaf-claude/competition/benchmark/repos/10/crates/searcher/src/line_buffer.rs` (fields :293-323, `buffer` :361, `free_buffer` :367, `fill` loop :419-437, `roll` :485, `ensure_capacity` :504), `/home/decaf/code/decaf-claude/competition/benchmark/repos/10/crates/searcher/src/searcher/core.rs` (`Core::roll` :185-213, changed line :201, fast-path gate :403), and `/home/decaf/code/decaf-claude/competition/benchmark/repos/10/crates/searcher/src/searcher/mod.rs` (`Config` :151-185, `max_context` :213-215).
