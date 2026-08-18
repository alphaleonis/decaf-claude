---
# dcc-u10u
version: 1
title: 'Re-measure the wave presets post-dduy: review (and audit) on the five adjudicated subjects'
status: in-progress
type: task
priority: high
created_at: 2026-08-18T08:40:37Z
updated_at: 2026-08-18T14:55:41Z
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
- [ ] Folded in; existing per-tool figures asserted unchanged; calibration reported per subject
- [ ] Readout in `v2/analysis/` (new section or file) incl. the pre/post-dduy line for `review`
- [ ] Recommendation: is `review` post-dduy fit to ship, and does anything in it need the same
      treatment `bugs` got
