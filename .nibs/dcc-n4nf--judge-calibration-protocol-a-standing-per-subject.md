---
# dcc-n4nf
version: 1
title: 'Judge calibration protocol: a standing per-subject sample graded every grading day'
status: todo
type: feature
priority: normal
created_at: 2026-08-18T08:40:37Z
updated_at: 2026-08-18T08:40:37Z
parent: dcc-ho2w
order: zs
---

Judge drift is real and currently unmeasured between grading days. On 2026-08-17 the same
`claude-opus-5` judge, same prompt, agreed with the pilot's pass-1 verdicts on the same clusters at
10–11/14 (prometheus) and **3/12** (efcore) — inside a day where its own two passes agreed 12/14
and 9/12. On efcore the pilot judge turned out to be the lenient one (a thread match to a mangled
GitHub suggestion nit; a match to a *rejected bot* thread). The fold-in pipeline reports
calibration ad hoc; nothing makes it standing.

## What to build

- A fixed **calibration sample** per subject: ~15 clusters stratified across the six verdicts,
  chosen once, committed under `pooled/<subject>/grading/calibration-sample.json` with the pilot
  pass-1 and pass-2 verdicts alongside.
- Every grading day that touches a subject grades that sample blind (relabelled, mixed into
  whatever else is being graded — `v2/scoring/foldin.py`'s key format already supports old/new
  kinds) and `judge_stability.py` gains a `--calibration` mode that emits agreement vs pilot p1,
  vs pilot p2, and today p1 vs today p2, as numbers into `grading/calibration-<date>.json`.
- `score_pooled.py` refuses (exit 3) to emit metrics for an analysis whose newest verdicts carry
  no calibration record — the same "empty is not the same as failed" discipline as the rest.
- Pairs with [[dcc-di47]] (thread recall as a band): judge variance is the other half of the
  uncertainty a headline must carry.

## Acceptance

- [ ] Calibration samples committed for the five adjudicated subjects
- [ ] `judge_stability.py --calibration` + a test; `score_pooled.py` guard + a test
- [ ] `/bench-analyze` and `prompts/README.md` say to grade the sample every time
- [ ] The 2026-08-17 numbers (10/14, 3/12, 9/14, 8/12) recorded as the first entries
