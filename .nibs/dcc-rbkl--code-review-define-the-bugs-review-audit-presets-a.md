---
# dcc-rbkl
version: 1
title: 'code-review: define the bugs / review / audit presets and wire them into the auto loops'
status: in-progress
type: feature
priority: high
estimate: m
tags:
    - code-review
created_at: 2026-07-29T18:29:16Z
updated_at: 2026-07-29T19:04:21Z
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

- [x] [run] `rg -n "bugs|review|audit" -A6 decaf-quality/skills/code-review/SKILL.md` — expect: the
      three presets defined as axis settings, each stating its deliverable
- [x] [run] `rg -n "preset" decaf-quality/skills/auto-code-review/SKILL.md` — expect: the loop
      selects a preset per iteration, with the narrowing rule stated
- [x] [run] `rg -rn "code-review with arguments" decaf-build/skills/*/SKILL.md` — expect: every
      pass-through updated or explicitly confirmed compatible
- [ ] [manual] Running each preset on one real changeset produces visibly different reports, and
      each matches its stated deliverable
- [x] [manual] The Step 2b.5 shed order differs by preset — rank by drop cost for `bugs`/`review`,
      by drop cost **+** minor yield for `audit`, so `consistency-reviewer` does not lead the cut
      when the suggestion tier is part of the deliverable. Moved here from #dcc-2a8i, which could
      not satisfy it before presets existed

# Notes

Depends on all four axes existing. Blocked by #dcc-evph, #dcc-1x90, #dcc-jt58, #dcc-xewu.

## Done 2026-07-29

**Presets are now the primary interface**, named for what they deliver rather than how hard they
try — `bugs` / `review` / `audit`, each a point in the four-axis space, each axis still overridable
after it (`review models=high`, `audit roster=8`).

The legacy ladder is retained as aliases that resolve before anything runs: `mid` → `review`,
`high` → `review models=high`, `max` → `audit`, `modeN` → `+ roster=N`. `tools.json` and every
existing invocation keep working.

**`low` needed an explicit axis override, and that is worth knowing.** It resolves to
`bugs roster=2 evidence=norm` — not plain `bugs`. With two reviewers corroboration is scarce, and
`evidence=strong` would demand a lone reviewer score ≥80 unaided, emptying the report on the one
mode whose purpose is fast feedback. A preset is a default, not a straitjacket, and this is the case
that proves it.

**The audit shed order landed** (the criterion moved here from #dcc-2a8i). Under `bugs`/`review`,
Step 2b.5 ranks by substantive drop cost, shedding `consistency` and `knowledge` first. Under
`audit` it ranks by drop cost **plus** minor yield — `consistency` moves to mid-table and
`test-reviewer` rises to first, because ranking `audit` by substantive drop cost alone would cut
exactly the personas it was chosen for.

**Auto-loop integration.** `auto-code-review` now picks a preset per iteration rather than reusing
one:

- iteration 2: `review roster=4|6|uncapped reach=narrow`, by fix-delta size
- iteration 3+: `bugs roster=3`, scoped to the newest delta

`reach=narrow` on every re-review matters more than the roster does: the first pass already reported
what the surrounding code lacks, and a later pass re-reporting the same absences is noise triage has
to reject again each round. **`audit` is never inherited into a re-review** — otherwise every
iteration re-surfaces the whole backlog and the loop cannot converge.

Pass-throughs updated in `auto-dev`, `auto-tdd`, `batch-dev` and `auto-deliver`, which were still on
the pre-legacy `quick|std|max` spelling. Examples updated across both READMEs and the internal
callers in `resolve-code-review` and `resolve-refactor`.

### Unverified

Every axis value in the preset table is a first estimate. The presets are the unit #dcc-gxuk
measures; the cross-product is not and never will be.
