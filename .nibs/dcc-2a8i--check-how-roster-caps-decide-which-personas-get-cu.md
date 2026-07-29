---
# dcc-2a8i
version: 1
title: Check how roster caps decide which personas get cut, and whether that ranking is optimal
status: draft
type: task
created_at: 2026-07-28T23:33:37Z
updated_at: 2026-07-29T11:24:12Z
parent: dcc-hyxw
order: az
---

`code-review`'s Step 2b.5 resolves a `midN`/`highN` cap by keeping the floor plus the
highest-ranked gate-matched specialists, ranked by a hand-written rule set: categorical
coverage first (stack reviewer, data-migration, prior-feedback, spec-compliance), then the
changeset's primary risk dimension, with `knowledge-reviewer` and `consistency-reviewer`
explicitly "ranked last" as the first to shed.

That ranking was written from intuition. There is now measured per-persona data
(`analysis/scripts/roster_yield.py`) to check it against, and at least three places where
it looks wrong:

- `adversarial-reviewer` returns 40 substantive clusters at 8,138 tok each — the best value
  at scale in the roster — but it is not in the rules' top tier.
- `consistency-reviewer` is ranked to shed first, yet it produces 28 valid-minor clusters
  and 18 sole-useful ones. It is a suggestion engine, so whether shedding it first is right
  depends on the product question in #dcc-e0wj workstream 3.
- `go-reviewer` is a stack reviewer and therefore ranked in the top tier, but it has the
  roster's worst signal share (50%).

Also worth checking: the cap counts the floor but excludes validators, so a cap bites only
the ~9.4-reviewer wave. And ranking happens per changeset, so "optimal" means optimal given
the Step 2a classification, not globally.

## Context

Captured while re-analysing benchmark subjects 2 and 3 after the #dcc-9kkz contamination
fix. The per-persona value/cost table came out of #dcc-e0wj workstream 2, which found no
persona is dead weight on participation — which is precisely why *ordering* matters: if
nothing is droppable outright, the cap's drop order becomes the real lever.

Related: #dcc-1xtt (gate tuning — which personas are dispatched at all) is the sibling
question; this one is about what happens once a cap forces a choice among those dispatched.
