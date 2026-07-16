# subagent agent-aaa71b70703f98044

## Sibling-Consistency Review — ripgrep `-A/--after-context` performance fix

### Sibling Census

**Read-loop idiom** (the changed `fill()` inner loop is one of exactly two places in the crate that manually drive an `io::Read` in a loop to amortize/fill a buffer):
- `crates/searcher/src/line_buffer.rs:416-437` — `LineBuffer::fill()` (the code under review)
- `crates/searcher/src/searcher/mod.rs:999-1027` — `Searcher::fill_multi_line_buffer_from_reader()`, the multi-line-mode sibling that does the same job ("fill an internal buffer from an arbitrary reader, growing it as needed, until EOF")

**`lines::preceding` call sites** (three total): `core.rs:198-202` (`roll`, under review), `core.rs:252-257` (`before_context_by_line`), and `lines.rs` itself (definition + tests). `before_context_by_line` was already using `self.config.before_context` prior to this diff.

**Golden byte-count literals**: `binary3`/`binary4` in `crates/searcher/src/searcher/glue.rs:724-788`, both built from `DEFAULT_BUFFER_CAPACITY` and asserting a Read-path `byte count` and a Slice-path `exp_slice`.

### Comparison Sweep

**1. Read loop vs. `mod.rs`'s read loop — EINTR handling diverges.**
The sibling loop explicitly treats `io::ErrorKind::Interrupted` as retryable:
```rust
// crates/searcher/src/searcher/mod.rs:1005-1011
let nread = match read_from.read(&mut buf[pos..]) {
    Ok(nread) => nread,
    Err(ref err) if err.kind() == io::ErrorKind::Interrupted => {
        continue;
    }
    Err(err) => return Err(S::Error::error_io(err)),
};
```
The new `fill()` loop instead propagates any error, including `Interrupted`, straight out via `?`:
```rust
// crates/searcher/src/line_buffer.rs:419-425
while !self.free_buffer().is_empty() {
    let readlen = rdr.read(self.free_buffer())?;
    if readlen == 0 {
        break;
    }
    self.end += readlen;
}
```
The pre-existing single-read version of `fill()` had this same gap, so it isn't strictly new — but the diff is exactly what turns this into a multi-`read()`-per-`fill()` loop (the amortization the PR is going for), which mechanically increases the number of syscalls made before control returns to the caller, and therefore the exposure window to a stray `EINTR` on Unix. This is the only other "read-until-buffer-full-or-EOF" loop in the crate, so corroboration is thin (one sibling, not two), which caps my confidence — flagging per the "divergence revealed by sibling comparison" allowance rather than as a standalone bug claim.

### Considered But Not Flagged

- **Dropped `.as_bytes_mut()`** (`line_buffer.rs:420`, was `rdr.read(self.free_buffer().as_bytes_mut())?`): `free_buffer()` already returns `&mut [u8]` (`line_buffer.rs:367-369`), and the sibling loop in `mod.rs:1005` passes a bare `&mut [u8]` (`&mut buf[pos..]`) to `.read()` with no `ByteSlice` conversion. Removing the call makes this line *more* consistent with the sibling idiom, not less — not a drift.
- **`roll()`: `max_context()` → `before_context`** (`core.rs:201`): the sibling `before_context_by_line` (`core.rs:252-257`) already computes its `lines::preceding` call using `self.config.before_context` (minus 1), never `max_context()`. This change makes `roll()` *more* consistent with that established sibling convention, not less.
- **Comment coherence in `roll()`** (`core.rs:188-197`): re-read against the changed code — the comment's claim ("we only need to find the N preceding lines based on before context... skip this step when before_context==0") still accurately describes the `before_context`-based call and the `before_context == 0` early-return branch above it. No stale identifier or contradicted claim.
- **Golden literal consistency** (`glue.rs:740`, `774`): both `binary3` and `binary4`'s `byte count` literals were updated in lockstep (262146→262142); the untouched `262146:a\n` position inside `exp_slice` in both tests correctly stays the same since it belongs to the unaffected slice-reader path. Repo-wide grep found no other occurrence of `262146`/`262142` left stale.
- **`DEFAULT_BUFFER_CAPACITY` usage in `glue.rs` tests**: haystack construction already references the constant symbolically (`glue.rs:4,120,169,644,663,683,727,762`); the expected-output numbers are hardcoded golden values, matching the established style of `binary1`/`binary2`'s hardcoded `byte count` strings — not a `CONS_LITERAL` violation.

```json
[
  {
    "file": "crates/searcher/src/line_buffer.rs",
    "line": 420,
    "severity": "Medium",
    "category": "design",
    "issue": "[CONS_SYMMETRY] New inner read loop propagates io::ErrorKind::Interrupted via `?` instead of retrying; the crate's only other read-until-full loop retries on Interrupted (crates/searcher/src/searcher/mod.rs:1005-1011)",
    "fix": "Match the mod.rs idiom: match on the read() result and `continue` when err.kind() == io::ErrorKind::Interrupted instead of using bare `?`.",
    "confidence": 50,
    "pre_existing": false
  }
]
```

Files read for this review (absolute paths):
- `/home/decaf/code/decaf-claude/competition/benchmark/repos/10/crates/searcher/src/line_buffer.rs`
- `/home/decaf/code/decaf-claude/competition/benchmark/repos/10/crates/searcher/src/searcher/core.rs`
- `/home/decaf/code/decaf-claude/competition/benchmark/repos/10/crates/searcher/src/searcher/mod.rs`
- `/home/decaf/code/decaf-claude/competition/benchmark/repos/10/crates/searcher/src/lines.rs`
- `/home/decaf/code/decaf-claude/competition/benchmark/repos/10/crates/searcher/src/searcher/glue.rs`

### Probe Requests
None — no probes needed; all comparisons were resolved by reading source directly.
