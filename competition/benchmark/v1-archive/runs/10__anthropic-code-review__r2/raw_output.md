All steps complete. Here is the review — **printed to the terminal only, nothing posted to GitHub** (per your instruction).

---

## Code review — BurntSushi/ripgrep PR #3185

**Status note:** PR #3185 (`fix slow searching of stdin with large values of -A/--after-context`) is already **MERGED**. Reviewing and printing findings anyway as requested.

The process ran 5 review dimensions (CLAUDE.md compliance, shallow bug scan, git-history context, prior-PR comments, code-comment compliance). No CLAUDE.md/AGENTS.md exists in the repo. Four dimensions found nothing actionable; the `core.rs` change (`before_context` instead of `max_context()`) and the `glue.rs` test-constant updates are correct. **One finding survived confidence scoring (score: 100/100).**

### Found 1 issue:

**1. The new inner read-loop in `LineBuffer::fill` breaks `--line-buffered` streaming** (bug due to `crates/searcher/src/line_buffer.rs`, the added `while !self.free_buffer().is_empty() { let readlen = rdr.read(...)?; if readlen == 0 { break } self.end += readlen; }` loop)

The PR replaced a single `read()` per iteration with a loop that keeps calling `read()` until the free buffer is completely full or the stream hits true EOF. This does fix the `-A` slowdown from #3184, but it is contrary to how `--line-buffered` is meant to work: `fill()` now blocks topping off the (often large, due to `-A`/`-B` sizing) buffer instead of returning promptly with whatever data is available. Streaming pipelines like `journalctl -f | rg --line-buffered PATTERN` stall and produce no timely output.

https://github.com/BurntSushi/ripgrep/blob/d4b77a8d8967ce1bf701ec65ceb9a75e85e5f2e0/crates/searcher/src/line_buffer.rs#L417-L426

**Confirmed by upstream history, not inference:** this exact commit (`8c6595c215d1e24bed5b7b86e2b18f3c871439ef`) was bisected as the cause of regression issue [#3194](https://github.com/BurntSushi/ripgrep/issues/3194) ("Line buffering appears broken in 15.0.0", dup [#3199](https://github.com/BurntSushi/ripgrep/issues/3199)) and was **fully reverted** in commit `d47663b1b4548e4fa02d6e4b575718d0f5f5e7d6` ("searcher: fix regression with `--line-buffered` flag"), whose message states: *"in retrospect, this change is clearly contrary to how `--line-buffered` works. We specifically do not want to wait around until the buffer is full."* The `core.rs` `before_context` change was kept — it alone fixes #3184 — while the `line_buffer.rs` loop and the two `glue.rs` byte-count constants (`262146`→`262142`) were reverted.

**Recommended fix:** drop the `line_buffer.rs` inner-loop change (and its paired `glue.rs` constant edits); keep only the `core.rs` `before_context` fix.

---

Reasoning trail: the shallow-bug, git-history, and prior-PR reviewers independently reached this same conclusion, and the Haiku confidence scorer verified the revert and scored it 100. The CLAUDE.md-compliance and code-comment reviewers returned zero findings.
