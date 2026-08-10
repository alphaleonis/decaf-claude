---
# dcc-gxuk
version: 1
title: 'benchmark: measure the three presets and restate the ours baseline'
status: scrapped
type: task
priority: high
estimate: l
tags:
    - benchmark
created_at: 2026-07-29T18:29:16Z
updated_at: 2026-08-10T17:55:11Z
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

# What to run — scoped 2026-07-29

**Three presets on one subject per size class**, `ours-*` only. The other tools are unaffected by
the redesign and stay archived.

| target | subjects | cells |
|---|---|---|
| `ours-bugs` | 1 (csharp/small), 5 (typescript/medium), 9 (go/large) | 6 |
| `ours-review` | same | 6 |
| `ours-audit` | same | 6 |

**18 cells.** One subject per size band is the minimum that both compares the presets on identical
code *and* exercises the size-derived roster across all three bands — the axis most likely to
misbehave, since it changes default coverage without anyone having measured it.

```
bash competition/benchmark/scripts/bench_next.sh --tool ours-bugs
bash competition/benchmark/scripts/bench_next.sh --tool ours-review
bash competition/benchmark/scripts/bench_next.sh --tool ours-audit
```

**The harness runs the dev plugin, not the installed one.** `tools.json` invokes
`/decaf-quality-dev:code-review`, a renamed copy at `~/.claude/skills/decaf-quality-dev/` with all
114 internal `decaf-quality:` references rewritten. Without that rewrite the new orchestrator would
dispatch the *stable* plugin's agents and the run would measure a chimera. Refresh the copy after
any skill edit — it is a snapshot, not a link.

**Retired targets.** `pr-review-toolkit` and `tag1-comprehensive-review` are no longer run. Their
pending cells are marked `obsolete`; their 36 graded cells stay committed and stay in the analysis,
because cluster membership is pooled across whatever tools are present and removing them would
shift every other tool's numbers.

**Also still pending, and not part of this scope:** 12 cells for `anthropic-code-review` and
`superpowers` on subjects 8, 11 and 12 — the three never-run subjects. `bench_next` without
`--tool` will pick those up first. Run them only if widening the study is the intent.

# What must be measured, not just recorded

- **Bug-catch per preset** against the archived 16/18 — but see the caveat below; that figure is
  from a different configuration and only three subjects are being run here. `bugs` narrowing `reach` and `roster` is exactly the
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

## Baseline caveat — read before quoting any comparison

**The archived `ours` column is not a baseline for these runs.** It measured the pre-axis skill at
`mid --report`, before `roster`, `models`, `evidence` and `reach` existed. It is a different tool
that happens to share a name.

Three of the four axes changed default behavior in ways that move the numbers on their own:
smaller default rosters on small diffs, a cheaper `max`, a screen that tiers findings before
consolidation, and a validation wave that no longer selects on single-finder. Attributing a
difference to any one of them from this run is not possible — 18 cells over 3 subjects supports
"the presets differ, and here is how", not "intervention X caused Y".

Say that wherever the results are published.

## Reasons for Scrapping
Superseded by the [[dcc-ho2w]] benchmark v2 milestone.

This task IS what produced the 18 contaminated cells. Every one of them ran against a shared checkout
whose `.decaf/code-reviews/` carried the previous cell's report, which the decaf recurring-findings
cross-check then read — see [[dcc-2cxq]]. All 18 were invalidated and quarantined.

Re-running them under v1 was explicitly scrapped: two of the first three subjects audited under v2
had invalid ground truth, so the numbers would be graded against defects that may not be in the
reviewed diff.

The actual goal — measure the three presets and restate the `ours` baseline — is now delivered by
[[dcc-vkeh]] (roster pilot) and [[dcc-plsq]] (full v2 run), against audited ground truth and with the
leak controls in place.

## Summary

**Scrapped 2026-08-10** — Scrapped as superseded by [[dcc-ho2w]]. The 18 cells this task ran were contaminated and have been
invalidated; re-running them under v1 was scrapped with [[dcc-2cxq]]. Measuring the three presets now
happens under [[dcc-vkeh]] and [[dcc-plsq]] against audited ground truth.
