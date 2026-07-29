---
# dcc-3v3m
version: 1
title: Subject 10's extraction captured no severity labels — calibration is blank for all five tools
status: todo
type: task
priority: normal
tags:
    - benchmark
    - metrics
created_at: 2026-07-29T11:47:17Z
updated_at: 2026-07-29T11:47:38Z
parent: dcc-z1xw
order: a0
---

# The problem

Subject 10's `analysis.json` carries severities on only **2 of its 78** `reported_by` entries
(one `critical`, one `low`, both from anthropic sub-agents). Every consolidated-report entry —
for all five tools — has an empty severity string.

So `severity_calibration` is `null` for all five tools on this subject, and subject 10 contributes
nothing to the pooled cross-subject figure. Every other graded subject carries severities normally,
so this is an extraction defect in this subject's harvest, not a property of the tools or of the PR.

Found while settling the calibration definition (#dcc-hmp6). Under the previous macro-averaged
metric the gap was worse than invisible: the single stray sub-agent `critical` gave
anthropic-code-review a free `1.00` on n=1, which then carried a full one-ninth weight in its
published figure. Pooling drops it correctly, so nothing is currently *wrong* — the subject is just
mute on this axis.

# Why it is worth fixing

Calibration denominators are the weak point of the whole metric (anthropic sits at n=10 across nine
subjects). Subject 10 is a free ~10-20 clusters of denominator that is already paid for — the runs
happened, the bundles are committed, only the severity field was dropped on the way into
`findings.json`.

# Where to look

- `competition/benchmark/analysis/subject-10/findings.json` and the `extract` step that produced it
  — subject 10 is one of the subjects with **no** `extract/` directory (compare subject-01,
  04, 05, 06, 07 which have one)
- Whatever severity-parsing the extraction applies per tool — five different report formats, and
  all five came back empty here, which points at the extraction pass rather than a per-tool parser

# Acceptance

- [ ] [manual] Root cause identified: why this subject's harvest dropped severities where the
      others kept them
- [ ] [run] `python3 -c "import json;d=json.load(open('competition/benchmark/analysis/subject-10/analysis.json'));print(sum(1 for c in d['clusters'] for r in c['reported_by'] if not r.get('severity')))"`
      — expect: substantially fewer than 76
- [ ] [run] `python3 competition/benchmark/analysis/scripts/compute_metrics.py competition/benchmark/analysis/subject-10/analysis.json competition/benchmark/analysis/subject-10/costs.json` —
      expect: `severity_calibration` non-null for more than one tool
- [ ] [manual] Subject 10's `report.md` calibration caveat and the synthesis page restated if the
      pooled figures move
