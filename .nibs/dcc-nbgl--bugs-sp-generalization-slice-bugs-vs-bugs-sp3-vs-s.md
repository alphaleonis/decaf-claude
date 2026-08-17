---
# dcc-nbgl
version: 1
title: 'bugs-sp generalization slice: bugs vs bugs-sp3 vs superpowers on 3 fresh subjects'
status: in-progress
type: task
priority: high
created_at: 2026-08-17T13:36:27Z
updated_at: 2026-08-17T13:36:36Z
parent: dcc-hyxw
order: ars
---

Everything measured for `bugs-sp` ([[dcc-1sbc]], [[dcc-pulk]], [[dcc-ce0m]]) rests on two `library`
subjects, and the pilot's rule is that one type does not generalize. Before any decision about the
shipping `bugs` preset (and the fate of [[dcc-sk3k]]), test the two claims a decision would rest on
off library code:

1. `bugs-sp` v3 dominates the four-seat `bugs` wave on every reported axis at less cost.
2. superpowers' single agent *finds* more real defects per cell than `bugs-sp`'s seat.

## Design

Three fresh subjects — the only ones that are out-of-window for the judge, checkout-ready, and
never run: `mattermost-mattermost-36824` (contract/M, 4 human threads),
`immich-app-immich-28886` (contract/S, 2 human — thin), `grafana-grafana-117615` (app-ui/S, 2 human
— thin). Three arms × 2 repeats: `ours-bugs` (post-dduy: Sonnet volume seats and screeners),
`ours-bugs-sp3`, `superpowers`. 18 cells, then a from-scratch `/bench-analyze` on each subject
(extract → cluster → two blind grading passes → class pass) with the fold-in prompts preserved
under `v2/scoring/prompts/`.

Readouts: the per-tool class table and defect recall against each subject's real-defect pool
(neither depends on human-thread count); per-cell real defects reported and found; cost per cell
and per real finding; thread recall disclosed with n (thin on two subjects — per-subject only,
never pooled). Cells count toward the eventual full run (dcc-plsq).

## Acceptance

- [ ] 18 cells run, all CLEAN, committed
- [ ] Three subjects scored (`check_artifacts` consistent, two grading passes, class axis,
      stability), committed
- [ ] Readout written to `v2/analysis/BUGS-SP-RESULTS.md` (§ Generalization) with the two claims
      answered subject by subject and pooled over the five subjects where vintage allows
- [ ] Recommendation recorded on the fate of `bugs` and dcc-sk3k
