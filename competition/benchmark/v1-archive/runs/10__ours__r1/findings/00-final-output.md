Review complete. Working tree is clean (only the new `.decaf/` review artifact is untracked; no tracked source was modified).

✅ Review file: `.decaf/code-reviews/CODE_REVIEW_2026-07-16_16-26-45.md`

**Findings: 1 Critical, 0 High, 2 Medium, 1 Low, 1 Minor** → Verdict: ❌ NEEDS_CHANGES

**Headline:** PR #3185 bundles two independent fixes. The `core.rs` `roll()` change (use `before_context` instead of `max_context()`) is correct and is what actually fixes #3184. The `line_buffer.rs` inner read loop introduced a **Critical** regression — it withholds output until the buffer fills, breaking `--line-buffered` streaming (found independently by broad, rust, and quick reviewers; all 3 validators confirmed). I verified this against upstream ground truth: the author reverted exactly that hunk 5 days later in commit `d47663b1b454` ("fix regression with `--line-buffered` flag", Fixes #3194), keeping the `core.rs` half. Nothing was posted to the PR.
