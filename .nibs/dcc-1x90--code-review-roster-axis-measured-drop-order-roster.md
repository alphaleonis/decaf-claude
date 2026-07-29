---
# dcc-1x90
version: 1
title: 'code-review: roster axis — measured drop order, roster scaled to changeset size'
status: todo
type: feature
priority: high
estimate: m
tags:
    - code-review
created_at: 2026-07-29T18:29:16Z
updated_at: 2026-07-29T18:30:12Z
parent: dcc-9q01
blocked_by:
    - dcc-evph
order: aV
---

# Why

When a `roster` cap forces a choice among gate-matched personas, Step 2b.5 ranks them by a
hand-written category rule. #dcc-2a8i measured that rule against the 18 archived runs and found it
wrong in two specific ways and right in one.

# What to change

`decaf-quality/skills/code-review/SKILL.md` Step 2b.5:

1. **`adversarial-reviewer` moves ahead of `security-reviewer`** and into the top specialist slot.
   It is the most load-bearing specialist measured — 1.85 drop cost per run over 13 runs, 10
   sole-found substantive clusters, and rank 1-2 under every leave-one-out jackknife. The current
   rules place it mid-tier and explicitly behind security. **This is the one change the data
   supports confidently.**
2. **Split the ranking by evidence quality, not by category alone.** Personas dispatched in >= 12
   runs have stable measured drop cost (swing <= 4 ranks); those in <= 6 runs swing up to 13. So:
   rank the well-sampled personas by measurement, and keep category ranking for the rarely-firing
   specialists — their gate is the evidence of fit, and there is no usable measurement.
   **Do not promote `security-reviewer` on its n=3 figure**, which tops the table and swings 13.
3. **Scale the default roster with changeset size.** Drop cost is ~0 on small diffs — most personas
   contribute nothing another persona did not also find — and rises steeply with size
   (`adversarial` 0.50 → 1.50 → 3.20 across small/medium/large). A tight cap on a small diff is
   nearly free; on a large one it is expensive. A fixed `N` gets this backwards at both ends.
4. **Preset-dependent shed order.** `consistency-reviewer` has 0.00 substantive drop cost but
   yields 1.6 valid-minor per run: shed it first under `bugs`, not under `audit`. Rank by drop
   cost for `bugs`/`review`, by drop cost **+** minor yield for `audit`.
5. **State the provenance and date of the ordering**, and that it is refreshable from
   `analysis/scripts/roster_yield.py`. The current rule went wrong because it was folk knowledge.

The floor stays `broad` + `quick` — justified by the `evidence` screen needing an agreement signal
to score with (#dcc-xewu), not by `quick`'s solo value, which is 0.24/run with zero unique findings.

# Acceptance

- [ ] [run] `rg -n "Rank the gate-matched specialists" -A15 decaf-quality/skills/code-review/SKILL.md`
      — expect: order stated as measured drop cost with its provenance, not as agent category
- [ ] [run] `python3 competition/benchmark/analysis/scripts/roster_yield.py` — expect: exit 0; the
      figures the ranking cites are reproducible from committed data
- [ ] [manual] `adversarial-reviewer` ranks ahead of `security-reviewer`
- [ ] [manual] Personas below the n>=12 stability threshold are ranked by gate, not by figure
- [ ] [manual] Default roster scales with changeset size, or the decision to keep a fixed `N` is
      recorded against the size table

# Notes

Measurement and its limits: **#dcc-2a8i** (child of this nib).
