---
# dcc-hmp6
version: 1
title: 'Decide what severity calibration measures: consolidated report vs max-over-subagents'
status: todo
type: task
priority: high
estimate: m
tags:
    - benchmark
    - metrics
created_at: 2026-07-28T20:57:13Z
updated_at: 2026-07-28T20:57:41Z
parent: dcc-z1xw
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

- [ ] [manual] Option chosen and recorded with rationale. `[manual]` — it is a methodology
      judgement about what the study should report, not a computable result
- [ ] [run] `rg -n "Severity calibration" competition/benchmark/analysis/METHODOLOGY.md` —
      expect: the definition states which severity it uses and why
- [ ] [run] `python3 competition/benchmark/analysis/scripts/compute_metrics.py --help` —
      expect: exit 0 (script still runs after the change)
- [ ] [run] `rg -n "0\.62" .nibs/ competition/benchmark/analysis/METHODOLOGY.md` — expect: no
      stale citations of the superseded figure outside explicitly-marked historical notes
- [ ] [manual] All 9 subjects' metrics/report artifacts and the synthesis page regenerated, and
      the three citing nibs restated

# Notes

Found while root-causing the calibration gap for #dcc-e0wj workstream 1. Do **not** let this
land as a side effect of the severity-contract prototype in that workstream — that change alters
ours' actual behaviour, this one alters how every tool is scored, and conflating them would make
neither measurable.
