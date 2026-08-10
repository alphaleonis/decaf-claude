Review complete. Tracked source is clean (both revert probes fully restored, 0 PROBE markers), and nothing was posted to PR #3185 — this was a local review-only run.

**Review file:** `.decaf/code-reviews/CODE_REVIEW_2026-07-16_17-08-53.md`

**Findings by severity:** 1 Critical, 0 High, 1 Medium, 0 Low, 5 Minor — **Verdict: NEEDS_CHANGES**

Key result: the PR bundles two independent changes. The `core.rs` `roll()` change (`before_context` instead of `max_context()`) is **correct** and is what actually fixes #3184 — verified safe by four independent reviewers. But the `line_buffer.rs` inner read-loop introduced a **Critical** regression: it withholds already-matched lines from streaming `stdin` until the 64 KB buffer fills, breaking `--line-buffered` (`tail -f`/`journalctl -f | rg`). I reproduced it at runtime (pre-fix emits immediately; merged build withholds) and confirmed via upstream history that it shipped in 15.0.0, was reported as issue #3194, and was fixed by follow-up PR #3195.
