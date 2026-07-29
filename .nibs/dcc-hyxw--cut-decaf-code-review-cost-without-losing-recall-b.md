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
updated_at: 2026-07-29T11:24:51Z
blocked_by:
    - dcc-9kkz
order: zzzV
---

# Why

The controlled benchmark (#dcc-z1xw) and the analysis in #dcc-e0wj establish that `ours` costs
$21.33/run against anthropic's $7.61 while losing on severity calibration (0.50 vs 0.92; both restated on the repaired data, #dcc-9kkz). The
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
  against anthropic's 9.6k — a 2.0x gap on the repaired data.

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
Ordered **free work first, then cheap-and-safe paid work, then the big lever, then the parked
items** — so every question that can be settled without API spend is settled before any re-run is
bought, and the riskiest change lands last when the baseline is already improved.

1. **#dcc-hmp6** — settle the yardstick. It is a *decision*, not a measurement, so it costs
   nothing, and three children below score themselves on calibration against a committed baseline.
   Changing what `severity_calibration` measures after they run would invalidate their results.
2. **#dcc-3fl5** — the only intervention needing **no** re-runs: the 18 archived `ours` runs
   already contain the answer. It either closes a question or justifies spending on the rest, and
   it carries a decision rule fixed in advance so a small number cannot be read post-hoc.
3. **#dcc-c2uc** — the biggest safe saving: the validation wave is 17.3% of sub-agent output and
   anthropic does the same job on Haiku. Low risk, coverage unchanged. **Shares one re-run with 4.**
4. **#dcc-1xtt** — cheap and independently testable per gate; loosening `security-reviewer` costs
   more, not less, so pair it with 3 in the same re-run to net out.
5. **#dcc-gcob** — the big lever, and **the repair raised its rank** (see below). Needs its own
   re-run and carries the highest risk in the epic: stripping overlap can cost corroboration, and
   ours' calibration (0.50) is already its weakest metric.
6. **#dcc-lf4a** — small and free to implement, but low single-digit percent of session output;
   do not let it displace the above.
7. **#dcc-2a8i** — `draft`. Its premise weakened with the repair: if per-agent verbosity rather
   than roster size is the dominant driver, the cap's *drop order* matters less than it looked.
   Refine it before picking it up, or fold it into 5.
8. **#dcc-xewu** — **parked**, blocked on the product decision in #dcc-e0wj workstream 3. A hard
   pre-consolidation filter commits to the "short trustworthy list" product; that call comes first.

### What the #dcc-9kkz repair changed about this ordering

The contaminated cells made ours look like it ran **41% more agents each emitting 43% more** than
anthropic. On clean data it runs only **23% more agents (14.5 vs 11.8)** but each emits **2.0× more
(19.5k vs 9.6k)**.

So the dominant cost driver is **per-agent verbosity, not roster size**. That promotes #dcc-gcob
from "larger design change" to the best-evidenced lever in the epic, and correspondingly discounts
everything that works by trimming the roster — including #dcc-2a8i and the roster-reduction half of
#dcc-1xtt. It does not change the sequencing, because gcob's *risk* is unchanged and the free work
still comes first, but it changes what to expect from each.

# Acceptance

- [ ] [manual] Every child either landed with a re-measured cost/recall delta against the
      committed baseline, or was closed with the evidence that killed it
- [ ] [run] `python3 competition/benchmark/analysis/scripts/roster_yield.py` — expect: exit 0,
      and the post-change roster table recorded alongside the baseline for comparison
- [ ] [manual] No regression in the behaviours #dcc-e0wj lists under `# Preserve` — notably
      validators correcting their own findings downward
- [ ] [manual] **Cost still scales with diff size, not repo size.** Partial
      r(cost, repo files | diff LOC) stays at or below the 0.403 baseline — which on the repaired
      data (#dcc-9kkz) is the **lowest in the field**, ahead of anthropic 0.572 and superpowers
      0.831. #dcc-gcob and any history-retrieval work are the two that can break this; both must
      keep every evidence channel scoped to the changed files
