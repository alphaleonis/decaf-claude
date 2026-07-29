---
# dcc-3fl5
version: 1
title: Price the Considered-But-Not-Flagged channel (analysis only, no re-runs)
status: todo
type: research
priority: high
estimate: s
tags:
    - code-review
created_at: 2026-07-28T20:41:05Z
updated_at: 2026-07-29T11:24:12Z
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

- [ ] [run] `python3 competition/benchmark/analysis/scripts/cbnf_yield.py` — expect: exit 0,
      one row per archived `ours` run with promoted-finding counts and their graded verdicts,
      plus a total
- [ ] [run] `python3 competition/benchmark/analysis/scripts/cbnf_yield.py --json` — expect:
      exit 0, machine-readable output for the synthesis page
- [ ] [manual] Verdict recorded against the decision rule above, with the promotion count and
      what those promotions were judged to be. `[manual]` because the call is a judgement on a
      measured number, not the number itself.

# Notes

Reasoning and measured basis: #dcc-e0wj → `# Candidate interventions` → item 5.
