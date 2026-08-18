---
# dcc-u10u
version: 1
title: 'Re-measure the wave presets post-dduy: review (and audit) on the five adjudicated subjects'
status: in-progress
type: task
priority: high
created_at: 2026-08-18T08:40:37Z
updated_at: 2026-08-18T17:45:46Z
parent: dcc-hyxw
order: ary
---

The wave presets have not been measured since [[dcc-dduy]] (2026-08-17) moved volume and
verification agents from Haiku to Sonnet under `models=low`/`norm`. Every `ours-review` and
`ours-audit` figure in `v2/analysis/PILOT-RESULTS.md` / `TUNING-SIGNALS.md` is pre-dduy on two
`library` subjects; the generalization slice ([[dcc-nbgl]]) measured only `bugs` arms. `review` is the
default preset and the one most people run, so a `tuning → main` merge without this would ship a
model-policy change blind.

## Design

`ours-review` × 2 repeats on the five subjects that already have adjudications
(`prometheus-prometheus-18081`, `dotnet-efcore-34127`, `mattermost-mattermost-36824`,
`immich-app-immich-28886`, `grafana-grafana-117615`) — 10 cells — folded in with the preserved
fold-in pipeline (`v2/scoring/prompts/`, `v2/scoring/foldin.py`): extract both layers, cluster
against the existing pool, blind-grade only genuinely new clusters inside a relabelled calibration
sample, two passes + class, report the calibration. Optionally `ours-audit` on the three new
subjects (6 cells) if spend allows. On prom/efcore the arm id `ours-review` already holds pre-dduy
cells — run under `ours-review` with `BENCH_REPEAT` continuing the numbering (r3, r4) and record in
`tools.json` that r1/r2 there are pre-dduy; on the three new subjects r1/r2 are post-dduy.

Readouts: class table (per-tool `class_distribution`), defect recall against each subject's pool,
per-cell real defects reported, cost per cell and per real finding, thread recall with n; the
pre- vs post-dduy comparison on prom/efcore as its own line (verification-verdict distribution:
confirmed/refuted/uncertain — the rubber-stamp risk dcc-c2uc named and never measured).

## Acceptance

- [x] 10 (or 16) cells CLEAN, committed — the 10 `ours-review` cells are done (2026-08-18): prom r4/r5, efcore r3/r4, mattermost r1/r2, immich r1/r2, grafana-117615 r1/r2. All rc=0, is_error=false, isolation CLEAN, artifact captured. A prom r3 was lost to [[dcc-xhku]] and is committed as a failure record, not evidence; r5 replaced it. The 6 optional `ours-audit` cells are not run.
- [x] Folded in as arm `ours-review-postdduy` (foldin.py refuses a tool already present; see tools.json). Calibration reported per subject: 53/75 vs pilot p1, 51/75 vs p2, all five PASS the pre-registered threshold. Existing figures were asserted and 12 movements found — NOT unchanged: 6 benign (`unique_real` lost to a second reporter) and 6 structural (the real-defect pool grew on immich 4→5 and grafana 4→6, deflating every tool's recall). See [[dcc-dirp]] — the criterion is wrong as written.
- [x] Readout: `v2/analysis/REVIEW-POSTDDUY.md`, incl. the pre/post-dduy line on prom/efcore and the first measurement of the dcc-c2uc rubber-stamp question.
- [x] Recommendation: ship (no regression found), but dduy's benefit to `review` is unmeasurable at two subjects — the two move in opposite directions with repeat variance exceeding the effect. Single-seat `review` worth exploring on a wider slice; not before [[dcc-n5h2]].
