# Subject 10 — findings-quality analysis

**ripgrep#3185** (rust / small) — a 4-file PR whose escaped bug was a `--line-buffered`/streaming
regression in `LineBuffer::fill` (a new read-until-buffer-full loop), later reverted in #3195.
Solo-maintainer repo, so no human-review threads: this subject scores on **bug recall + noise + FP
discipline**. Judge: `claude-opus-4-8`, blind. 20 distinct issue-clusters graded: **1 TP-primary, 3
valid-other (test gaps), 1 false-positive, 15 nitpicks.**

## Did they catch the bug?

Yes — almost universally, which surprised me given how subtle it is (the maintainer himself merged it
and only reverted after a user bug report). **`ours`, `anthropic-code-review`, `tag1`, and
`superpowers` all flagged the streaming regression in both repeats.** `pr-review-toolkit` caught it in
only one of two runs (bug-catch 0.5) — and even then rated it merely `[Inference]` low, where
`ours`/`tag1` called it **critical/high** and named `--line-buffered` / `tail -f` explicitly. So on
raw recall the tools are close; on **severity calibration** the fan-out reviewers were sharper.

## The real story is noise, not signal

Every tool found essentially the **same** valid set (inter-tool Jaccard 0.5–1.0; `superpowers` and
`tag1` had an identical valid set). Almost nothing was uniquely surfaced — **only
`pr-review-toolkit` contributed a unique true finding** (a binary-detection-across-read-boundary test
gap). So the tools barely differ in *what real issues they find*. They differ enormously in **how much
junk they bury it in**:

- **Nitpicks per cell:** `pr-review-toolkit` 6.5, `ours` 5.5, `anthropic` 5.0, `tag1` 4.5,
  **`superpowers` 1.5**. The fan-out reviewers each emitted ~5–6 low-value items per run (naming
  quibbles, a CHANGELOG link nit, "add a debug_assert" on the *correct* fix, undocumented-magic-number
  notes) around the one real bug.
- **Precision** (TP+valid ÷ reported) lands low for everyone (0.25–0.32) except **`superpowers` at
  0.50**, purely because it said less.
- **False positives:** only `anthropic-code-review` produced one — a speculative "transient `Ok(0)` →
  unbounded OOM" that the code doesn't actually allow (the loop `break`s on `Ok(0)`).

## Fan-out efficiency (subagent redundancy)

The multi-agent tools spend a lot of agents re-finding the same thing. **`ours` is the most redundant
(subagent-distinctness 0.36** — roughly two-thirds of its ~11 subagent-findings were the same handful
of clusters, chiefly the streaming bug restated by agent after agent). `pr-review-toolkit` was the most
distinct (0.63). This is the systematic version of the corpus's "quick-reviewer found 0 unique" signal:
on a small PR, 11 agents mostly corroborate one bug rather than expand coverage.

## Cost vs. catch

On this subject the cheap tools win decisively. **Cost per bug caught: `superpowers` $2.71, `tag1`
$13.0, `ours` $17.4, `pr-review-toolkit` $18.4, `anthropic` $20.4.** `superpowers` caught the same
bug at ~1/7th the cost of the fan-out reviewers and with the least noise. The fan-out premium bought
**sharper severity** and a bit of **corroboration**, but **no extra real findings** here — the one
unique true finding came from the mid-priced `pr-review-toolkit`, not the priciest tools.

## Caveats (do not over-generalize from one subject)

- **One small PR with a single subtle bug and no human threads.** Precision looks bad for everyone
  because there was almost nothing real to find beyond one bug — a target that rewards terseness. On a
  large, multi-issue PR the fan-out tools' depth and validation should pay off very differently; that's
  what the other 11 subjects are for.
- **Severity, not recall, was the separator here** — a dimension this small subject happens to isolate
  well.
- **Single judge** (`claude-opus-4-8`); the `c6` (comment-mismatch → nitpick) and `c8`/`c11`
  (design/perf → nitpick) calls are the most debatable and are flagged below for human spot-check.

## Human spot-check queue (bias control)

- **Every TP-primary:** `c1` (confidence 92) — verify the streaming-regression match is correct.
- **The false-positive:** `c18` (OOM claim, confidence 60) — confirm the `Ok(0)` break refutes it.
- **Low-confidence / debatable:** `c6` (50), `c8` (50), `c11` (50), `c14` (48), `c16` (50) — mostly
  nitpick-vs-valid boundary calls on design/perf/test observations.
