---
# dcc-n4nf
version: 1
title: 'Judge calibration protocol: a standing per-subject sample graded every grading day'
status: completed
type: feature
priority: normal
created_at: 2026-08-18T08:40:37Z
updated_at: 2026-08-19T16:57:58Z
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

## Summary

**Completed 2026-08-19** — Standing samples built and committed for all five adjudicated subjects — 15 clusters each,
stratified across the six verdicts, chosen once from a subject-scoped seed so the choice is
reproducible from the repo alone. `build_calibration_sample.py` REFUSES to re-draw without --force,
because re-drawing makes today's calibration incomparable with every earlier one.

`judge_stability.py --calibration` compares today's verdicts against the pilot's pass 1 AND pass 2
on that sample, and reports the DIRECTION of disagreement (harsher / softer / same) — the property
that decides whether comparative claims survive. It refuses an ungraded sample rather than reporting
0/0: a missing measurement is not a calibration of zero.

`score_pooled.py` exits 3 for a subject with no calibration record, with the exact command to fix
it; `--no-calibration` covers a first scoring. Tested both ways.

The 2026-08-17/18/19 numbers are recorded in pooled/CALIBRATION-HISTORY.md. The per-subject
backfills are marked BACKFILL and partial (n=3-5 of 15) because both earlier grading days drew their
own samples — exactly the confound the standing sample removes. Real calibration starts from the
next grading day.

The finding worth carrying: 2026-08-19's judge was systematically harsher than the pilot — 11
disagreements, 11 of them harsher, three pilot-real clusters downgraded and none upgraded — while
agreeing with itself 24/24 on prometheus. Self-agreement cannot detect this, which is the whole
argument for the standing sample.
