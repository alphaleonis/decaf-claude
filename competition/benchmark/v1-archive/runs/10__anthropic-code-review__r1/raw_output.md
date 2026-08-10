I have everything needed. Here's the full result. Per your instruction, **nothing was posted to GitHub** and `--comment` was not used — this is terminal output only.

---

## Process summary

- **Working dir** is a clone of `BurntSushi/ripgrep`; PR #3185 = "fix slow searching of `stdin` with large values of `-A/--after-context`" (state: **MERGED**, author BurntSushi).
- **CLAUDE.md discovery:** no `CLAUDE.md` or `AGENTS.md` files exist anywhere in the repo, so the CLAUDE.md-adherence pass had nothing to check.
- **PR touches:** `crates/searcher/src/line_buffer.rs`, `crates/searcher/src/searcher/core.rs`, `crates/searcher/src/searcher/glue.rs`, `CHANGELOG.md`.
- **5 review passes** ran (bug scan, git-history, prior-PRs, code-comments, CLAUDE.md-adherence). Four found nothing actionable; **two independently converged on one strong finding** (git-history + prior-PR passes). One finding cleared the 80-confidence gate — it scored **100/100**.

## Finding (1 issue, confidence 100)

**The batched read loop in `LineBuffer::fill()` breaks `--line-buffered` / streaming responsiveness.**

This PR wraps the single `rdr.read(...)` call in an inner `while !self.free_buffer().is_empty()` loop, so `fill()` now keeps reading until the buffer is completely full or EOF — instead of returning after one successful read. On a slow/interactive stream (e.g. `journalctl -f | rg foo --line-buffered`), a match already in the buffer can't be flushed until the buffer eventually fills or the pipe closes.

**file:line** — `crates/searcher/src/line_buffer.rs:419-424` (the inner `while` read loop)

**Why it's a real bug (not speculation — verified against upstream history):**
- The `line_buffer.rs` half of this PR is upstream commit `8bf6f0a2`.
- Issue [#3194](https://github.com/BurntSushi/ripgrep/issues/3194) ("Line buffering appears broken in 15.0.0") reported the breakage; BurntSushi `git bisect`-ed it straight to this commit. Duplicate: [#3199](https://github.com/BurntSushi/ripgrep/issues/3199).
- Five days after merge, commit `d47663b1` / PR [#3195](https://github.com/BurntSushi/ripgrep/pull/3195) ("searcher: fix regression with `--line-buffered` flag") **reverts exactly this inner loop**, with the maintainer's own words: *"in retrospect, this change is clearly contrary to how `--line-buffered` works. We specifically do not want to wait around until the buffer is full."*
- The **`core.rs` half** (`before_context` instead of `max_context()` for the `lines::preceding` call) was **not** reverted and is sound — kept as-is because it alone fixes the motivating issue #3184. Flag only the `line_buffer.rs` hunk.

---

Below is the exact comment I **would** have posted (rendered here only — not sent):

---

### Code review

Found 1 issue:

1. The new batched read loop in `LineBuffer::fill()` keeps calling `read()` until the buffer is full or EOF, instead of returning after one successful read. This defeats `--line-buffered`/streaming: on a slow or interactive stream (e.g. `journalctl -f | rg foo --line-buffered`), matches already in the buffer can't be flushed until the buffer fills or the pipe closes. The `core.rs` (`before_context` vs `max_context()`) half is fine — this is only about the `line_buffer.rs` read loop. (bug — later reverted upstream in [#3195](https://github.com/BurntSushi/ripgrep/pull/3195) after regression reports [#3194](https://github.com/BurntSushi/ripgrep/issues/3194)/[#3199](https://github.com/BurntSushi/ripgrep/issues/3199))

https://github.com/BurntSushi/ripgrep/blob/8bf6f0a2a8fd4d0786561b2901f2b1443ff2d8d4/crates/searcher/src/line_buffer.rs#L417-L426

🤖 Generated with [Claude Code](https://claude.ai/code)

<sub>- If this code review was useful, please react with 👍. Otherwise, react with 👎.</sub>

---

**Note on eligibility:** the skill would normally halt here because the PR is already merged (and, indeed, this exact issue was caught and reverted upstream). I proceeded only because you explicitly asked for the findings printed to the terminal with no posting. This finding is real and historically confirmed, but it's moot for the live repository — the offending hunk no longer exists on `master`.
