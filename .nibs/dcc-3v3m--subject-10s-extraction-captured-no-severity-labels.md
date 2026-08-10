---
# dcc-3v3m
version: 1
title: Subject 10's extraction captured no severity labels — calibration is blank for all five tools
status: scrapped
type: task
priority: normal
tags:
    - benchmark
    - metrics
created_at: 2026-07-29T11:47:17Z
updated_at: 2026-08-10T17:51:43Z
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

## Reasons for Scrapping
Obsolete under the [[dcc-ho2w]] v2 milestone.

The specific remedy — re-harvest subject 10's severities and recompute `severity_calibration` — has
nothing left to act on. Subject 10's v1 `analysis.json` is quarantined, the v1 published figures are
void, v1 extraction is being replaced wholesale ([[dcc-y2e6]]), and the v2 scoring model revisits
severity treatment from scratch ([[dcc-595v]]) rather than inheriting v1's definition.

The finding underneath it is NOT obsolete and has been carried into [[dcc-y2e6]] as an acceptance
item: extraction must fail loudly when a field it is supposed to capture comes back empty for a whole
tool/subject, instead of emitting a metric that reads as data. That is the hazard this nib actually
documented, and it applies to any pipeline, v1 or v2.

## Summary

**Scrapped 2026-08-10** — Scrapped as obsolete under the [[dcc-ho2w]] v2 milestone — see the Reasons for Scrapping section.

Nothing left to act on: subject 10's v1 analysis is quarantined, the v1 figures are void, and both
extraction and the severity definition are being rebuilt. The underlying hazard — extraction
silently emitting an empty field that reads as data — is carried into [[dcc-y2e6]] as an acceptance
item.
