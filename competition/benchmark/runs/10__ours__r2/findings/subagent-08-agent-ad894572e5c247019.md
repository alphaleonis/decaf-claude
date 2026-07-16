# subagent agent-ad894572e5c247019

I now have everything needed. I traced the full picture: the reporter's scenario reaches the fixed code paths, confirmed by both static analysis and the reported timing.

## Spec-compliance review — ripgrep PR #3185 vs. issue #3184

**Spec source: `linked`** (issue #3184, referenced by "Fixes #3184"). Reviewed at full strength — no severity cap. This is a Bug report; the spec is its repro + expected behavior.

**Verdict: the change faithfully implements the reported requirement.** No spec-compliance findings at or above the reporting threshold.

Key verification for the crux question (does the fix help the *reported binary/stdin* scenario, not just the maintainer's non-binary benchmark?):

- The reporter ran `cat <9.8GB binary file> | rg XXXXX -A<N>`, default flags, and observed the *entire* file being processed (`-A9999999` = 235s). A super-linear-in-N runtime over the whole file is only consistent with **convert-mode** binary detection, not an early quit.
- Confirmed in-repo: for explicit/stdin haystacks with default flags, binary detection defaults to `BinaryDetection::convert(b'\x00')` (`crates/core/flags/hiargs.rs:1160`; applied via `crates/core/search.rs:249-257`). In convert mode `quit_byte()` is `None`, so `should_binary_quit()` (`crates/searcher/src/searcher/glue.rs:90-93`) is always false and `fill()` reads the entire stream — the "found \0 byte around offset 7" message is recorded lazily but does not stop the search.
- Therefore both fixed paths are exercised in the reporter's exact scenario: the `fill` inner read loop (`crates/searcher/src/line_buffer.rs:419-425`) and the `roll` change to `before_context` (`crates/searcher/src/searcher/core.rs:198-205`). NUL→line-terminator conversion changes line structure but not buffer sizing or the fill/roll amortization, so the invariance-to-N result carries over to the binary input. The benefit is realized in the reported case even though the PR benchmarked only non-binary text.

Findings:

```json
[]
```

## Requirement Coverage Matrix

| Req | Description | Type | Status | Evidence |
|-----|-------------|------|--------|----------|
| R1 | `cat large_file \| rg PATTERN -A<N>` runtime must be roughly invariant to N (not super-linear like the reported 0.33s→235s curve) | functional/perf | **Covered** | `core.rs:198-205` — `roll` now passes `before_context` (0 for `-A`-only) to `lines::preceding`, removing the O(N) backward scan per buffer roll (`before_context==0` short-circuits it entirely); `line_buffer.rs:419-425` — inner `while !free_buffer().is_empty()` fill loop amortizes reads across the whole (grown) buffer. Maintainer bench: `-A999`→`-A999999` all ~2.0s post-fix. |
| R2 | Fix must address the stdin path specifically (repro is stdin-only; files were already fast) | constraint | **Covered** | `line_buffer.rs:419-425` targets the stdin behavior (per commit `8c6595c`: `read` on stdin caps ~64K, defeating buffer-growth amortization). The `roll` fix (`core.rs`) is general but is *required* to reach invariance — after the fill fix alone stdin `-A999999` was still 6.9s, not flat. |
| R3 | Invariance must hold for the reported *binary* input (NUL at offset 7, binary detection active), not only clean text | edge-case | **Covered** (benefit realized; not separately benchmarked by PR) | Default stdin detection = `convert` (`hiargs.rs:1160`), so `should_binary_quit()` is false (`glue.rs:90-93`) and the full stream flows through the fixed `fill`/`roll` paths; the 235s report itself proves full-stream processing. Convert's NUL replacement is O(bytes), not O(N·bytes), so it does not reintroduce N-dependence. |
| R4 | Correctness preserved — same results, only faster | constraint | **Covered** | `fill` EOF detection via `newbytes.is_empty()` (`line_buffer.rs:432-437`) still handles a final partial line with no terminator; `roll` retention `max(context_start, last_line_visited)` (`core.rs:203-204`) keeps everything after-context needs. Pre-flight: 77 unit + 1 doctest PASS; extensive `-A/-B/-C` integration tests unchanged. |

## Considered But Not Flagged

- **Binary scenario not benchmarked in the PR (not a code gap).** The maintainer verified with non-binary `bigger.txt`; the issue's input was a 9.8GB binary file. I initially treated this as a possible `SPEC_EDGE_CASE` gap (anchor ~25) but **refuted** it: the reported full-file processing time and the default convert-mode wiring both show the reporter's scenario executes the identical fixed code paths. Benefit is realized. This is a verification-completeness observation (test-reviewer scope), not a spec deviation.
- **`roll` fix also speeds up the file/mmap-less path — not scope creep.** Changing `max_context()`→`before_context` in `core::roll` benefits all `read`-based searching, not just stdin. It is not unrequested scope creep: it is the algorithmic half of the fix and is necessary to satisfy R1 (the stdin fill fix alone did not achieve invariance). Improving the file path is a benign, in-scope side effect of removing an O(N)-per-roll scan.
- **No new regression test.** Neither commit adds a test asserting the perf characteristic. Performance regressions are hard to assert deterministically in unit tests, and this is test-reviewer's scope, not spec compliance. Noted only for completeness.
- **Quit-mode over-read on first fill — analyzed, no regression.** The new inner loop reads to buffer-full before the `Quit` truncation runs. On the first fill the buffer is still 64K (no growth yet) and stdin reads cap at ~64K, so an early NUL is detected within one read; no meaningful over-read or behavioral change versus the old single-read structure.

### Probe Requests (optional; not run)
- Build `rg` (release) and pipe a synthetic binary haystack (an early NUL plus a match, followed by enough lines that a single `-A` window exceeds 64K) via stdin, timing `-A99` … `-A9999999`, to empirically confirm the runtime is flat in the binary/convert case. Static tracing already establishes coverage; this would add end-to-end confirmation of R3. Requires generating a multi-hundred-MB input, hence nominated rather than run.

Relevant files: `/home/decaf/code/decaf-claude/competition/benchmark/repos/10/crates/searcher/src/line_buffer.rs` (`fill`, 406-477), `/home/decaf/code/decaf-claude/competition/benchmark/repos/10/crates/searcher/src/searcher/core.rs` (`roll`, 185-213), `/home/decaf/code/decaf-claude/competition/benchmark/repos/10/crates/searcher/src/searcher/glue.rs` (`ReadByLine::fill`/`should_binary_quit`, 58-93), `/home/decaf/code/decaf-claude/competition/benchmark/repos/10/crates/core/flags/hiargs.rs` (binary defaults, 1152-1170).
