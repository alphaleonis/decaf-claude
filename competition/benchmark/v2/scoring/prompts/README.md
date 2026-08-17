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
