# subagent agent-ab5cbe3cfefe6ed52

I have completed a thorough analysis. All 77 searcher tests pass, the change matches the real upstream ripgrep commit, and I've traced the correctness reasoning through `roll`, `preceding`, the separator logic, and passthru. Here is my review.

---

### Strengths

- **Correct, minimal, and well-scoped.** The change is a one-line functional edit (`max_context()` → `before_context`) plus an explanatory comment, confined to the single place it matters (`Core::roll` in `crates/searcher/src/searcher/core.rs:198-202`). It matches the actual upstream ripgrep fix (BurntSushi, follow-up to #3184) verbatim.
- **The guard was correctly left alone.** `roll` still branches on `if self.config.max_context() == 0` (core.rs:186), *not* `before_context == 0`. This is the subtle, load-bearing detail: with `before_context==0 && after_context>0` the code must still enter the `else` branch so that `preceding(buf, 0)` retains the last line as the reference point for the context separator. Had the author "simplified" the guard too, they would have broken the separator. They didn't.
- **The reasoning that after-context doesn't need `context_start` is sound.** `context_start` governs only how much *trailing* buffer is retained as before-context for a future boundary match. After-context is emitted forward and is driven by `last_line_visited` (which clamps `consumed = max(context_start, last_line_visited)`), not by `context_start`. So dropping `after_context` from this computation cannot drop lines that after-context still needs.
- **Output-preserving, provably.** The retained-tail is empty iff `last_line_visited == buf.len()`, and that condition is identical before and after the change (because `preceding(...)` always returns an offset `< buf.len()` for a non-empty buffer). So the separator's gap test (`is_gap = last_line_visited < start_of_line`, core.rs:650) yields the same result in both versions — no spurious or missing `--` separators, no changed `absolute_byte_offset`/line-number accounting (the consumed bytes are simply counted now-vs-later, netting the same totals).
- **Passthru is inert to this change.** `SearcherBuilder::build` forces `before_context = after_context = 0` under passthru (mod.rs:317-319), so `max_context() == 0` and `roll` never reaches the edited branch. Confirmed no interaction.
- **Good comment.** The added comment explains *why* (before-context is all that's needed; the walk-back is costly for large N) rather than narrating a change.

### Issues

#### Critical (Must Fix)
None.

#### Important (Should Fix)
None.

#### Minor (Nice to Have)

- **`core.rs:196-197` — comment says "skip this step when `before_context==0`", but it isn't literally skipped.** With `before_context==0`, `lines::preceding(buf, term, 0)` still runs; it just reduces to a single backward `rfind_byte` over the last line (O(one line)) instead of walking back N lines. The effect (removing the `-A`-proportional cost) is real, but "skip" slightly overstates it. Consider "…this becomes cheap (a single line lookback) when `before_context==0`." Purely wording; not blocking.

- **No regression test accompanies the fix (test-coverage gap).** The head commit adds no test. This is defensible — it's a performance fix, and performance is benchmark-, not unit-testable, and the upstream commit likewise added none. Behavior *is* guarded indirectly: `SearcherTester` re-runs every context case a second time under `heap_limit(minimal_heap_limit)` (testutil.rs:547-557), which forces buffer rolls, and it cross-checks the rolling reader's output byte-for-byte against the non-rolling slice reader. The after-context-only cases that this change most affects (e.g. `context_sherlock6`'s `.after_context(3)` sub-case with `before_context==0`, glue.rs:1249) are among those cross-validated, and all 77 tests pass. The residual gap is that SHERLOCK is only 6 lines, so the "match, exhaust after-context, then many trailing non-matching lines, then a buffer boundary, then another match" scenario isn't hit with a *large* N. A small unit test asserting output invariance for `before_context=0` + large `after_context` across a forced roll would close that gap cheaply. Nice-to-have, not required to merge.

### Recommendations

- Optionally tighten the comment wording per the Minor note.
- Optionally add one focused rolling-buffer regression test for `before_context=0, after_context=large` to lock in the output-invariance that this change relies on (the existing harness makes this easy: build a haystack with a match followed by many non-matching lines and a size that forces a roll, then compare read-vs-slice output). Not a blocker.

### Assessment

**Ready to merge?** Yes.

**Reasoning:** This is a clean, minimal, provably output-preserving performance fix that correctly narrows the buffer-retention computation to `before_context` while leaving the separator-preserving `max_context()==0` guard intact; the full searcher test suite (77 tests, including after-context-only cases under forced buffer rolling) passes, and the only notes are cosmetic/nice-to-have.
