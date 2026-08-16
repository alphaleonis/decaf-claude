---
# dcc-1sbc
version: 1
title: 'bugs-sp: single-agent experimental preset (superpowers-adapted solo reviewer)'
status: in-progress
type: feature
priority: high
created_at: 2026-08-16T13:14:39Z
updated_at: 2026-08-16T14:00:01Z
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

- [x] `solo-reviewer` agent brief added (per the proposal's outline: intent slot, whole-surface
      checklist, reach block, self-assigned anchors, calibration lines, execution license, decaf
      report format) — `decaf-quality/agents/solo-reviewer.md`
- [x] `code-review` SKILL.md: `bugs-sp` preset + the `roster=1` pipeline path — presets table
      row + "The bugs-sp path (experimental)" section (dispatch template, step skips, report
      header), plus skip markers in Steps 4.9/4.95/5/5.5/5.6
- [x] Synced to the dev copy the harness invokes — mechanism is `scripts/install-dev-plugin.sh`
      (snapshot + namespace rewrite); verified repo `decaf-quality/` had zero drift from the
      pilot's Aug 6 snapshot before re-running it, so the sync carries only this change
- [x] Benchmark arm: `run_cell_v2.sh` INVOKE case (+ unknown-tool list) + `tools.json` entry with
      `model_policy`; `capture_tool_artifacts.sh` already sweeps `.decaf/` so no change needed there
- [ ] Experiment run (operator-gated spend): 2 pilot subjects × 2 repeats, re-adjudicated pooled,
      scored against the proposal's success criteria (recall ≥8/16 reported, ≤$4.30/cell mean,
      defect-share ≥2/3, repeat stability)

## Smoke test (2026-08-16)

Ran the full `bugs-sp` path on a scratch repo with two planted uncommitted defects (an off-by-one
in a pagination end bound; a `ValueError` guard silently downgraded to clamping). The seat found
both — the off-by-one as Critical / anchor 100 / `executed` (ran the existing suite, named the
failing test, walked all pages to show duplicates), the contract change as Medium / 75 with a
before/after probe against HEAD. Report body matched the format; reach=narrow was respected
(absence hunt declined, missing-test note folded into the fix); tree ended clean. ~57k subagent
tokens on the session model.

One link not exercisable in the implementing session: agent-type registration is loaded at session
start, so `decaf-quality-dev:solo-reviewer` was dispatched via a general-purpose agent with the
brief inlined. The registry error listed all 23 sibling agents from the same directory, so fresh
sessions (every harness cell is one) discover it by the same mechanism. Verify trivially at the
start of the experiment run: the first cell's team announcement names the agent.
