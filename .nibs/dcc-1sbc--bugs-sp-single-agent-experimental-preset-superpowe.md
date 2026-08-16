---
# dcc-1sbc
version: 1
title: 'bugs-sp: single-agent experimental preset (superpowers-adapted solo reviewer)'
status: todo
type: feature
priority: high
created_at: 2026-08-16T13:14:39Z
updated_at: 2026-08-16T13:14:39Z
parent: dcc-hyxw
order: ar
---

Implement the experimental preset proposed in
`competition/benchmark/v2/analysis/PROPOSAL-BUGS-SP.md` (dcc-1ix0 acceptance item 3) and add its
benchmark arm.

The preset: `roster=1` — one `solo-reviewer` agent (new brief, superpowers-adapted, decaf-native
output) on the session model; clustering/screen/consolidation/validation/probe-protocol all
skipped; filtering happens at generation via the `reach` block and calibration lines; report is
standard decaf format so `resolve-code-review` / `auto-code-review` consume it unchanged.

Decisions encoded (operator, 2026-08-16): new preset rather than modifying `bugs`; per-class
reported table is the primary readout, not precision; new tool arm `ours-bugs-sp` in the
benchmark matrix.

## Acceptance

- [ ] `solo-reviewer` agent brief added (per the proposal's outline: intent slot, whole-surface
      checklist, reach block, self-assigned anchors, calibration lines, execution license, decaf
      report format)
- [ ] `code-review` SKILL.md: `bugs-sp` preset + the `roster=1` pipeline path (which steps are
      skipped, orchestrator's reduced role)
- [ ] Synced to the dev copy the harness invokes (`~/.claude/skills/decaf-quality-dev/`) — confirm
      the sync mechanism first
- [ ] Benchmark arm: `run_cell_v2.sh` INVOKE case + `tools.json` entry with `model_policy`
- [ ] Experiment run (operator-gated spend): 2 pilot subjects × 2 repeats, re-adjudicated pooled,
      scored against the proposal's success criteria (recall ≥8/16 reported, ≤$4.30/cell mean,
      defect-share ≥2/3, repeat stability)
