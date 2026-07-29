---
# dcc-jt58
version: 1
title: 'code-review: reach axis — what counts as reportable'
status: completed
type: feature
priority: normal
estimate: m
tags:
    - code-review
created_at: 2026-07-29T18:29:16Z
updated_at: 2026-07-29T18:47:52Z
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

- [x] [manual] The generate-vs-suppress question above is answered and recorded
- [x] [run] `rg -n "reach" -A10 decaf-quality/skills/code-review/SKILL.md` — expect: the three
      values defined by what they admit, not by prose adjectives
- [x] [run] `rg -ln "reach" decaf-quality/agents/*.md` — expect: reviewer briefs reference the axis
      wherever their scope depends on it (pre-existing, coverage, docs)
- [x] [manual] `auto-code-review` and `resolve-code-review` still receive the tier structure they
      triage on — the Minor/Consistency bucket must survive `reach=norm`
- [x] [manual] `reach=narrow` verified not to drop a finding class those two skills depend on

## Done 2026-07-29

### The open question, answered

**Both — and which one depends on the dimension.** That distinction is the useful part:

- **Absences are a dispatch-side saving.** Hunting for a missing test or an undocumented decision is
  a separate search activity, so `narrow` genuinely spends less. This is where the money is: `test`
  is the largest finding category ours produces (41 clusters across the benchmark) for 6 substantive
  ones, and `test-reviewer` has the roster's worst tokens-per-substantive.
- **Pre-existing is a reporting rule, not a saving.** A reviewer cannot know a defect is pre-existing
  without analysing it. `reach` only decides whether that analysis reaches the report — so `narrow`
  cuts *reading*, not cost, on this axis.

### What shipped

`reach=<narrow|norm|wide>` is settable, and modes map onto it (`low`→narrow, `mid`/`high`→norm,
`max`→wide). It acts in three places:

1. **Dispatch** — a `## Review reach` block in the base context tells reviewers what to hunt. One
   place, not fifteen; agents stay reach-agnostic the way they are model-agnostic.
2. **Consolidation** — Step 5 rule 7 routes pre-existing findings by reach: dropped to Considered
   But Not Flagged under `narrow`, the informational section under `norm`, **promoted to primary
   findings under `wide`**.
3. **Report** — Pre-existing Issues, Testing Gaps and Residual Risks sections are present or absent
   by reach, each saying so inline.

The seven agents whose scope includes absences got a short `## Review reach` section so their briefs
do not contradict the dispatch directive, with `norm` as the fallback when no directive is present.

### The interaction worth knowing

Under `reach=wide`, `auto-code-review` now **triages and fixes pre-existing defects**. Its standing
rule is that the loop fixes the change under review, not the backlog — that rule now yields to an
explicit `wide`, because an autonomous loop is often the only reader that code will get. This is the
vibe-coding case the axis exists for, and it only fires when `wide` was chosen explicitly or came
from a preset implying it. Never by default.

### Grounding

Ours' findings by category over the benchmark, which is what makes `narrow` worth having:

| category | clusters | substantive |
|---|---|---|
| test | 41 | 6 |
| design | 37 | 6 |
| logic | 28 | 18 |
| style | 22 | **0** |
| doc | 20 | 1 |
| bug | 17 | 11 |

`logic`+`bug` are 45 clusters for 29 substantive findings; `test`+`design`+`style`+`doc` are 120
clusters for 8. Unverified until #dcc-gxuk, and note that narrowing does cost something — those 8
are real findings that `narrow` will not surface.

## Summary

`reach=<narrow|norm|wide>` is settable and acts in three places: a dispatch-side block telling
reviewers what to hunt, Step 5 routing of pre-existing findings, and report-section gating. Modes
map onto it (low→narrow, mid/high→norm, max→wide).

The open question is answered, and the answer is that it is two different mechanisms. Absences
(missing tests, undocumented decisions) are a dispatch-side saving, because hunting for them is a
separate search activity — that is where the money is, since `test` is the largest category ours
produces for the fewest substantive findings. Pre-existing defects are a reporting rule and save
nothing, because you cannot know a defect is pre-existing without analysing it.

Interaction worth knowing: under `reach=wide` auto-code-review now triages and fixes pre-existing
defects. Its standing "fix the change, not the backlog" rule yields to an explicit wide, because an
autonomous loop is often the only reader that code gets. Never fires by default.

Implemented in the orchestrator rather than across fifteen agents; the seven whose scope includes
absences carry a short note so their briefs do not contradict the dispatch directive.
