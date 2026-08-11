---
description: Score a v2 pooled-adjudication subject — extract, cluster, blind-grade, then compute metrics deterministically
argument-hint: "<pooled-subject-dir>  e.g. competition/benchmark/v2/pooled/dotnet-efcore-34127"
---

Score one **v2 pooled-adjudication** subject. This is the v2 counterpart of `/bench-analyze`; the v1
command scores the retired key-based dataset and must not be used here.

Design context: `competition/benchmark/METHODOLOGY-v2.md` section 2. Three axes are reported
**separately and never merged** — pooled (precision/noise), threads (the miss detector), anchor
(only if the subject has a key).

## Inputs

- `<subject-dir>/fixture.json` — checkpoint, base, app type, size
- `<subject-dir>/threads.json` — human review threads with `admission` already computed
- `<subject-dir>/cells/<tool>__r<n>/` — one directory per run cell (`final-output.md`, `meter.json`,
  `access.log`)

## Stages

**1. Extract — one subagent per cell, in parallel.** Read that cell's `final-output.md` plus any
tool-written report file, and emit every finding normalized to:

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
`threads.json`, and the clusters **with tool identity stripped** (send `cluster_id`, `summary`,
`file:line` only; keep the tool map yourself). Per cluster it returns:

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
