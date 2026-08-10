# subagent agent-aaaa158259a8c99ac

## Summary

Fixes a performance bug in ripgrep's context-line handling that made large `-A/--after-context` values pathologically slow, especially when searching `stdin`. Two root causes are addressed: (1) `LineBuffer::fill` issued only one `read()` per loop iteration, which on Linux caps at ~64K for `stdin`, preventing the buffer from filling and defeating the amortization that large context buffers rely on; (2) `Core::roll` scanned back `max_context()` (before+after) preceding lines even when `before_context == 0`, doing unnecessary work that only `-B/--before-context` needs. Together these dropped `-A999999` search time from ~6.6s to ~2.0s in the author's benchmark. Verified directly against the local repo's two commits (`8c6595c`, `d4b77a8`).

**Type:** Performance fix (bug fix)
**Effort:** 2/5 — ~33 lines total across 4 files; two isolated, well-scoped logic changes plus matching test-constant updates and a changelog entry.

## Walkthrough

| File | Change | Summary |
|------|--------|---------|
| crates/searcher/src/line_buffer.rs | Modified | `fill()` now loops `read()` calls until the free buffer is full or EOF, instead of one `read()` per outer-loop pass — fixes stdin's ~64K read cap from starving buffer amortization |
| crates/searcher/src/searcher/core.rs | Modified | `Core::roll` passes `config.before_context` (not `max_context()`) to `lines::preceding()`, skipping the costly backward scan for preceding lines when only `-A` is set |
| crates/searcher/src/searcher/glue.rs | Modified | Updates two test expectations' byte-count constants (262146 → 262142) to match the new fill-loop behavior |
| CHANGELOG.md | Modified | Adds a Performance-improvements entry referencing #3184 for the `-A/--after-context` fix |

Note: the PR title/commit reference "Fixes #3184," but per the task framing #3184 is the *issue* ("Excessive slowdown with larger -A context windows?") and this change is PR #3185 — the CHANGELOG entry itself links to `pull/3184`, which looks like a mislabeled link (should likely point to the PR, not the issue). Flagging as an inconsistency rather than correcting it.
