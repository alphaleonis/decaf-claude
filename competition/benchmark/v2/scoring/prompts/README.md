# Fold-in prompts (nib dcc-1sbc / dcc-pulk)

The prompts used to fold a new tool arm into an already-graded v2 subject without re-grading the
baseline, preserved verbatim after the pilot's own grader prompt turned out not to be — the pilot
authored it from the `/bench-analyze` rules and kept nothing. `<scratch>/` marks per-run paths.

| file | stage | notes |
|---|---|---|
| `foldin-extractor.md` | 1 — one agent per cell, both layers | `__CELL__`, `__TOOL__`, `__REP__` placeholders |
| `foldin-clusterer.md` | 2 — assign new findings to existing clusters or new ones | `__INPUT__`, `__NEWIDS__`; a cleared note clusters with the claim it clears |
| `foldin-blind-grader.md` | 3 — verdicts, blind, run twice independently | subject-specific bits (diff path, repo, threads file, PR title) are substituted per subject; the rules text is the `/bench-analyze` rubric verbatim |
| `foldin-class-grader.md` | 3b — `finding_class`, blind to verdict and tool | `__CLUSTERS__`, `__PR__`, `__DIFF__` |
| `../foldin.py` | deterministic merge | appends `reported_by`, new clusters with pass-1 verdicts + class, pass-2 verdicts, cells; rebuilds `findings.json` |

Discipline that goes with them: new clusters are graded inside a stratified sample of already-graded
clusters, relabelled so the judge cannot tell new from old, and the sample's agreement with the pilot
verdicts is reported as calibration. On 2026-08-17 that calibration was 10–11/14 on prometheus and
**3/12 on efcore** (today's two passes agreed 9/12 with each other) — the pilot's efcore judge was
the lenient one on inspection (a thread match to a mangled suggestion nit; a match to a rejected bot
thread). Report the calibration every time; do not assume the judge is stable across weeks.

## The fold-in acceptance criterion (nib dcc-dirp)

**Not "existing per-tool figures unchanged" — that is unachievable and rewards a weak arm.** An arm
contributing nothing novel passes trivially; one that finds a real defect nobody had recorded
necessarily fails. The gate is that **every movement is EXPLAINED**, checked by
`scoring/assert_foldin_movements.py <before-metrics.json> <after-metrics.json>`, which exits 3 only
on an unexplained one.

Two classes are benign:

- `unique_real-lost` — "unique" means only-that-tool, so a second reporter correctly removes it.
- `pool-grew` — the real-defect pool is the union of what tools found, so a new arm finding a real
  defect enlarges it and lowers every other arm's recall **without those arms changing**. Measured
  2026-08-18: immich 4 -> 5 and grafana 4 -> 6, dropping `ours-bugs` from 1.000 to 0.800 and 0.667.

Consequence: **a defect-recall figure is only comparable against figures from the SAME pool.** Print
the pool size beside it, always, and never compare a recall across fold-ins.

## Grade the standing calibration sample — every time (nib dcc-n4nf)

Every grading day that touches a subject must grade that subject's **standing calibration sample**
(`pooled/<subject>/grading/calibration-sample.json` — 15 clusters, chosen once, stratified across
the six verdicts), relabelled and mixed into whatever else is being graded so the judge cannot tell
a calibration cluster from a live one. Then record it:

    judge_stability.py <pass1> <pass2> \
      --calibration pooled/<subject>/grading/calibration-sample.json \
      -o pooled/<subject>/grading/calibration-<date>.json

**Do not draw a fresh sample.** A fresh draw confounds sampling with drift, and two days' numbers
are then not comparable — which is what happened on 2026-08-18 and 2026-08-19. The same clusters
every day makes a difference in the number a difference in the judge.

`score_pooled.py` exits 3 for a subject with no calibration record. Pass `--no-calibration` only
when a subject is being scored for the very first time.

**Self-agreement is not calibration.** On 2026-08-19 the judge on prometheus agreed with itself
24/24 (kappa 1.0) while agreeing with the pilot on 9/15 and 6/15, and every one of its 11
disagreements was in the harsher direction. `judge_stability.py`'s stability mode cannot see that,
because it never looks at the baseline. Report the direction too: a uniformly harsher judge leaves
comparative claims intact while making absolute counts unpublishable.
