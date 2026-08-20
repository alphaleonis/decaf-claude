---
# dcc-sfny
version: 1
title: The valid-other/trivia boundary has no pre-registered floor, and sits on 0.60
status: completed
type: bug
priority: high
created_at: 2026-08-20T18:42:57Z
updated_at: 2026-08-20T19:25:53Z
parent: dcc-ho2w
order: zzzs
---

`judge_stability.py` pre-registers two floors — `real_vs_not.kappa >= 0.60` and
`exact_agreement >= 0.70`. Neither is the boundary the design says carries the metric. Its own
docstring:

> `trivia` versus `valid-other` is the load-bearing subjectivity in this design. v1 put 58 of 98
> clusters in `nitpick` and only 6 in `false-positive`, so that boundary **is** the metric.

It computes `valid_other_vs_trivia_boundary` and holds it to nothing.

## Measured 2026-08-20

| | prometheus calibration (n=10) | PostHog, two full passes (n=62 on the boundary) |
|---|---|---|
| `valid_other_vs_trivia` kappa | 0.403 | **0.598** |
| agreement | 0.60 | 0.758 |
| `real_vs_not` kappa | 0.732 | 0.907 |
| `exact_agreement` | 0.733 | 0.852 |
| `matches_thread` same index | 3/3 | **24/24** |

Both runs report `stable: true`, because the floors that exist are the ones the judge clears.

Read the two columns together. **`real_vs_not` is strong (0.907) and thread matching is perfectly
reproducible (24/24).** The instability is confined to exactly one call — is a correct observation
worth a reader's attention — and that call decides `precision`, since `precision` counts REAL and
excludes `valid_minor`, while `trivia` counts as noise. So arm *rankings* are safe and precision
*levels* inherit a boundary sitting on its floor at n=62 and under it at n=10.

Also worth noting the raw spread: PostHog's two passes assigned `false-positive` **7 times versus 2**
over the same 108 clusters. The verdict most likely to be quoted as "this tool was wrong" is the least
reproducible one.

## What to do

Options, roughly by cost:

1. **Pre-register a floor for this boundary too**, and report `stable` per-boundary rather than as one
   flag. A run that clears the coarse collapse and fails the boundary is not "stable" for a precision
   figure, and today it says it is.
2. **Sharpen the rubric at that one line.** The current instruction is a paragraph of prose. It needs
   decision rules with worked examples drawn from already-graded clusters — cheapest intervention with
   a real chance of moving the number.
3. **Three graders, majority vote, on the boundary cases only.** The other verdicts do not need it:
   `real_vs_not` at 0.907 and thread matching at 24/24 are already reproducible. Cost scales with the
   ~60% of clusters that touch this line, not with the whole pool.
4. **Publish precision as a band, not a point** — from the two passes already run — so the figure
   carries its own reproducibility.

## Done 2026-08-20

Options 1 and 2 taken; option 4 follows from them as a reporting consequence. Option 3 (three graders
on boundary cases) is NOT done and is the remaining lever if the band is too wide to be useful.

- `BOUNDARY_KAPPA_FLOOR = 0.60` and `BOUNDARY_MIN_N = 50` in `judge_stability.py`, alongside the two
  existing floors, all three pinned by `t_thresholds_are_the_documented_ones`.
- `stable` split into `stable_for_rankings` (the two coarse floors) and
  `stable_for_precision_levels` (those plus the boundary), with a per-check `checks` block and a
  `stable_reason` string. `passes: null` on the boundary means UNESTABLISHED — under n=50 the figure
  is not a measurement, and that is not the same as a failure. The CLI prints the reason to stderr
  whenever precision levels are not licensed.
- Rubric: `scoring/prompts/verdict-rubric.md` is now the single canonical copy (both
  `foldin-blind-grader.md` and `/bench-analyze` hand it over verbatim; they carried two paraphrases
  that had already drifted). It replaces the prose paragraph with a four-question walk — asserts a
  defect at all / reachable / anything to do / consequence material — and worked examples of every
  answer taken from graded clusters: `e08`, `ma06`, `gf06`, `im02`, `gf12`, `gf02`, `ma26`, `im03`,
  `e05`, `gf05`, `im07`. The 7-versus-2 `false-positive` spread is recorded there too.
- Under the new floors, both measured runs report `stable: false` with rankings licensed and levels
  not. **PostHog precision is published as a band across both passes**, per the last criterion's
  second branch. The boundary did not clear its floor and this pass did not try to make it.

Write-up: `v2/analysis/GRADING-INTEGRITY-2026-08-20.md` §1.

## Acceptance

- [x] A pre-registered floor exists for `valid_other_vs_trivia_boundary`, written down before the next
      grading run
- [x] `stable` is reported per boundary, not as a single flag that a weak boundary can pass
- [x] The rubric for this one call carries worked examples from real graded clusters
- [x] Either the boundary clears its floor at n>=50, or precision is published as a band with both
      passes shown

## Summary

**Completed 2026-08-20** — Three pre-registered floors instead of two. The valid-other/trivia boundary now has one (kappa >=
0.60 over at least 50 boundary clusters), and `stable` is split into `stable_for_rankings` and
`stable_for_precision_levels`, with an underpowered boundary reporting null rather than false —
unestablished is not failed.

Under the new floors both measured runs report `stable: false` with rankings licensed and levels not,
so PostHog precision publishes as a band across both passes rather than a point.

The rubric for that one call is now a single canonical file (`scoring/prompts/verdict-rubric.md`)
handed to the grader verbatim, replacing two paraphrases that had already drifted. It carries a
four-question decision walk and worked examples of every answer drawn from eleven already-graded
clusters.

Option 3 from the nib — three graders on boundary cases only — was not taken and remains the lever if
the band turns out too wide to be useful.
