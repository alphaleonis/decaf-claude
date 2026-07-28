Review complete. I did **not** post anything to GitHub (no `--comment`, no API writes) — output is terminal-only, plus a local report at `.decaf/code-reviews/CODE_REVIEW_2026-07-16_18-12-21.md`.

---

# Code Review — PR #3185 (BurntSushi/ripgrep)

**"fix slow searching of `stdin` with large values of `-A/--after-context`"** · MERGED · reviewed at your explicit request
**Scope:** 4 files, +22/-11 (`grep-searcher`) · **Mode:** `max` (11 reviewers, Opus, no down-tiering) · **Spec:** issue #3184 (linked)
**Pre-flight:** build PASS · 77 unit + 1 doctest PASS · **Verdict: ✅ APPROVED** (no Critical/High)

Note on process: this PR is already merged; the skill normally refuses merged PRs, but you explicitly directed the review, so I proceeded. The central correctness risk (after-context surviving a buffer roll) was independently verified **sound** by five reviewers — no correctness defect was found.

## 🟡 Medium findings (2)

**#1 — `fill()` now blocks until the buffer fills, delaying output on slow/interactive stdin**
`crates/searcher/src/line_buffer.rs:419` · found by quick + broad + design · **validator: confirmed**
The new inner `while !self.free_buffer().is_empty()` loop reads until the fixed **64 KB** buffer is full or EOF, rather than returning after the first read that yields a line terminator. Reachable via the public `search_reader` path with an ordinary pipe — so `tail -f app.log | rg ERROR` no longer surfaces matches incrementally; output is withheld until ~64 KB accumulates or the pipe closes. Output stays correct and ordered — this is a latency/blocking change. Almost certainly a deliberate tradeoff (it's the mechanism of the fix), but it's an unstated behavioral change on a public API. **Fix:** capture the tradeoff in a comment; or break the inner loop once a terminator is present if interactive latency matters (forfeits the perf win).

**#2 — Inner read-drain loop lacks its load-bearing rationale (refactor trap)**
`crates/searcher/src/line_buffer.rs:419` · found by knowledge (High) + broad (Low), consolidated to Medium
The reason the loop must drain reads — on Linux `read()` on stdin caps at ~64 KB, so one read per fill under-fills context-grown buffers and causes #3184 — lives only in the commit message. The loop *looks redundant* with the outer `loop`; a maintainer collapsing it back to a single read would silently reintroduce the slowdown **with all 77 tests still green**. **Fix:** one-line comment stating why it drains, e.g. "do not collapse to a single read."

## 🔵 Minor findings (3)

**Consistency — `crates/searcher/src/line_buffer.rs:420`:** new read count named `readlen`; the crate's convention is `nread` (`crates/searcher/src/searcher/mod.rs:1005-1017`, `crates/cli/src/process.rs:260-265`).

**Consistency — `CHANGELOG.md:11`:** PERF entry links **issue** #3184 via a `/pull/3184` URL (#3184 is the issue, #3185 the PR). Resolves via GitHub redirect, and the changelog already mixes `/issues/` and `/pull/`, so low-stakes. Minor grammar: "performance of large values **with** `-A`" → "**of** `-A`".

**Testing Gap — `crates/searcher/src/searcher/glue.rs` (no test added):** No test guards the `roll()` `before_context`-vs-`max_context()` change. **Probe #2 (run):** reverting `core.rs:201` to `max_context()` leaves **all 77 tests passing** — the headline fix ships with zero guarding tests. Suggested: a `search_reader` test with a >64 KB haystack and an `-A` large enough to span a buffer roll, asserting exact context output.

## Refuted / notably dismissed
- **`Ok(0)`-transient → OOM** (adversarial, Medium) — **refuted by validator**: real readers return `Ok(0)` only at EOF; the unbounded growth is pre-existing terminator-less-line behavior, immaterial to `Ok(0)`.
- **"multi-read fill untested"** (test-reviewer, Medium) — **weakened by Probe #1**: collapsing the loop to one read fails `binary3`/`binary4` (`byte count` 262146 vs the new 262142), proving the harness feeds short reads and the multi-read binary path *is* exercised. Same probe confirms the two updated `glue.rs` assertions are meaningful, not tautological.

## Probes I ran (both restored; tree byte-identical, suite green)
- **#2** — reverted `roll()` → `max_context()`: **77/77 pass** (proves the roll change is untested).
- **#1** — collapsed `fill()` inner loop to one read: **`binary3` + `binary4` FAIL** (proves those assertions guard the fill change).

**Bottom line:** APPROVED. No correctness defects; the actionable items are a decision-capture comment (#1/#2, same lines) and one high-value missing regression test. All findings above have `file:line` references and none were posted to GitHub.
