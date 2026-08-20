---
# dcc-8dtt
version: 1
title: 'cost_per_real_finding penalizes repeats: total cost over a deduplicated pooled denominator'
status: completed
type: bug
created_at: 2026-08-20T17:14:06Z
updated_at: 2026-08-20T19:47:54Z
parent: dcc-ho2w
order: zzz
---

`tools[arm].cost_per_real_finding` divides the arm's **total** cost by its **deduplicated pooled**
real-cluster count. The numerator scales linearly with the number of cells; the denominator barely
moves, because repeats of the same arm find largely the same clusters — which is the whole reason
repeats are run. The metric therefore gets worse the more times an arm is run, independently of the
tool's actual cost-effectiveness.

## Measured on PostHog-posthog-55149 ([[dcc-fm7x]])

| arm | cells | total $ | $/cell | real | `cost_per_real_finding` | per-cell normalized |
|---|---|---|---|---|---|---|
| `ours-review` | 2 | 101.03 | 50.51 | 37 | **2.73** | 1.365 |
| `ours-audit` | **1** | 44.43 | 44.43 | 40 | **1.11** | 1.111 |
| `ours-bugs` | 2 | 20.12 | 10.06 | 16 | 1.26 | 0.629 |
| `superpowers` | 2 | 12.80 | 6.40 | 24 | 0.53 | 0.267 |

`review` looks 2.5x worse than `audit` on the emitted metric. Per cell it is 23% worse. Almost the
entire gap is that `review` ran twice and `audit` once — a scheduling decision, not a property of
either tool.

## Why this is not confined to one subject

Repeat counts are uneven across the whole corpus by design and by accident: `ours-review` has 5 cells
on prometheus and on efcore against 2 for most arms, retired arms have 3-6, and probe cells add more.
Any cross-arm cost ranking built on this field silently rewards the arms that happened to run fewest
times. It was surfaced here only because a reader asked why one arm cost twice another — the number is
not self-evidently wrong on its face, which is what makes it dangerous.

## Fix

- Report cost **per cell** alongside any arm total, and never present an arm total next to per-arm
  quality figures without the cell count in the same table.
- Replace or supplement the field with a repeat-invariant form. The honest version needs per-cell real
  attribution: mean over cells of (cell cost / real clusters that cell contributed), which measures
  "what one run of this tool costs per real finding" and does not move when repeats are added.
- Until then, emit `n_cells` inside each arm's block so the field cannot be read without it, and mark
  `cost_per_real_finding` as repeat-dependent in `METRICS.md`.

## Acceptance

- [ ] Each arm's metrics block carries its own `n_cells`
- [ ] A repeat-invariant cost metric exists, or the existing one is documented as repeat-dependent
      everywhere it is rendered
- [ ] `analysis/` write-ups and the interactive report ([[dcc-p3wg]]) show cost per cell, not only totals
- [ ] Any existing cross-arm cost claim re-checked against unequal cell counts

## Summary

**Completed 2026-08-20** — Each arm's block now carries `n_cells`, `cost_per_cell`, a repeat-invariant
`cost_per_real_finding_per_cell` (mean over cells of cell cost / real clusters that cell
contributed), and `cost_per_real_finding_repeat_dependent: true` beside the original field, which is
kept because it answers a real question — total spend — and only misleads when read without its
divisor.

Reproduces the nib's table: on PostHog-55149 `ours-review` is 2.73 against `ours-audit`'s 1.11 on the
repeat-dependent form and 1.77 against 1.11 on the invariant one, so most of the 2.5x gap was the
extra repeat. Documented in METRICS.md with the rule that the field is never rendered without
`n_cells` in the same table.
