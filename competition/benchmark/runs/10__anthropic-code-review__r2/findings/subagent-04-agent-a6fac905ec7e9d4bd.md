# subagent agent-a6fac905ec7e9d4bd

## Summary

I traced the history of PR #3185 and its changed files and found a confirmed, real-world regression directly caused by this PR.

**Key finding: the `line_buffer.rs` read-loop change breaks `--line-buffered` streaming.**

- PR body links to `Fixes #3184` ("Excessive slowdown with larger `-A` context windows?"), authored/fixed by the maintainer (BurntSushi) himself.
- The PR has two commits: (1) `8bf6f0a2`/local `8c6595c2` — puts `read()` in an inner loop in `LineBuffer::fill()` (`crates/searcher/src/line_buffer.rs:419-425`) that keeps calling `read()` until the buffer is completely full or EOF, to better amortize syscalls when reading `stdin`; (2) `146f78f7`/local `d4b77a8d` — changes `core.rs`'s context-start computation to use `self.config.before_context` instead of `self.config.max_context()` (`crates/searcher/src/searcher/core.rs:~197`), avoiding unnecessary backward scanning when only `-A` is set.
- Searching subsequent issues turned up **ripgrep#3194 "Line buffering appears broken in 15.0.0"** (https://github.com/BurntSushi/ripgrep/issues/3194) and duplicate **ripgrep#3199** (https://github.com/BurntSushi/ripgrep/issues/3199), both filed shortly after 15.0.0 shipped. BurntSushi bisected #3194 directly to commit `8c6595c215d1e24bed5b7b86e2b18f3c871439ef` — the *first* commit of this very PR.
- The follow-up fix commit (https://github.com/BurntSushi/ripgrep/commit/d47663b1b4, "searcher: fix regression with `--line-buffered` flag") reverts **only** the `line_buffer.rs` read-loop change, explicitly stating: *"this change is clearly contrary to how `--line-buffered` works. We specifically do not want to wait around until the buffer is full. We want to read what we can, search it and move on."* It keeps the `core.rs` `before_context` change, since that alone was sufficient to fix #3184.
- I confirmed the local checked-out repo (`/home/decaf/code/decaf-claude/competition/benchmark/repos/10`) is at HEAD `d4b77a8d` — exactly the post-merge, pre-revert state of PR #3185 — so this regression is present in the code as currently reviewed.

I reported this single finding via `ReportFindings` (file `crates/searcher/src/line_buffer.rs`, line 419) with the full evidence trail and links. No other prior-PR caveats on `core.rs`'s context handling turned up (that part of the fix was never touched again upstream), and the `glue.rs` changes are just test-expectation updates (byte counts 262146→262142) tracking the buffer-filling behavior change, which reverts back to 262146 alongside the `line_buffer.rs` revert.
