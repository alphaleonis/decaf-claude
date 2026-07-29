---
# dcc-jt58
version: 1
title: 'code-review: reach axis — what counts as reportable'
status: todo
type: feature
priority: normal
estimate: m
tags:
    - code-review
created_at: 2026-07-29T18:29:16Z
updated_at: 2026-07-29T18:30:51Z
parent: dcc-9q01
blocked_by:
    - dcc-evph
order: ak
---

# Why

`reach` is the axis the tool we benchmarked against does not have, and its absence is the clearest
defect in that design. Anthropic's skill puts *"pre-existing issues"* and *"lack of test coverage"*
in the same false-positive list as *"something that looks like a bug but is not"*. The first two are
**scope** judgements; the third is a **confidence** judgement. Same bucket, different questions.

That conflation is also why its precision looks so good — it never emits the categories that dilute
ours, so they cannot count against it.

The case that forces the split: an autonomous fix loop wants `reach=wide` (pre-existing defects
count, because nothing else will find them) with `evidence=strong` (do not hand the fixer hunches).
No single dial expresses that.

# What to change

Define what each `reach` value admits, and make reviewers honour it:

| value | admits |
|---|---|
| `narrow` | defects introduced by the changed lines only |
| `norm` | the above, plus issues in code the change directly touches or relies on |
| `wide` | the above, plus pre-existing defects, testing gaps, doc gaps, residual risks |

The report structure mostly exists already — Findings / Minor Findings / **Pre-existing Issues** /
**Testing Gaps** / **Residual Risks** are separate sections today, and `auto-code-review` already
refuses to triage the last three. So this is largely about whether reviewers *generate* those
tiers, not about new report plumbing.

# The open question this nib must answer first

**Does `reach=wide` mean reviewers generate more, or that the report stops suppressing what they
already generate?** The cost differs enormously — generating more means more reviewer output on
every run; suppressing later means paying for it regardless. Decide before implementing, and record
which.

# Acceptance

- [ ] [manual] The generate-vs-suppress question above is answered and recorded
- [ ] [run] `rg -n "reach" -A10 decaf-quality/skills/code-review/SKILL.md` — expect: the three
      values defined by what they admit, not by prose adjectives
- [ ] [run] `rg -ln "reach" decaf-quality/agents/*.md` — expect: reviewer briefs reference the axis
      wherever their scope depends on it (pre-existing, coverage, docs)
- [ ] [manual] `auto-code-review` and `resolve-code-review` still receive the tier structure they
      triage on — the Minor/Consistency bucket must survive `reach=norm`
- [ ] [manual] `reach=narrow` verified not to drop a finding class those two skills depend on
