---
# dcc-hmp6
version: 1
title: 'Decide what severity calibration measures: consolidated report vs max-over-subagents'
status: completed
type: task
priority: high
estimate: m
tags:
    - benchmark
    - metrics
created_at: 2026-07-28T20:57:13Z
updated_at: 2026-07-29T11:48:53Z
parent: dcc-hyxw
order: a0
---

# The problem

`analysis/scripts/compute_metrics.py::_calibration` computes
`P(judged substantive | tool said critical/high)` from the **max severity across every
`reported_by` entry** — which includes each individual sub-agent's own claim:

```python
sevs = [SEV_RANK.get((rb.get("severity") or "").lower(), 0)
        for rb in c.get("reported_by", []) if rb.get("tool") == tool]
if not sevs or max(sevs) < SEV_RANK["high"]:
```

A reader never sees those claims. They see the tool's **consolidated report**. So the published
figure answers "did any sub-agent over-claim?" when METHODOLOGY.md says it answers *"can you
trust the tool's top-of-list and stop reading?"* — a question only the consolidated artifact
can answer.

# Why it matters — it systematically penalizes fan-out

Splitting the two definitions over the 9 graded subjects:

| tool | max-over-agents (published) | consolidated report only |
|---|---|---|
| superpowers | 0.65 | 0.65 |
| pr-review-toolkit | 0.47 | 0.50 |
| anthropic-code-review | 0.83 | **0.88** |
| tag1-comprehensive-review | 0.55 | 0.79 |
| ours | 0.65 | **0.77** |

`superpowers` is the control: one sub-agent, so consolidated *is* the max, and the two agree
exactly. Every fan-out tool improves under the consolidated definition, and the more agents it
runs the larger the correction — because more agents means more chances that *someone* said
critical, whether or not it survived consolidation.

The distortion is not uniform across tools, so it is not a harmless constant: it flatters
single-agent tools and penalizes fan-out ones, on the axis the study uses to rank them.

Concretely, ours' gap to anthropic is **0.77 vs 0.88**, not 0.62 vs 0.88 — roughly 40% of the
headline. See #dcc-e0wj workstream 1, which found the residual gap is a category-boundary
problem rather than a general ranking failure.

> **The table and figures above are stale** — computed before the #dcc-9kkz data repair, and
> mixing a macro-averaged published figure with a pooled corrected one. See **## Decision** below
> for the verified numbers. The direction of every claim held; the magnitudes did not.

# Options

1. **Switch to consolidated severity.** Measures what METHODOLOGY.md claims to measure. Changes
   published numbers for four of five tools.
2. **Report both**, renamed: `severity_calibration` (consolidated, reader-facing) alongside
   something like `subagent_severity_calibration` (max-over-agents, a fan-out discipline
   signal). Loses nothing, costs a column.
3. **Keep as-is, document the caveat.** Cheapest, but leaves a headline number that does not
   match its own stated definition.

Option 2 is the likely answer — the max-over-agents figure is genuinely informative about
reviewer discipline, it is just not *calibration*. Decide explicitly rather than by default.

# Blast radius

Every artifact carrying a calibration figure has to be regenerated, and prose quoting one has
to be restated:

- `analysis/scripts/compute_metrics.py` (definition), `render_report.py:84` and
  `aggregate_synthesis.py:98-107` (consumers)
- `analysis/subject-NN/metrics.json`, `report.md`, `report.html` — all 9 subjects
- `analysis/synthesis-data.json`, `analysis/synthesis-report.html`
- `analysis/METHODOLOGY.md` — the definition text
- Prose in **#dcc-e0wj** (headline table, workstream 1) and **#dcc-05uw** (evidence section)

This is why it is not a checkbox: the numbers appear in committed reports that have already been
cited in three nibs.

# Acceptance

- [x] [manual] Option chosen and recorded with rationale. `[manual]` — it is a methodology
      judgement about what the study should report, not a computable result
- [x] [run] `rg -n "Severity calibration" competition/benchmark/analysis/METHODOLOGY.md` —
      expect: the definition states which severity it uses and why
- [x] [run] `python3 competition/benchmark/analysis/scripts/compute_metrics.py --help` —
      expect: exit 0 (script still runs after the change)
- [x] [run] `rg -n "0\.62" .nibs/ competition/benchmark/analysis/METHODOLOGY.md` — expect: no
      stale citations of the superseded figure outside explicitly-marked historical notes.
      Remaining hits are all in #dcc-e0wj and all label 0.62 as superseded
- [x] [manual] All 9 subjects' metrics/report artifacts and the synthesis page regenerated, and
      the citing nibs restated — #dcc-e0wj, #dcc-05uw, #dcc-hyxw, #dcc-xewu, #dcc-gcob, #dcc-c2uc,
      and #dcc-9kkz's figures marked historical. **The synthesis page has not been re-published as
      an Artifact** — its URL is not recorded in the repo; the committed
      `analysis/synthesis-report.html` is current

# Notes

Sits under #dcc-hyxw rather than the benchmark nib because it **defines the yardstick that epic
measures against**: #dcc-c2uc, #dcc-gcob and #dcc-xewu all carry acceptance criteria comparing
calibration to a committed baseline, and changing the definition moves those baselines. Settle
it before spending on re-runs, or the results are scored against a number that then shifts.

Found while root-causing the calibration gap for #dcc-e0wj workstream 1. Do **not** let this
land as a side effect of the severity-contract prototype in that workstream — that change alters
ours' actual behaviour, this one alters how every tool is scored, and conflating them would make
neither measurable.

