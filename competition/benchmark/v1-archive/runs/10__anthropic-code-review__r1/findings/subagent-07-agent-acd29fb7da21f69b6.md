# subagent agent-acd29fb7da21f69b6

## PR #3185 Summary: Fix slow searching of stdin with large `-A/--after-context`

### Title & Purpose
**Title:** "fix slow searching of `stdin` with large values of `-A/--after-context`"

**Purpose:** Optimize ripgrep's performance when searching stdin with large after-context values by addressing two issues:
1. When reading stdin, `read()` calls often return only ~64K bytes, preventing amortization of system call overhead
2. When only `-A/--after-context` is set (no `-B/--before-context`), ripgrep was unnecessarily finding preceding lines in the buffer, an expensive operation for large context values

---

### Files Changed

| File | Change Size | Purpose |
|------|-------------|---------|
| `CHANGELOG.md` | +2 lines | Add performance improvement entry |
| `crates/searcher/src/line_buffer.rs` | ~40 lines modified | Restructure buffer reading loop |
| `crates/searcher/src/searcher/core.rs` | ~5 lines modified | Optimize context line detection |
| `crates/searcher/src/searcher/glue.rs` | 4 lines modified | Update test expectations |

---

### Functional Changes

**`line_buffer.rs` — Buffer reading optimization**
- Wraps the `read()` call in a `while` loop that continues reading until the free buffer is exhausted or EOF is reached
- Old flow: single `read()` → check if done → process
- New flow: multiple `read()` calls batched → then check if any data arrived → process
- Allows the buffer to accumulate data from multiple small `read()` calls before processing begins, amortizing I/O overhead
- Moves the empty-buffer check after attempting to fill the buffer, reducing syscall frequency

**`core.rs` — Avoid unnecessary line searching**
- Changes the `lines::preceding()` call from using `self.config.max_context()` (the maximum of before/after) to using only `self.config.before_context`
- Adds explanatory comment: the preceding-line search is only needed when before-context is set
- When `before_context == 0`, skips this potentially costly operation entirely
- Fixes the performance regression for `-A` (after-context only) searches

**`glue.rs` — Test data updates**
- Two test expectations have byte counts adjusted from `262146` to `262142` 
- Reflects the slight change in when binary detection occurs due to the restructured buffer reading

---

### Tests
No new tests added. Two existing test cases in `glue.rs` had their byte-count expectations updated to reflect the new behavior (lines affected by the binary detection timing shift).
