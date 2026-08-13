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
updated_at: 2026-08-13T09:36:56Z
blocked_by:
    - dcc-9kkz
order: zzzV
---

# Why

The controlled benchmark (#dcc-z1xw) and the analysis in #dcc-e0wj establish that `ours` costs
$21.33/run against anthropic's $7.61 while losing on severity calibration (0.70 vs 0.90 — restated
on the repaired data, #dcc-9kkz, and on the settled metric definition, #dcc-hmp6; at n=10 for
anthropic that gap is not one this corpus resolves confidently). The
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
- **~44% of sub-agent findings restate a sibling's** — the 77% previously cited counts validator rows, consolidated-report rows and cross-repeat determinism; corrected in #dcc-gcob, which also found the restatement is mostly corroboration of substantive findings. Ours emits 19.5k output per agent
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

**SUPERSEDED 2026-07-29 by #dcc-9q01** — the axis/preset redesign re-measures ours against a new
default, so the sweep reserved below is no longer the next spend. Kept for the reasoning.

**Sweep order was fixed: #dcc-c2uc + #dcc-1xtt are already landed and unverified, so the next
benchmark spend measures those two and nothing else.** Both changed the default path (validators to
the cheap tier; stack-reviewer and security dispatch gates), and both carry a named risk that hides
in aggregate — a cheap validator becoming a rubber stamp, and a narrowed stack gate missing subtler
idiom surface. Landing any further roster or persona change before that sweep makes its results
unattributable. Decided 2026-07-29.

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
5. ~~**#dcc-gcob** — the big lever.~~ **SCRAPPED 2026-07-29 without a re-run.** The measurement
   that would have justified it refuted it instead: the 77% restatement baseline counted validator
   rows, consolidated-report rows and cross-repeat determinism (real figure 44%, which puts ours mid-pack rather than the field's outlier), and the
   redundancy is corroboration — substantive clusters average 2.80 finders against trivia's 1.32,
   and 62% of all restatement lands on substantive findings. Disjoint briefs would have deleted the
   signal consolidation ranks on. **The epic's biggest lever is gone, and no replacement is
   planned** — the per-agent output gap (19.5k vs 9.6k) is unattacked. See #dcc-gcob.
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

## Current Focus

Completed dcc-3fl5: **Third branch of the pre-set rule: a suggestion amplifier, not a safety net.** Step 5.5 promotes
0.39 findings per run — 7 across the 18 archived `ours` runs, from 891 CBNF bullets. Three were
graded `valid-minor`, four `trivia`, and **none substantive**. The channel has never recovered a
real defect in this corpus.

Its own best case is the indictment: on subject 9 repeat 2 three reviewers each independently
traced every constructor and ruled out a nil-deref; Step 5.5 overrode all three and shipped it, and
the blind judge graded it trivia. On the evidence the step is not rescuing findings reviewers
talked themselves out of — it is overriding reviewers who dismissed correctly.

**This nib's cost premise was wrong and no removal case follows from it.** CBNF sections are 19.8%
of sub-agent report text but only ~1.8% of a run's 260.8k output tokens, so deleting the reviewer
section would not move $21.33/run. The orchestrator's Step 5.5 pass over 49.5 bullets/run is the
real cost and is not isolated by this analysis. Per the rule, the keep/drop call moves to #dcc-e0wj
workstream 3 — carrying the note that promoted items are ranked like any other finding and land
ahead of explicit dismissals, which makes the severity contract a cheaper lever than deletion.

Shipped `analysis/scripts/cbnf_yield.py` (deterministic candidate finder + cost meter, `--json`)
and `analysis/cbnf-adjudication.json` (the read of each candidate against that run's actual
bullets, with the borderline calls marked). A similarity threshold was tried as the decision rule
and rejected — it identified 2 of 7 at 0.5 and traded errors both ways at 0.3 — so the script
reports candidates and defers to the committed adjudication, flagging any unadjudicated one rather
than dropping it. Undercount risk stated: a promotion merged into a sub-agent's cluster would be
invisible.

## ⚠️ Measured premise is VOID (2026-08-10)
This epic's premise — `ours` at $21.33/run vs anthropic's $7.61, and 0.70 vs 0.90 severity
calibration — comes from the v1 benchmark ([[dcc-z1xw]], scrapped) and from [[dcc-e0wj]], whose
evidence base is void. See the warning section in dcc-e0wj for the four counts.

Two leaks push in opposite directions (contamination flattered `ours`; the GitHub leak flattered
`anthropic`), so the direction of the cost/quality gap is unknown, not merely imprecise.

**This does not automatically invalidate the child interventions.** The per-persona analysis finding
that no persona is dead weight, and the interventions that follow from how the roster works rather
than which agents are in it, may hold on their own reasoning. But **any child whose justification is
a measured figure must be re-justified** before it lands — check each against first principles or
wait for [[dcc-plsq]].

Live children to re-check: [[dcc-c2uc]], [[dcc-1xtt]], [[dcc-lf4a]].


## Premise restated on v2 data (2026-08-13)

**The "Why" above rests on v1 numbers and v1 is void.** "$21.33/run against anthropic's $7.61",
"severity calibration 0.70 vs 0.90" and the `roster_yield.py` per-persona analysis all come from the
retired dataset — contamination, GitHub leak, unaudited ground truth, unpinned effort, with the two
leaks pushing in opposite directions. None of it may be cited, including here.

Replacement premise from the v2 pilot ([[dcc-vkeh]], `v2/analysis/TUNING-SIGNALS.md`) — two subjects,
both `library`, seven tools x two repeats, blind-adjudicated twice:

- **decaf's presets are accurate but verbose.** Of `ours-audit`'s 41 reported-but-not-substantive
  clusters, **every one is judged low/nit/info — zero medium or above**; `ours-review` is the same
  shape. Severity-weighted precision gains +0.18 to +0.25 over plain, against +0.07 to +0.12 for
  `comprehensive-review`. The noise is not wrong, it is small.
- **`ours-audit` is the roster's best detector** — 37 real findings and 6 unique real findings, both
  the most of any tool. Any intervention must be checked against `unique_real`, not precision, or it
  trades away the thing the preset is good at.
- **`ours-bugs`'s gate is discarding consensus defects.** It found 40 clusters, reported 7, and 7 of
  the 33 it suppressed were real — including three high-severity findings that four to six other
  tools reported. `ours-audit` and `ours-review` demote more in absolute terms and lose 8% and 7%, so
  the shared machinery is sound and the fault is the `bugs` preset's own threshold.
- **The target to beat is `superpowers`: 31 real findings for $17.16, $0.55 each**, with no roster and
  no demotion machinery, against `ours-audit`'s 37 for $117.60. That is a far more demanding bar than
  the v1 comparison this epic was founded on.

The cheapest intervention the data supports is presentational, not architectural: collapse the
Minor/nit tier into a counted summary line instead of enumerating each item as a finding. It moves
plain precision substantially and touches no substantive finding, because none of decaf's
non-substantive output is above `low`.

Bounded by: two subjects, one application type, and `ours-bugs` having no precision figure at all
(it never cleared the ten-cluster publication floor — the demotion finding needs no ratio).