## Decision
## Decision

**Option 1 — consolidated only** (not option 2). `severity_calibration` now counts only
`reported_by` entries with `subagent: null`. The max-over-sub-agents variant is *not* kept as a
second published column: it is still derivable from `analysis.json`, which retains every
sub-agent's severity, so nothing is lost from the data — only from the leaderboard, where a second
severity column would invite exactly the misreading this nib was filed about.

**Aggregation changed at the same time, and it mattered as much as the severity source.** The old
published figure was a *macro-average of per-subject ratios*; e0wj's "0.77" was *pooled*. Comparing
them overstated the correction. Per-subject denominators run 0–25 clusters, so the macro average let
a subject with one flagged cluster outweigh one with twenty, and dropped subjects where a tool
flagged nothing — leaving anthropic averaged over 6 subjects and ours over 7. Now pooled
(`Σ substantive / Σ flagged`), with `k/n` published beside every ratio.

### Restated figures (9 graded subjects, post-#dcc-9kkz data)

| tool | old (macro, max-over-agents) | new (pooled, consolidated) |
|---|---|---|
| anthropic-code-review | 0.92 | **0.90** (9/10) |
| tag1-comprehensive-review | 0.55 | **0.79** (19/24) |
| ours | 0.50 | **0.70** (21/30) |
| superpowers *(control)* | 0.63 | **0.65** (17/26) |
| pr-review-toolkit | 0.47 | **0.48** (23/48) |

`superpowers` runs one agent, so consolidated *is* the max — it moves only by the macro→pooled
change, which is the control working as intended. Every fan-out tool improves, the largest
corrections going to the tools that run the most agents.

The nib's original table (0.83/0.65/0.47/0.55/0.65 → 0.88/…) was computed before the #dcc-9kkz
repair and mixed the two aggregations. **The gap it set out to correct is real but smaller than it
claimed**: ours-to-anthropic goes 0.42 → 0.20 pooled, not "40% of the headline".

### What this does not fix — denominators

Anthropic emits confidence scores rather than severities and hard-filters below 80, so its
consolidated report flags critical/high on **10 clusters across 9 subjects**; one cluster moves its
figure by 0.10. 95% Wilson intervals: anthropic [0.60, 0.98], ours [0.52, 0.83] — overlapping.
[Inference] The 0.90/0.79/0.70 ordering is not separated by this corpus; the distance from
pr-review-toolkit (0.48, n=48) to the rest is. METHODOLOGY, the per-subject glossary and the
synthesis page all now say so, and the aggregator prints `THIN` for any tool under n=20.

Subject 10 contributes nothing: its extraction captured no severity labels at all (76 of 78
`reported_by` entries have an empty severity). Under the old macro average this handed anthropic a
free 1.00 on n=1; pooling drops it correctly. Filed as **#dcc-3v3m**.

### Incidental

`aggregate_synthesis.py` accumulated cells through a set, so `synthesis-data.json`'s `cells` array
was ordered by interpreter hash seed and the file was never byte-reproducible. Now sorted — a
re-run on unchanged inputs produces an identical file.

## Summary

Settled on **consolidated-report severity, pooled across subjects** — option 1, not the option 2
this nib predicted. The max-over-sub-agents variant is dropped from the published metrics rather
than renamed and kept: it stays derivable from `analysis.json`, and a second severity column on the
leaderboard would invite the misreading the nib was filed about.

Aggregation turned out to matter as much as the severity source and was changed with it: the old
published figure macro-averaged per-subject ratios over denominators running 0-25, which let a
one-cluster subject outweigh a twenty-cluster one and dropped subjects where a tool flagged
nothing. Now pooled, with `k/n` published beside every ratio.

Restated: anthropic 0.92 → **0.90 (9/10)**, tag1 0.55 → **0.79 (19/24)**, ours 0.50 → **0.70
(21/30)**, superpowers 0.63 → **0.65 (17/26)**, pr-review-toolkit 0.47 → **0.48 (23/48)**.
superpowers is the single-agent control and moves only by the macro→pooled change.

Two corrections to the nib's own premise: its table predated the #dcc-9kkz repair, and the
"0.77 vs 0.88" it cited compared a pooled figure against a macro one. The ours-to-anthropic gap
narrows 0.42 → 0.20, not "40% of the headline". And the denominators are the real weakness —
anthropic's figure rests on 10 clusters across 9 subjects, Wilson intervals overlap ours', and the
0.90/0.79/0.70 ordering is not resolved by this corpus. That caveat is now in METHODOLOGY, the
per-subject glossary, the synthesis page, and a `THIN` warning in the aggregator.

Shipped: `_calibration` rewritten, aggregation pooled, `k/n` rendered; 9 subjects' metrics.json and
report.html regenerated, 8 report.md narratives restated; METHODOLOGY definition rewritten;
synthesis-data.json and synthesis-report.html updated; #dcc-e0wj, #dcc-05uw, #dcc-hyxw, #dcc-xewu,
#dcc-gcob, #dcc-c2uc restated and #dcc-9kkz's figures marked historical. Incidentally fixed
`aggregate_synthesis.py` emitting a hash-seed-ordered `cells` array, so the file is now
byte-reproducible. Filed #dcc-3v3m for subject 10's missing severity labels.

Not done: the synthesis page was not re-published as an Artifact — no URL is recorded in the repo.
