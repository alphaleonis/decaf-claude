---
description: Score a v2 pooled-adjudication subject — extract, cluster, blind-grade, then compute metrics deterministically
argument-hint: "<pooled-subject-dir>  e.g. competition/benchmark/v2/pooled/dotnet-efcore-34127"
---

Score one **v2 pooled-adjudication** subject. The v1 command that scored the retired key-based
dataset has been removed; its data is void and its machinery lives on only under
`competition/benchmark/scripts/`, guarded.

Design context: `competition/benchmark/METHODOLOGY-v2.md` section 2. Three axes are reported
**separately and never merged** — pooled (precision/noise), threads (the miss detector), anchor
(only if the subject has a key).

## Inputs

- `<subject-dir>/fixture.json` — checkpoint, base, app type, size
- `<subject-dir>/threads.json` — human review threads with `admission` already computed
- `competition/benchmark/v2/runs/<subject-id>__<tool>__shim-<on|off>__r<n>/` — one directory per run
  cell (`final-output.md`, `meter.json`, `access.log`, `isolation.txt`), written by
  `run_cell_v2.sh`. **Score one shim arm at a time.** `shim-on` is the treatment arm and the one
  results are reported from; `shim-off` is the control, and pooling the two would mix a cell that
  could read post-checkpoint GitHub with one that could not.

Scoring artifacts (`extract/`, `findings.json`, `analysis.json`, `metrics.json`) are written into
`<subject-dir>`, beside the fixture — that is what `check_artifacts.py <subject-dir>` reads.

**Refuse to score a cell whose `final-output.md` is empty or whose `isolation.txt` says
CONTAMINATED.** An empty cell is a crash, not a tool that found nothing, and the two are
indistinguishable once they reach `analysis.json` as "contributed no clusters".

## Stages

