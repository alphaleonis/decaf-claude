---
# dcc-1sbc
version: 1
title: 'bugs-sp: single-agent experimental preset (superpowers-adapted solo reviewer)'
status: completed
type: feature
priority: high
created_at: 2026-08-16T13:14:39Z
updated_at: 2026-08-17T08:09:52Z
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
- [x] Experiment run (operator-gated spend): 2 pilot subjects × 2 repeats, re-adjudicated pooled,
      scored against the proposal's success criteria — done 2026-08-17; results in
      `v2/analysis/BUGS-SP-RESULTS.md`. Recall 6/16 reported (10 found) ✗, cost $5.13 ✗,
      defect share 44% (70% primary-only) ✗, stability superpowers-like ~

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

## Experiment run (2026-08-17) — cells done, grading pending

`run_pilot.sh prometheus-prometheus-18081,dotnet-efcore-34127 ours-bugs-sp 2` — 4/4 ok, all
isolation CLEAN, log `v2/runs/pilot-20260817T063038Z.tsv`.

| cell | cost | wall | Opus out | turns | report summary (C/H/M/L/Minor) |
|---|---|---|---|---|---|
| prometheus r1 | $6.30 | 894s | 70,981 | 14 | 0/3/1/2/3 |
| prometheus r2 | $4.31 | 777s | 61,741 | 10 | 0/2/0/2/2 |
| efcore r1 | $5.06 | 913s | 66,581 | 14 | 2/0/0/0/3 |
| efcore r2 | $4.86 | 878s | 63,182 | 13 | 2/0/1/0/2 |
| **mean** | **$5.13** | **866s** | | | |

Mechanics all held in fresh sessions: `solo-reviewer` resolved as an agent type and appears in
every team announcement; pre-flight skipped as specified; one Opus lane per cell (no other
models); the report was written to `.decaf/code-reviews/` and captured (15–24 KB) in every cell;
capture ratio 82–84% (`final-output.md` is a fragment as expected — `cell-report.md` is the
scoreable text, and the report file is the finding set). One format drift: efcore r1 folded the
`Verified` tag into the Confidence cell (`100 (verified by execution)`) instead of its own row.

**Cost criterion (≤ $4.30 mean) — NOT met at $5.13.** Like-for-like on the same subjects,
`superpowers` cost $4.36–$4.82 (prometheus) and $3.47–$4.51 (efcore); `ours-bugs` cost
$8.19–$9.82 (prometheus). So `bugs-sp` sits ~20% above superpowers and ~40% below `ours-bugs`,
on ~40% more Opus output than superpowers (62–71k vs 38–55k). Repeat spread on prometheus
($6.30 vs $4.31) is the single-seat variance the proposal named. Where the extra output goes is
unattributed — candidates: the per-finding table format (Evidence field, tables) and Step 6
assembly; check against the transcripts before changing anything.

Recall / composition / stability criteria await pooled re-adjudication (`/bench-analyze` on both
subjects with the new arm folded in, blind, two passes).

## Summary

**Completed 2026-08-17** — Implemented, run and scored. `bugs-sp` = one `solo-reviewer` seat on the session model, no wave,
no funnel; benchmark arm `ours-bugs-sp`. Run 2026-08-17 on both pilot subjects × 2 repeats, all
CLEAN, folded into the pooled adjudication incrementally (48/51 findings merged into pilot-graded
clusters; 3 new demoted-only clusters graded blind in two calibrated passes; every existing tool's
figure unchanged). Results: `v2/analysis/BUGS-SP-RESULTS.md`. Verdict: dominates `bugs` on every
reported axis at ~40% less cost (18 vs 7 reported, 8 vs 6 defect-class, 10 vs 8 real defects found,
$1.33–2.48 vs $6.00–8.29 per real finding) but misses 3 of 4 pre-registered criteria — reported
recall 6/16 (found 10), cost $5.13 vs ≤$4.30, defect share 44% (70% primary-only) — and does not
reproduce superpowers (18 vs 45 reported, 12 vs 31 real). Stays experimental. Follow-up: dcc-pulk.
Also landed: `score_pooled.py` per-tool `class_distribution` + `defect_recall` (tested, reproduces
TUNING-SIGNALS' hand counts).
