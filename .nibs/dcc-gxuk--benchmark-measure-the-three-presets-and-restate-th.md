---
# dcc-gxuk
version: 1
title: 'benchmark: measure the three presets and restate the ours baseline'
status: todo
type: task
priority: high
estimate: l
tags:
    - benchmark
created_at: 2026-07-29T18:29:16Z
updated_at: 2026-07-29T18:31:24Z
parent: dcc-9q01
blocked_by:
    - dcc-rbkl
order: ag
---

# Why

This redesign invalidates every committed `ours` figure. The benchmark's `ours` column is one
configuration (`mid --report`); after #dcc-9q01 it is a configuration *space*. Nothing downstream —
the epic's cost targets, the synthesis page, the per-subject reports — can be read against the new
default until this runs.

It also subsumes the sweep that was reserved for #dcc-c2uc and #dcc-1xtt. Both landed unverified;
both get re-measured here under whatever the new default is.

# What to run

Re-run **`ours` only** — the other four tools are unaffected — once per preset:

| preset | cells | note |
|---|---|---|
| `bugs` | 9-18 | expected to be much cheaper; the recall risk lives here |
| `review` | 9-18 | the new default; this is the one that replaces the committed baseline |
| `audit` | 9-18 | expected dearest; check it is not merely `review` with noise |

[Estimate] ~$18/cell before the redesign's savings, so ~$160 single-repeat or ~$320 full **per
preset**. Two repeats is what makes a 1-of-2 result distinguishable from noise; single-repeat gives
that up.

Then `/bench-analyze` per subject. Note this **re-clusters and re-grades across all five tools**, so
the other tools' verdicts can shift even though their runs did not — the same effect that moved
figures during the #dcc-9kkz repair.

# What must be measured, not just recorded

- **Bug-catch per preset** against 16/18. `bugs` narrowing `reach` and `roster` is exactly the
  configuration that could lose an escaped defect.
- **Severity calibration** against 0.70 (21/30) — and read the denominator; anthropic's own figure
  rests on n=10.
- **Multi-finder agreement rate.** #dcc-gcob established corroboration as the discriminator, and
  both the `roster` cap and the `evidence` screen cut into it. A drop here is a **cost**, not a
  success.
- **Cost and output tokens per preset**, against $21.33/run and 367k tokens.
- **The `evidence` screen's confirmed/refuted split**, since it absorbs the validation wave —
  specifically whether it still corrects findings downward rather than rubber-stamping (the risk
  named in #dcc-c2uc).
- **Repo-sensitivity** (partial r on repo files given diff) against the 0.403 baseline. Ours has
  the *lowest* in the field; a `reach=wide` preset is exactly what could flip it to repo-scaled.

# Do not measure the cross-product

Four axes at three values is ~100 combinations at $160-320 each. Measure the three presets. Feel for
off-preset combinations comes from real use. **State that limit wherever the results are published**
— this epic already produced one metric (`subagent_distinctness`) that was misread for want of
anyone checking what it counted.

# Worth folding in while spending

- The **three unrun subjects** (go/medium, rust/medium, rust/large) would fix the thin samples that
  make #dcc-2a8i's drop-cost table unusable through its middle.
- **Subject 6's `cluster-assign.json` id scheme** (`ours__r1__N` vs `findings.json`'s `f00NN`)
  blocks the large-run clustering test #dcc-xewu still needs. Cheap to fix and worth doing first.

# Acceptance

- [ ] [run] `python3 competition/benchmark/analysis/scripts/compute_metrics.py --help` — expect:
      exit 0 after any schema change
- [ ] [run] `python3 competition/benchmark/analysis/scripts/aggregate_synthesis.py . -o /dev/null` —
      expect: exit 0 and sane sanity-check output
- [ ] [manual] Each preset's figures recorded against the baselines above, with an explicit
      judgement per preset on whether recall and corroboration held
- [ ] [manual] `tools.json` records which preset each run used — the archived cells predate all of
      this and are not comparable
- [ ] [manual] Synthesis page and per-subject reports restated, and the cross-product limit stated
