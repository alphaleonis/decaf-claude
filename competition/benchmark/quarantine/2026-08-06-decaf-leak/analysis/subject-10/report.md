# Subject 10 — findings-quality analysis

**ripgrep#3185** (rust / small) — a 4-file PR whose escaped bug was a `--line-buffered`/streaming
regression in `LineBuffer::fill` (a new read-until-buffer-full loop), later reverted in #3195.
Solo-maintainer repo, so no human-review threads: this subject scores on **bug recall + noise + FP
discipline**. Judge: `claude-opus-5[1m]`, blind. 18 clusters graded: **1 TP-primary, 2 valid-other,
4 valid-minor, 1 false-positive, 10 trivia.**

**This is a re-analysis.** The two `anthropic-code-review` cells were re-run on 2026-07-29 with a
plugin-qualified invocation. The cells previously recorded under that label had executed
`decaf-quality` (ours) at `high` mode — see nib dcc-9kkz — so every anthropic number in the earlier
version of this report was measuring ours. The eight non-anthropic cells are unchanged (16 Jul) and
their extraction was reused verbatim; only the anthropic findings were re-extracted, and all 18
clusters were re-graded blind.

## The escaped bug, and the first miss of the repair series

The change wraps `fill()`'s single `rdr.read(...)` in `while !self.free_buffer().is_empty() { … }`,
so `fill()` now packs the whole buffer across multiple reads instead of returning once data is
available. That is a throughput win on a file and a latency regression on a pipe — it broke
`journalctl -f | rg --line-buffered` and was reverted.

**Four of five tools caught it in both repeats. `pr-review-toolkit` caught it in only one** —
bug-catch 0.50, the first sub-1.00 recall across the three subjects re-analyzed so far. Subjects 2
and 3 were unanimous, which made them useless as discriminators; this one finally separates.

`tag1` produced the subject's **only unique-true** cluster, `c13`: because `self.end += readlen`
advances per iteration, a read error later in the same pass propagates out of `fill()` before
binary detection or `last_lineterm` run, so bytes already read in that pass are silently
discarded. Under the old single-read code that first chunk would have been searched and its matches
emitted. Nobody else saw it.

The other `valid-other`, `c11`, is a genuine consequence of the same restructuring: under
`BinaryDetection::Quit` the NUL check now runs only after the buffer is packed, so on a
short-read stream ripgrep consumes up to a full buffer past the NUL before quitting.

## Noise character — and one very clean run

**`anthropic` is the standout: precision 0.83, zero trivia, zero false positives**, from 11
findings across just 3 clusters. Its second repeat emitted a *single* finding — the primary bug —
and nothing else. That is the confidence filter working exactly as intended, and on this subject it
threw nothing valuable away.

`pr-review-toolkit` is the mirror image: precision **0.05**, 5.5 trivia per cell, 12 clusters
touched, and it still missed the bug half the time. Its output on a 33-line diff includes newtype
redesigns for pre-existing `usize` fields (`c14`, `c15`) and a comment request on a line the diff
merely reordered (`c20`).

`ours` sits mid-field again — 26 findings, 9 clusters, precision 0.27, 1.5 trivia/cell — and took
the subject's only clean false-positive hit on a `known_safe` entry: `c7` asserts the changed
`glue.rs` byte-count constants are undocumented magic numbers, when the adjacent in-file comment
already explains exactly why they moved.

`superpowers` was minimal to a fault: 6 findings, 5 clusters, caught the bug, and produced one FP.

## Did the fan-out earn its agents?

No. `superpowers` caught the primary bug with **one** agent; ours used 10.5 and `anthropic` 8.5 to
reach the same conclusion. Distinctness is 0.27–0.63, and `pr-review-toolkit`'s comparatively high
0.63 is not a virtue here — its agents diverged into unrelated speculation rather than corroborating
a catch.

On a 33-line diff there is simply not enough surface to justify a wide roster. This is the clearest
subject in the study for that point.

## Cost versus catch

superpowers **$2.31**, anthropic **$5.81**, pr-review-toolkit **$9.21** (for half a catch), tag1
**$12.99**, ours **$17.35**.

Ours is **3.0× anthropic** and **7.5× superpowers** on the smallest subject in the benchmark, for a
catch both of them also made, more noise than either, and the subject's only `known_safe` false
positive. `tag1` at least bought something for its $12.99 — the unique `c13`.

A note on the corrected baseline: anthropic's $5.81 here is *higher* than its $5.58 on subject 2,
whose diff is five times larger. Anthropic runs a fixed five-agent wave regardless of changeset
size, so it has a cost floor around $5–6 that a small diff cannot undercut. Ours, whose roster
scales with the diff, still spent $17.35 on 33 lines.

## Caveats

- **`human_issues` is empty** — solo-maintainer repo with no review threads — so `TP-human` cannot
  occur and the subject scores only on recall, noise, and FP discipline.
- **Severity calibration is unavailable for all five tools.** This subject's extraction did not
  capture severity labels — 76 of 78 `reported_by` entries carry an empty severity, and every
  consolidated-report entry is among them — so no tool has a denominator. anthropic's earlier 1.00
  came from the one sub-agent `critical` in the subject, which the metric no longer counts
  (#dcc-hmp6). The column is blank by design here;
  the missing severities are an extraction gap, not a property of the tools.
- **The eight non-anthropic cells reuse the 16 Jul extraction.** Bundles are unchanged, but any
  extraction error there persists.
- **Cluster count moved 20 → 18** with a changed verdict vocabulary, so headline counts are not
  comparable to the previous version of this file.
- Four clusters were graded at confidence ≤ 58 (`c9` 52, `c5` 55, `c6` 55, `c4`/`c11` 58); those and
  the TP-primary verdict want a human eyeball.
