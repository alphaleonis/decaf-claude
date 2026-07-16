# Benchmark run: 10__superpowers__r2

| field | value |
|---|---|
| tool | superpowers |
| subject | 10 (rust / small) — BurntSushi/ripgrep#3185 |
| review diff | `d4b77a8d8967ce1bf701ec65ceb9a75e85e5f2e0^1..d4b77a8d8967ce1bf701ec65ceb9a75e85e5f2e0` (merge d4b77a8d8967ce1bf701ec65ceb9a75e85e5f2e0) |
| session model | claude-opus-4-8 |
| status | done (exit 0, is_error=false, subtype=success) |
| **total review time — wall (s)** | 694 |
| longest single subagent (s) | 632 |
| duration_ms (orchestrator self) | 692148 |
| duration_api_ms (summed parallel API time, not wall) | 558755 |
| num_turns | 6 |
| cost_usd | 2.9926987500000006 |
| input_tokens | 7 |
| output_tokens | 4907 |
| cache_creation_tokens | 40855 |
| cache_read_tokens | 161690 |
| total_tokens (orchestrator only) | 207459 |
| **subagents** | 1 |
| **ws output_tokens** | 5817 |
| ws input_tokens | 56 |
| ws cache_creation | 135858 |
| ws cache_read | 1996700 |
| ws total_tokens | 2138431 |
| session_id | 88a9f03a-80f0-47ea-8fd0-3e2a195551a6 |
| findings (raw lines) | 56 |

> **ws = whole-session** (orchestrator + every subagent transcript, deduped). The non-ws token
> rows are the orchestrator session ONLY — they miss subagent tokens for fan-out tools.
> **`cost_usd` is the authoritative whole-session cost** (Claude Code sums subagents; not an estimate).
> Caveat: `ws total_tokens` is inflated by prompt-cache re-reads (cache_read counted per turn);
> `ws output_tokens` is the clean, cache-independent work signal. Findings files under ./findings/.

### Per-subagent (diagnostic)

Subagents run in PARALLEL — the TOTAL review time is the wall clock above (694s), NOT the sum of these.

| agent | output_tokens | total_tokens | duration_s |
|---|---:|---:|---:|
| agent-a462e9eb3fb77c188 | 910 | 1930972 | 632 |

## Findings (final result text)

```
The reviewer subagent completed its review. Here is its full report, verbatim:

---

## Code Review: `searcher: fix a performance bug with -A/--after-context`

### What the change does

In `crates/searcher/src/searcher/core.rs`, the `roll()` function decides how many bytes to drop from the front of the streaming buffer and how many trailing bytes to retain as context before the next `read`. The one-line change swaps the retention target from `max_context()` (= `max(before_context, after_context)`) to `before_context`:

```rust
let context_start = lines::preceding(
    buf,
    self.config.line_term.as_byte(),
-   self.config.max_context(),
+   self.config.before_context,
);
let consumed = std::cmp::max(context_start, self.last_line_visited);
```

The insight is correct: `roll` retains *preceding* lines, which are only needed to satisfy `before_context` for a hypothetical future match at the start of the next chunk. After-context needs no preceding retention — it is emitted forward, and its cross-buffer state is carried entirely by `after_context_left` and `last_line_visited` (the latter preserved by the unchanged `max(context_start, self.last_line_visited)`). Retaining `after_context` preceding lines was pure dead weight that, for large `-A`, kept the buffer nearly full each roll, so each `read` advanced by very little — the quadratic-ish slowdown.

### Strengths

- **Minimal and surgical.** One functional line plus an explanatory comment; no API or structural churn.
- **Sound reasoning, well-documented.** The added comment explains *why* the after-context term is unnecessary, and the pre-existing comment about needing `last_line_visited` for the context separator remains accurate (that need is still met by the `max(...)`).
- **Behavior-preserving — verified.** I built the parent commit in a separate worktree and compared it against HEAD. Output is **byte-identical** across a broad matrix on stdin: `-A` only (0/5/50/5000/999999), `-B` only, mixed `-A>-B` and `-A<-B`, `-C`, `-v/--invert`, `--passthru`, and `--context-separator`. Line-numbered output matched too, confirming the `count_lines`/`absolute_byte_offset` accounting in `roll` (which now consumes more per roll) stays consistent.
- **Cross-path consistency — verified.** For HEAD, the changed streaming paths (stdin and `--no-mmap`) produce identical output to the mmap path for all `-A` values tested.
- **Performance goal met, dramatically.** On a ~250MB stdin input in a debug build: parent `-A999` = **117.8s** vs HEAD `-A999` = **1.0s**; HEAD stays roughly flat as `-A` grows (1.0s at `-A999` → ~1.5s at `-A999999`). Direction and magnitude match the commit's premise. (Memory was not separately measured, but the logic retains strictly *less* than before, consistent with the "no memory increase" claim.)
- **Existing tests pass and cover the changed path.** All 77 `grep-searcher` tests pass. The `SearcherTester` auto-heap-limit configs force frequent buffer rolling, and the after-context-only sub-tests (`before_context == 0`, `after_context ∈ {1,2,3}`) exercise exactly the `before_context < after_context` scenario this change alters.

### Issues

#### Critical (Must Fix)
None.

#### Important (Should Fix)
None.

#### Minor (Nice to Have)

- **`core.rs:194-197` — comment wording slightly overstates.** "We can skip this ... step when `before_context==0`" — the `lines::preceding` call is not actually skipped; it still runs with `count == 0`, which just makes it cheap (one `rfind` to the last line boundary instead of scanning back N lines). The *effect* is correct, but "skip" reads as if the call is bypassed. Consider "...this step becomes cheap (no backward scan) when `before_context==0`." Purely cosmetic.
- **No dedicated regression test for the perf-sensitive scenario.** Correctness of large-`-A` + multi-buffer rolling is covered only indirectly (small `-A` + minimal heap limit forces rolling; the logic is size-invariant). This matches ripgrep's usual practice of not adding timing-based tests, so it's acceptable — noting it only for completeness.
- **CHANGELOG:** No new entry, which is correct — the existing `PERF #3184` entry (added by the parent commit) already covers "Improve performance of large values with `-A/--after-context`." No gap.

### Recommendations

Ship as-is. Optionally tweak the "skip" wording in the comment. No other changes warranted.

### Assessment

**Ready to merge?** Yes.

**Reasoning:** The change is a correct, minimal, and well-reasoned fix; I verified it is byte-for-byte behavior-preserving against the pre-fix binary across a wide flag/size matrix (and consistent across the mmap/stdin/`--no-mmap` paths), while delivering the intended large, `-A`-invariant speedup. The only notes are cosmetic.

**Read-only compliance:** The main checkout was not mutated (HEAD still at `d4b77a8d`; only the pre-existing untracked `.decaf/` remains). The parent build was done in a temporary worktree at `/tmp/review-parent`, which has been removed, along with all temp test files.
```
