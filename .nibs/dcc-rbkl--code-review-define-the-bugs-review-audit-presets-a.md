---
# dcc-rbkl
version: 1
title: 'code-review: define the bugs / review / audit presets and wire them into the auto loops'
status: todo
type: feature
priority: high
estimate: m
tags:
    - code-review
created_at: 2026-07-29T18:29:16Z
updated_at: 2026-07-29T18:30:51Z
parent: dcc-9q01
blocked_by:
    - dcc-evph
    - dcc-1x90
    - dcc-jt58
    - dcc-xewu
order: ac
---

# Why

The axes are the mechanism; presets are the interface. Nobody can pick sensibly among four dials at
three-ish values each — that is a space of ~100 combinations, and the benchmark can measure two or
three. Named presets are what make the design usable and measurable at the same time.

They also answer #dcc-e0wj workstream 3 — *"a short trustworthy list, or exhaustive coverage with
tiers?"* — by making the product a per-run choice rather than a permanent commitment.

# What to change

| preset | roster | models | evidence | reach | the product |
|---|---|---|---|---|---|
| **`bugs`** | small | low | strong | narrow | high-confidence defects in changed lines only |
| **`review`** *(default)* | gate-matched | norm | norm | norm | the above plus actionable minor findings |
| **`audit`** | all matched | high | any | wide | everything, tiered |

**The axis values are a first guess** — nobody knows what `roster: small` should be. #dcc-gxuk
measures them; expect to revise.

Any axis stays individually overridable, per the operator's decision that presets should not be the
only way in.

## Autonomous-loop integration

`auto-code-review` should pick a preset **per iteration** rather than reusing one. Iteration 1 runs
`review`; iterations 2+ narrow `reach` and shrink `roster`, because a fixer re-review wants to
catch what the fix broke, not re-litigate the backlog. This needs no new machinery — the skill
already has delta classification and a `reReviewMode`; it selects a preset instead of a mode.

`auto-tdd`, `auto-dev`, `batch-dev` and `auto-deliver` pass modes through and need their
pass-through updated.

# Acceptance

- [ ] [run] `rg -n "bugs|review|audit" -A6 decaf-quality/skills/code-review/SKILL.md` — expect: the
      three presets defined as axis settings, each stating its deliverable
- [ ] [run] `rg -n "preset" decaf-quality/skills/auto-code-review/SKILL.md` — expect: the loop
      selects a preset per iteration, with the narrowing rule stated
- [ ] [run] `rg -rn "code-review with arguments" decaf-build/skills/*/SKILL.md` — expect: every
      pass-through updated or explicitly confirmed compatible
- [ ] [manual] Running each preset on one real changeset produces visibly different reports, and
      each matches its stated deliverable

# Notes

Depends on all four axes existing. Blocked by #dcc-evph, #dcc-1x90, #dcc-jt58, #dcc-xewu.
