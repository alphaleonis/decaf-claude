# subagent agent-a345d4655d351484c

I have enough to complete the compliance analysis. Let me record my findings.

## Spec-compliance review: ripgrep PR #3185 (grep-searcher, `-A/--after-context` perf)

**Spec source**: `linked` — GitHub issue #3184, the bug this PR closes. This is a bug report treated as intent (not a formal PRD). Per instruction, severities are capped at **Medium** (thin-spec discipline). The linked spec unambiguously describes this changeset (slow `-A` on piped stdin), so I reviewed at full strength within that cap.

**Bottom line**: The implementation faithfully addresses both root causes the author named, stays scoped to the streaming-reader path where the bug lives, preserves `-B/--before-context`, and updates the affected binary-quit tests to match. I found **no spec gaps, deviations, or problematic scope creep at reportable confidence.**

```json
[]
```

### Requirement Coverage Matrix

| Req | Description | Type | Status | Evidence |
|-----|-------------|------|--------|----------|
| R1 | Search performance must not degrade as `-A` grows; comparable regardless of `-A` | functional/perf | Covered | Both fixes; author benchmarks show ~2.0s flat across `-A999`…`-A999999` (commit `d4b77a8` body) |
| R2 | Fix the reported source specifically (piped `stdin`) | functional | Covered | `line_buffer.rs` fill() and `core.rs` roll() are on the `LineBufferReader`/`ReadByLine` streaming path used for stdin (`glue.rs:40,63,65`) |
| R3 | Root cause 1 — amortize `read`: fill large buffers despite ≤64K stdin reads | constraint | Covered | Inner read-drain loop `while !self.free_buffer().is_empty() { rdr.read(...) }` — `line_buffer.rs:419-425`; EOF via `newbytes.is_empty()` at `432-437` |
| R4 | Root cause 2 — skip after-context preceding-scan when rolling | constraint | Covered | `lines::preceding(buf, term, self.config.before_context)` replaces `max_context()` — `core.rs:198-202` |
| R5 | Preserve `-B/--before-context` (still retain N preceding lines) | constraint | Covered | roll() still runs the else-branch and passes `before_context`; when `after_context ≤ before_context`, identical to prior `max_context()`. Preceding lines are only needed for `-B`; after-context needs forward lines protected by `last_line_visited` (`core.rs:204`). Context tests (`context_sherlock1-6`, `context_code1-3`) pass |
| R6 | Reported input is a binary file → early binary-quit path; fix must reach it | edge-case | Covered | `BinaryDetection::Quit` branch runs inside the amended fill() loop (`line_buffer.rs:442-452`); `binary3`/`binary4` (`glue.rs:723-788`) use `BinaryDetection::quit(0)` and their Read-path byte counts shifted `262146→262142`, proving the change reaches this path |
| R7 | Record the perf fix in CHANGELOG | format/doc | Covered | `CHANGELOG.md:11-12` PERF #3184 entry |

### Considered But Not Flagged

- **Scope spans all streaming readers, not just stdin (intentional, benign).** Both fixes live in shared streaming code: `line_buffer.rs` fill() and `core.rs` roll(), the latter called only from `ReadByLine::fill()` (`glue.rs:63`) — the `SliceByLine`/mmap path (`glue.rs:117-131`) is untouched. So file-with-`--no-mmap` and `-z` decompressed streams also benefit. This is not avoidable scope creep: the code cannot distinguish stdin from other streams here, and the author explicitly acknowledges and benchmarks the file case. mmap (the default for on-disk files) is correctly unaffected. Not a finding.

- **`-B/--before-context` retention semantics changed only in the redundant direction.** Previously roll() retained `max(before, after)` preceding lines; now `before_context`. This reduces retention only when `after_context > before_context`, and those extra preceding lines were never used for output (after-context is forward-looking). No `-B` output change; test suite passes. Not a deviation.

- **`--stats` "bytes searched" for early binary-quit drops by one line (4 bytes).** The `binary3`/`binary4` expectations moved `262146→262142` for the Read searcher; match output (`0:a`) and binary offset are unchanged. The spec is silent on byte-count accounting, no match is newly missed (the `a` at 262146 was already unreported by the Read searcher pre-change), and the new count accurately reflects bytes actually searched before quit. Incidental and correct — not a spec deviation.

- **Author verified against a text file, not the reporter's binary file (verification/test-coverage, not spec-compliance).** Both commit-message benchmarks use `bigger.txt` (searchable subtitle text with a real match), whereas the reporter's scenario is a binary file that emits "binary file matches". The unit tests `binary3`/`binary4` do exercise the binary-quit path and changed, and the same fill()/roll() code runs until binary detection triggers, so the fix should benefit the binary case identically — but there is no regression test reproducing the reporter's exact scenario (large `-A` on an early-quitting binary stream staying `-A`-invariant). Framing this as "the fix is incomplete for binary" would be speculative (anchor 25) — I have strong reason to believe it works. Framing it as "missing regression test" is **test-reviewer scope**, not mine. Noted, not flagged.

- **CHANGELOG link path nit (coherence scope).** `CHANGELOG.md:11` links `#3184` via `.../pull/3184`, but 3184 is the issue (the PR is 3185); GitHub redirects `/pull/N`→`/issues/N`, so it resolves. Documentation-accuracy nit, out of spec-compliance scope; below the reporting bar.

No `### Probe Requests` — the review required no destructive git operations (used `git show`/`grep`/`Read` only).
