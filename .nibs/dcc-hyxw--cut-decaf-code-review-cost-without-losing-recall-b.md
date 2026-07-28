---
# dcc-hyxw
version: 1
title: Cut decaf code-review cost without losing recall (benchmark-driven interventions)
status: todo
type: epic
priority: high
tags:
    - benchmark
    - code-review
created_at: 2026-07-28T20:40:25Z
updated_at: 2026-07-28T21:08:51Z
order: zzzV
---

# Why

The controlled benchmark (#dcc-z1xw) and the analysis in #dcc-e0wj establish that `ours` costs
$21.33/run against anthropic's $11.82 while losing on severity calibration (0.62 vs 0.88). The
per-persona analysis (`analysis/scripts/roster_yield.py`) then showed **no persona is dead
weight** — every one participates in substantive clusters — so the cost has to come out of
*how* the roster works, not *which* agents are in it.

This epic collects the interventions that follow from the measurements, one nib each. Full
reasoning, measured basis and risk per intervention live in #dcc-e0wj under
`# Candidate interventions`.

# What the measurements constrain

- **9.4 reviewers + 5.1 validators** per run, against anthropic's 5 reviewers + ~5 Haiku
  auxiliaries. Ours runs roughly twice the reviewers.
- **Validators are 17.3% of sub-agent output** and originate nothing by design; with the
  always-on floor (broad 15.4% + quick 11.3%) that is 44% of sub-agent output spent regardless
  of the changeset.
- **Orchestrator thinking is 60–77% of orchestrator output**, and the orchestrator is 23% of
  session output. Consolidation is genuinely frontier-model work — there is no
  prompt-engineering fix.
- **~77% of sub-agent findings restate a sibling's**, and ours emits 19.5k output per agent
  against anthropic's 13.7k.

# The trap these all share

Corroboration is not waste. Consolidation promotes confidence on agreement (Step 5 rule 4),
which is what carries a finding over the confidence gate. An agent that never *uniquely* finds
anything may still be carrying the anchors — this already produced one wrong conclusion
(`performance-reviewer` looked droppable on sole-found; it was in fact among the finders on 7
of 9 perf clusters including an escaped bug). Every intervention here can reproduce that error
at roster scale. Re-measure; do not reason from simulation alone.

# Cost of measuring

`roster_yield.py --simulate` reuses recorded findings at zero API cost but only counts clusters
lost *entirely* — it cannot see anchor-promotion loss, so it flatters every reduction. Screening
only.

[Estimate] a real re-run is ~$18/run for a reduced roster against the $21.33 baseline: ~$320 for
the full 9-subject × 2-repeat sweep, ~$160 single-repeat (giving up stochasticity control), plus
blind re-grading. Prefer interventions that can share one re-run.

# Sequencing

1. #dcc-hmp6 — settle the yardstick first: it decides what `severity_calibration` measures, and
   three children below score themselves against it
2. #dcc-3fl5 — the only intervention needing **no** re-runs; either closes a question or
   justifies spend
3. #dcc-c2uc — best safe saving; can share a re-run with the gate changes
4. #dcc-1xtt — cheap, independently testable per gate
5. #dcc-gcob — larger design change; needs its own re-run
6. #dcc-xewu — **parked**: blocked on the product decision in #dcc-e0wj workstream 3
7. #dcc-lf4a — small and free, but low single-digit percent; do not let it displace the above

# Acceptance

- [ ] [manual] Every child either landed with a re-measured cost/recall delta against the
      committed baseline, or was closed with the evidence that killed it
- [ ] [run] `python3 competition/benchmark/analysis/scripts/roster_yield.py` — expect: exit 0,
      and the post-change roster table recorded alongside the baseline for comparison
- [ ] [manual] No regression in the behaviours #dcc-e0wj lists under `# Preserve` — notably
      validators correcting their own findings downward
- [ ] [manual] **Cost still scales with diff size, not repo size.** Partial
      r(cost, repo files | diff LOC) stays at or below the 0.403 baseline (anthropic 0.119,
      superpowers 0.831 for scale). #dcc-gcob and any history-retrieval work are the two that
      can break this; both must keep every evidence channel scoped to the changed files
