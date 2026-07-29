---
# dcc-3fl5
version: 1
title: Price the Considered-But-Not-Flagged channel (analysis only, no re-runs)
status: completed
type: research
priority: high
estimate: s
tags:
    - code-review
created_at: 2026-07-28T20:41:05Z
updated_at: 2026-07-29T12:03:50Z
parent: dcc-hyxw
order: aV
---

# Why

Every reviewer emits a `Considered But Not Flagged` section, and Step 5.5 has the orchestrator
reason over **all** of them to promote wrongly-dismissed findings. That costs output in every
agent plus orchestrator thinking — and orchestrator thinking is 60–77% of orchestrator output.

The channel exists for a real reason: LLM reviewers talk themselves out of legitimate findings,
and Step 5.5 is the compensation. But it has **never been priced against what it recovers**.

This is the only intervention in #dcc-hyxw that needs **no benchmark re-runs** — the 18 archived
`ours` runs already contain everything required. It either closes the question or justifies
spending on the rest.

# What to do

For each archived `ours` run, recover the findings Step 5.5 promoted from a dismissed item, and
join them to the judge's verdict:

- The consolidated report (`runs/*/findings/CODE_REVIEW_*.md`) carries the
  `Considered But Not Flagged` appendix and the final findings list.
- `analysis/subject-NN/findings.json` + `analysis.json` give per-finding cluster membership and
  the graded verdict (`TP-primary` / `TP-human` / `valid-other` / `valid-minor` / `trivia` /
  `false-positive`).
- Persona attribution, where `analysis.json` lacks it, is cached in
  `analysis/subject-NN/agent-personas.json` (see #dcc-m8ar).

Then answer: how many findings did Step 5.5 promote, and what were they judged to be?

# Decision rule, set in advance

- **Promotion rate ~zero** → the channel is dead weight; propose removing the reviewer output
  section and Step 5.5, and re-measure once as confirmation.
- **Promotes substantive clusters** → the channel earns its cost; close this and record the
  measured recovery rate so it is not re-litigated.
- **Promotes only trivia/valid-minor** → it is a suggestion amplifier, not a safety net; the
  keep/drop call moves to the product question in #dcc-e0wj workstream 3.

Setting the rule before looking prevents a post-hoc reading of a small number.

# Acceptance

- [x] [run] `python3 competition/benchmark/analysis/scripts/cbnf_yield.py` — expect: exit 0,
      one row per archived `ours` run with promoted-finding counts and their graded verdicts,
      plus a total
- [x] [run] `python3 competition/benchmark/analysis/scripts/cbnf_yield.py --json` — expect:
      exit 0, machine-readable output for the synthesis page
- [x] [manual] Verdict recorded against the decision rule above, with the promotion count and
      what those promotions were judged to be. `[manual]` because the call is a judgement on a
      measured number, not the number itself.

# Notes

Reasoning and measured basis: #dcc-e0wj → `# Candidate interventions` → item 5.

## Verdict
## Verdict

**Third branch of the decision rule: a suggestion amplifier, not a safety net.** Step 5.5 does
promote — the rate is not zero — but across 18 archived `ours` runs it has never once recovered a
substantive finding.

| | |
|---|---|
| CBNF bullets emitted | **891** over 18 runs (49.5/run), from 150 of 261 sub-agent reports |
| Promotions | **7** (0.39/run — one per ~127 bullets) |
| What they were judged to be | 3 `valid-minor`, 4 `trivia` |
| Substantive (`TP-primary` / `TP-human` / `valid-other`) | **0** |

The seven: a `!=` spacing nit, a CRLF-normalization diff, a CHANGELOG URL mismatch, an unfixed
sibling call site, a doc/code mismatch, a cross-package coupling note, and a nil-deref that three
reviewers had each independently traced and ruled out.

That last one is the channel's own best case and its clearest indictment. On subject 9 repeat 2,
`subagent-05`, `-12` and `-17` all walked every constructor and concluded the nil-deref is
impossible by construction. Step 5.5 overrode all three and shipped it as a "landmine". The blind
judge graded it **trivia** — the three reviewers were right and the promotion was wrong. Step 5.5
is not correcting reviewers who talked themselves out of a real finding; on the evidence it is
overriding reviewers who dismissed correctly.

### The cost is smaller than this nib assumed

The `# Why` above says the channel "costs output in every agent plus orchestrator thinking". The
first half is minor: CBNF sections are 19.8% of sub-agent *report* text but only **~1.3% of a run's
367k output tokens** (~4.7k tokens/run). (Restated 2026-07-29 — the 260.8k denominator came from a
stale `ws_output` that undercounted every tool by 35-49%; see #dcc-9q01.) Removing the reviewer-side section would not move the
$21.33/run figure.

The orchestrator side is unmeasured and is the real unknown — Step 5.5 reads all 49.5 bullets and
reasons over them inside the consolidation step, where thinking is 60–77% of orchestrator output
(#dcc-e0wj workstream 2). Nothing here isolates that share, so **a cost-based case for removal
cannot be made from this analysis.**

### What follows

Per the rule, the keep/drop call moves to the product question in **#dcc-e0wj workstream 3**. Two
things worth carrying there:

- The recovery is real but lands entirely in the suggestion tier. If the product answer is "ours is
  a breadth tool whose valid-minor tier is the differentiator", the channel is contributing to
  exactly that tier and should stay.
- If instead the answer is "ours must get its top-of-list trustworthy", note that Step 5.5 runs
  **before** the validation wave and promoted items are ranked like any other finding — the
  subject-9 nil-deref is a promoted item that outranked three explicit dismissals. That interacts
  directly with the severity-contract work in workstream 1 (#dcc-hmp6 restated ours' calibration to
  0.70) and is a cheaper lever than deleting the channel.

### Method and limits

`analysis/scripts/cbnf_yield.py` finds *candidates* deterministically — consolidated-report clusters
with no same-run sub-agent flag, which is the only shape a Step 5.5 promotion can take — and
`analysis/cbnf-adjudication.json` records the read of each against that run's actual CBNF bullets.
11 candidates, 7 adjudicated as promotions.

- A token-containment score was tried as the decision rule and **rejected**: at 0.5 it identified 2
  of the 7, and at 0.3 it admitted 2 non-promotions while still missing 2 real ones. It survives in
  the output only as a pointer to the nearest bullet.
- Step 5.5 rule 2 ("A dismissed it, B flagged it → include") is invisible to this method by
  construction, and deliberately so: B's flag would have carried the finding anyway, so that path is
  not incremental recovery.
- **Undercount risk.** If clustering merged a promoted item with a nearby sub-agent finding, the
  promotion is hidden. Not ruled out; it would move the count, not the finding that none of the
  promotions were substantive.
- Four candidates were adjudicated *not* promotions (no CBNF antecedent) — all in subject 9 repeat
  2, the largest run. Those are orchestrator-originated findings, which is a separate channel.

## Summary

**Third branch of the pre-set rule: a suggestion amplifier, not a safety net.** Step 5.5 promotes
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