**1. Extract — one subagent per cell, in parallel.** Read **both** of that cell's captured layers —
**`cell-report.md`** (the tool's complete main-chain output, recovered from the transcript) and
**`tool-artifacts/`** (whatever the tool wrote into the working tree, e.g.
`.decaf/code-reviews/CODE_REVIEW_*.md`) — and emit every finding normalized to:

> **Both layers, every time.** For a tool that files a report, the terminal output is a summary and
> the report is the finding set: the `ours-audit` pilot probe printed 4,919 chars and filed 41,419
> bytes, so the terminal alone is ~12% of that tool. For a tool that prints everything, the two
> overlap almost completely — dedupe by `file:line` + claim, and never count a finding twice because
> it appears in both. `tool-artifacts.tsv` lists what was captured and what was skipped and why; a
> cell with an empty `tool-artifacts/` and a manifest showing changed paths is a capture failure, not
> a tool that wrote nothing.

> **Read `cell-report.md`, not `final-output.md`.** `final-output.md` is `.result` — the session's
> final assistant message only. A tool that prints its report and then keeps working leaves the
> report out of it entirely: measured on the `comprehensive-review` pilot probe, `final-output.md`
> held 20% of what the tool printed and none of its original findings, while `superpowers` and
> `pr-review-toolkit` on the same subject were at 99% and 93%. The bias runs one way — it deletes
> findings — so scoring `.result` makes a verbose tool look quiet and precise. `run_cell_v2.sh`
> writes `cell-report.md` for every cell and prints the ratio; a cell under 80% is flagged.

```json
{"tool":"", "repeat":1, "subagent":"", "severity":"critical|high|medium|low|nit|info",
 "file":"", "line":0, "category":"", "claim":"", "raw":"",
 "disposition":"reported|demoted"}
```

**`disposition` is not optional, and getting it wrong inverts the result.** A tool can find a defect,
verify it, and then suppress it below its own reporting bar. Measured on a real cell: anthropic
headlined `### Verdict: No blocking issues found.` while a later section described the key defect
exactly — "Verified empirically… this is a pre-existing limitation, not a regression. Per the rubric,
pre-existing issues score 0." Scoring the headline gives recall 0.0; scoring everything it wrote gives
1.0. Same tool, same run.

So read the **whole report**, not the verdict. Section markers observed in practice:

| Tool family | Demoted-section markers seen |
|---|---|
| `anthropic-code-review` | `Sub-threshold observations (verified real, but scored below the reporting bar — not posted)`; `Notes on things checked and cleared (not findings)`; `Minor/cosmetic (below reporting bar)` |
| decaf presets | `### 🔵 Minor (N)`; `Considered But Not Flagged`; `**Not a defect** (all agents agree)` |

Mark a finding `demoted` when the tool states it is below its threshold, not posted, scored 0, or
explicitly "not a finding" — and `reported` otherwise. These lists are examples, not an allowlist:
tools reword their own headers, so judge by what the section *says* about whether the reader would
have been shown the finding. Write one JSON array per cell to
`<subject-dir>/extract/<tool>__r<n>.json`, then concatenate to `<subject-dir>/findings.json`.

**2. Cluster.** Pool all findings and group those asserting the SAME underlying issue (same file,
~same line, same claim) into clusters. Be careful that "the same bug described differently" collapses
to one cluster — this is the engine that makes cross-tool comparison possible.

**3. Blind grade.** Dispatch a grader with the checkpoint diff, the **admitted** threads from
`threads.json` (all of them, both origins — bot threads are matched too, they just score a different
axis; send each thread's `path`, `line`, `body` only, **never `author` or `origin`**, so the judge
cannot grade a thread differently for being bot-authored), and the clusters **with tool identity
stripped** (send `cluster_id`, `summary`, `file:line` only; keep the tool map yourself). Per cluster
it returns:

```json
{"cluster_id":"", "verdict":"matches-thread|matches-key|valid-other|valid-minor|trivia|false-positive",
 "matches_thread": 0, "judged_severity":"", "code_citation":"file:line-range", "confidence": 0,
 "rationale":""}
```

Rules the grader must follow:

- **A `code_citation` is required for every real verdict** (`matches-*`, `valid-other`). The judge
  shares a model family with the reviewers, so a verdict that cannot point at code is not evidence.
- `matches-thread` requires the index of the admitted thread it matches. Judge the *substance*, not
  the wording — a tool that raises the same defect in different words has matched it.
- `trivia` versus `valid-other` is the load-bearing boundary in this design. v1 put 58 of 98 clusters
  in that bucket and only 6 in `false-positive`, so this call **is** the metric. When genuinely
  uncertain, say so in `confidence` rather than splitting the difference.
- Never reward volume: judge each cluster on its own merits, blind to how many the tool produced.

Merge the verdicts back onto the clusters (with the tool map) and write `<subject-dir>/analysis.json`
with `subject`, `instrument`, `judge_model`, **`merged_at` copied verbatim from `fixture.json`**
(scoring refuses to emit metrics without it — it is what decides whether this subject's numbers may
be pooled into a headline, see METHODOLOGY-v2 section 5 and `scoring/vintage.py`),
`cells[]` (tool, repeat, cost_usd, wall_s, access-log
counts) and `clusters[]`.

**4. Check consistency — do not skip.**

```
python3 competition/benchmark/v2/scoring/check_artifacts.py <subject-dir>
```

Exits 3 if `extract/`, `findings.json` and `analysis.json` describe different finding sets. That has
happened and produced a published number resting on findings the pipeline no longer held.

**5. Compute metrics deterministically.**

```
python3 competition/benchmark/v2/scoring/score_pooled.py <subject-dir>/analysis.json \
  --threads <subject-dir>/threads.json -o <subject-dir>/metrics.json
```

Exits 3 on a data defect — a whole tool with empty severities, a cell contributing no cluster, a real
verdict without a citation. **Do not work around it; fix the extraction.** A null metric from a
silently-empty field is how a tool once received a free 1.00 on n=1.

**6. Report.** Give the operator, per tool: precision (plain and severity-weighted), trivia ratio,
unique real findings, findings/false-positives per cell, cost per real finding, and **thread recall as
its own line** — never folded into precision.

**Lead with `metrics.vintage.status`.** If it is `in-window`, say so in the first line of the report:
this subject merged before the judge's training cutoff, so its numbers are disclosable on their own
but **must not be pooled** with out-of-window subjects into any cross-subject figure. Five of the
twelve pooled subjects are in this class, including all three `backend` cells — see METHODOLOGY-v2
section 5.

Report **both `thread_recall` and `thread_recall_found`, plus `demotion_gap`.** Neither is allowed to
stand alone: as-reported is what a user would actually have seen, as-found is what the tool is capable
of. A large gap is a real and publishable property — a tool that finds everything and reports nothing
is not the same product as one that finds nothing, and the fix for the first is a threshold change.

`thread_recall` is computed over **human** threads only (dcc-qwt3). Report `incumbent_agreement` —
recall against bot-authored threads, i.e. agreement with incumbent automated review — as its own
line when the subject has bot threads, and never merge or average it with `thread_recall`. If
`threads.human_axis_thin` is true (1–2 human threads), report the recall **with n attached** and say
explicitly that it is per-subject disclosure only, not a poolable number.

Then two things that need a human eye:

- `threads.missed_by_every_tool` — admitted threads no tool raised. This is the miss detector's
  actual output and the reason review-disciplined repos were chosen.
- `threads.judge_dismissed_reported_threads` — a tool raised what an expert reviewer raised and the
  judge called it trivia or wrong. That is a **judge calibration failure**, not a tool failure, and it
  needs eyeballing before any number from this run is trusted.

## Rules

- Blind grading is non-negotiable — never tell the grader which tool produced a cluster.
- Never hand-compute a metric. If a number is not in `metrics.json`, it is not a result.
- Report the judge's model and training cutoff alongside results; it is pre-cutoff on most subjects.

## Reporting discipline — no interpretation before the artifact (nib dcc-t83x)

**Do not interpret a stage's output before the deterministic artifact exists.** Extraction counts,
cluster assignments, a single grading pass and `new_clusters` are all intermediates. Report them as
bare counts — "47 new clusters, ungraded" — and attach no reading.

On 2026-08-19 five conclusions about one dataset reversed inside a session. Four had the same cause:
an intermediate was interpreted in place of the pre-registered metric.

- **`new_clusters` is NOT a detection measure.** It counts claims not already in the pool. A defect
  eleven earlier arms recorded produces no new cluster when a twelfth finds it. Whenever it is
  surfaced, label it "claims not already in the pool — NOT a detection measure".
- **`precision` excludes `valid_minor`**, which is correct-and-actionable. Use `noise%` for "how much
  of this is worth reading". See `v2/scoring/METRICS.md`.
- **`finding_class` is what a finding is about; `verdict` is whether it is right.** A
  considered-and-cleared note is `defect`-class and `trivia`-verdict.

The comparison table comes from `v2/scoring/emit_facts.py` then `v2/scoring/compare_arms.py`, never
from ad-hoc code written for the question at hand.
