# subagent agent-afae6437d9aaf0202

```json
[
  {
    "file": "CHANGELOG.md",
    "line": 11,
    "severity": "Medium",
    "category": "other",
    "issue": "[CONS_LITERAL] New entry `[PERF #3184](https://github.com/BurntSushi/ripgrep/pull/3184)` pairs an ISSUE number (#3184, \"Excessive slowdown with larger -A context windows?\") with a `/pull/` URL. Every sibling entry pairs the cited number with the URL type that matches what that number actually is: `[PERF #2111](.../issues/2111)` (CHANGELOG.md:7, issue number + /issues/) and `[PERF #2865](.../pull/2865)` (CHANGELOG.md:9, PR number + /pull/); the same self-consistent pairing holds across dozens of BUG/FEATURE entries in the file (e.g. line 22 `[BUG #2933](.../pull/2933)`, line 39 `[BUG #3100](.../pull/3100)`). The actual fix landed via PR #3185, so `/pull/3184` does not point at a real pull request.",
    "fix": "Cite the PR that made the change, matching the URL type: `[PERF #3185](https://github.com/BurntSushi/ripgrep/pull/3185)` — or, if the issue is meant to be referenced instead, keep #3184 but link `/issues/3184` per the line-7 convention.",
    "confidence": 100,
    "pre_existing": false
  },
  {
    "file": "crates/searcher/src/searcher/core.rs",
    "line": 196,
    "severity": "Medium",
    "category": "naming",
    "issue": "[CONS_COMMENT] New comment says \"We can skip this (potentially costly, for large values of N) step when before_context==0\" (core.rs:195-197), but the code it sits on (core.rs:198-202, the unconditional call `lines::preceding(buf, self.config.line_term.as_byte(), self.config.before_context)`) has no `before_context == 0` branch that skips anything — that call always executes inside this `else` arm, whose only guard is `self.config.max_context() == 0` (core.rs:186). When before_context==0 but after_context>0, the call still runs (with count=0, doing one `rfind_byte` scan per lines.rs:181-196), it is not skipped.",
    "fix": "Reword to describe what actually happens, e.g. \"this call is O(1) rather than O(N) when before_context==0, since lines::preceding only needs to find the current line's start\" — or restructure the code to add the described guard so the comment is accurate.",
    "confidence": 100,
    "pre_existing": false
  },
  {
    "file": "crates/searcher/src/searcher/core.rs",
    "line": 203,
    "severity": "Low",
    "category": "design",
    "issue": "[CONS_HELPER] The `else` arm ends with a redundant same-name rebind-then-return: `let consumed = std::cmp::max(context_start, self.last_line_visited); consumed` (core.rs:203-205), shadowing the outer `consumed` binding from line 186. The sibling `if` arm of the very same statement returns its value directly as a tail expression with no rebind (`buf.len()`, core.rs:187), and no other function in this file uses a `let X = ...; X` tail pattern — e.g. `sink_before_context` computes `keepgoing` then ends with a bare `Ok(true)` (core.rs:582), not `let result = Ok(true); result`.",
    "fix": "Drop the redundant binding: `std::cmp::max(context_start, self.last_line_visited)` as the tail expression, matching the `if` arm's direct-return style.",
    "confidence": 100,
    "pre_existing": true
  },
  {
    "file": "crates/searcher/src/line_buffer.rs",
    "line": 420,
    "severity": "Low",
    "category": "naming",
    "issue": "[CONS_NAMING] New inner read loop binds the result of `.read()` as `readlen` (`let readlen = rdr.read(self.free_buffer())?;`, line_buffer.rs:420). Every other manual read-loop in the workspace names this value `nread`: `crates/searcher/src/searcher/mod.rs:1005` (`let nread = match read_from.read(&mut buf[pos..]) {`, in the structurally identical `fill_multi_line_buffer_from_reader<R: io::Read>` loop) and `crates/cli/src/process.rs:260` (`let nread = stdout.read(buf)?;`).",
    "fix": "Rename `readlen` to `nread` to match the established variable name for a `.read()` return value.",
    "confidence": 100,
    "pre_existing": false
  }
]
```

## Considered But Not Flagged

- **EINTR handling in the new `fill` inner loop** (`line_buffer.rs:419-425`): the loop propagates any `io::Error` from `rdr.read(...)?` immediately, including `ErrorKind::Interrupted`, whereas `searcher/mod.rs:1005-1011` (a structurally identical `R: io::Read` manual-fill loop) explicitly retries on `Interrupted`. Investigated as a possible convention violation, but the census falls apart: `crates/cli/src/process.rs:254-267`, the next closest sibling (a custom `Read` impl wrapping a subprocess's stdout), does *not* retry on `Interrupted` either — it propagates `stdout.read(buf)?` transparently. With siblings disagreeing (mod.rs retries, process.rs doesn't), there's no single convention to cite; not reportable per the anchor-0 rule (siblings disagree among themselves).
- **glue.rs `binary3`/`binary4` byte-count updates** (262146 → 262142 at lines 740 and 774): confirmed both sibling tests were updated symmetrically, and both retain the unrelated `exp_slice` literal `262146` correctly (a different concept — a match line-offset, not a byte count). Grepped the whole file for `DEFAULT_BUFFER_CAPACITY`/`byte count:` occurrences; no other test uses this same magic literal, so there is no missed sibling assertion.
- **`core.rs::roll`'s switch from `self.config.max_context()` to `self.config.before_context`** in the `lines::preceding(...)` call (core.rs:201): this actually *improves* alignment with the sibling call in `before_context_by_line` (core.rs:252-256), which already passes `self.config.before_context` (minus one) to the same helper. Not a deviation — the change moves the code closer to the established sibling pattern.
- **`line_buffer.rs::fill`'s use of `free_buffer()`/`ensure_capacity()`**: both are pre-existing canonical helpers used correctly in the new loop; no hand-rolled alternative introduced.
- **`fill`'s doc comment** ("If EOF is reached, then `false` is returned...", line_buffer.rs:398-401): unmodified by this diff and not directly adjacent to the changed lines (it sits above unrelated binary-detection logic too); out of scope as pre-existing and not touched by the changeset.
