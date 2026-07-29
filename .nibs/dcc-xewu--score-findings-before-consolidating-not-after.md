---
# dcc-xewu
version: 1
title: Score findings before consolidating, not after
status: deferred
type: feature
priority: normal
estimate: l
tags:
    - code-review
created_at: 2026-07-28T20:41:05Z
updated_at: 2026-07-29T11:46:05Z
parent: dcc-hyxw
order: "n"
---

# Why

Ours consolidates **everything** (Step 5), validates afterwards (Step 5.6), then suppresses via
the confidence gate. So the orchestrator spends frontier-model thinking on findings it is about
to discard — and orchestrator thinking is 60% of orchestrator output on a small subject, 77% on
a large one.

Anthropic inverts the order: a **Haiku** agent scores every issue against a 0–100 rubric and
everything below 80 is discarded **before** its orchestrator does any real reasoning. On a
discrete 0/25/50/75/100 ladder that means only findings scored exactly 100 survive. It posts the
study's best calibration (0.90, 9/10, vs ours' 0.70, 21/30) at half the cost.

Same insight, opposite order — and the order is where the cost difference lives.

# What to change

Move a cheap scoring pass ahead of consolidation. The prize is not only the thinking saved: a
pre-consolidation pass could **absorb** the validation wave (17.3% of sub-agent output) rather
than adding to it — one cheap pass over raw findings instead of an expensive pass over
consolidated ones.

This is simultaneously #dcc-e0wj workstream 1's calibration lever: an early cheap filter is what
makes a trustworthy top-of-list possible. The two workstreams converge here.

# Blocked on a product decision

A hard pre-filter is a **commitment to the "short trustworthy list" product**. If the intended
product is exhaustive coverage with explicit tiers, aggressive early filtering is the wrong
change — the valid-minor findings it would discard are precisely what a fix-and-rerun loop
consumes, and ours currently produces 4.8 of them per run against anthropic's 2.1.

Resolve #dcc-e0wj workstream 3's first item — *"a short trustworthy list, or exhaustive coverage
with tiers?"* — before starting. Do not treat this nib as ready until that is answered.

# Risk

High. This changes the skill's spine: dispatch → consolidate → validate → gate is the structure
every downstream skill's expectations are built on, including `auto-code-review`'s triage table,
which keys on severity × anchor × validated-flag. A finding that never reaches consolidation has
no anchor, so the whole downstream contract has to be re-checked.

# Acceptance

- [ ] [manual] Product decision recorded first (#dcc-e0wj workstream 3), and this design
      re-confirmed as the right change under it
- [ ] [run] `rg -n "Step 5" -A15 decaf-quality/skills/code-review/SKILL.md` — expect: the
      scoring pass documented ahead of consolidation, with its model tier stated
- [ ] [manual] Downstream contract re-verified: `auto-code-review` Step 3c and
      `resolve-code-review` Step 2 still receive severity, anchor and validation state for every
      finding they triage
- [ ] [manual] Re-measured on benchmark subjects: calibration against the 0.70 baseline (21/30), cost
      against $21.33/run, and escaped-bug recall against 16/18 — with an explicit judgement that
      recall did not regress

# Notes

Reasoning and measured basis: #dcc-e0wj → `# Candidate interventions` → item 2.
