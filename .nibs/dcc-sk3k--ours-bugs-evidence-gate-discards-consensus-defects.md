---
# dcc-sk3k
version: 1
title: ours-bugs' evidence gate discards consensus defects
status: todo
type: bug
priority: high
created_at: 2026-08-13T09:36:56Z
updated_at: 2026-08-13T11:40:01Z
parent: dcc-hyxw
order: ao
---

## Steps to Reproduce

1. [First step]
2. [Second step]
3. [Observed behavior]

## Expected vs Actual

**Expected:** [What should happen]
**Actual:** [What happens instead]

## Root Cause

[Analysis of why the bug occurs, filled in during investigation]

Measured in the v2 pilot ([[dcc-vkeh]], `v2/analysis/TUNING-SIGNALS.md`), across two subjects at two
repeats each, blind-adjudicated twice.

`ours-bugs` **found 40 clusters and reported 7**. Of the 33 it suppressed, **7 were graded real** — a
21% demotion loss. It discarded as many real findings as it published.

The comparison that localizes the fault: `ours-audit` demoted 50 and lost 8%; `ours-review` demoted 46
and lost 7%. Both suppress more in absolute terms and lose roughly a third as much proportionally, so
**the shared demotion mechanism is sound** and the defect is the `bugs` preset's own threshold.

## What it threw away

Not marginal calls. Every one was reported by four to six other tools:

| severity | finding | other tools reporting it |
|---|---|---|
| high | the when-clause result was already simplified under the assumption the rewrite deletes | 4 |
| high | `Coalesce` admitted by the unfiltered operator recursion | 4 |
| high | all five new tests positive; none covers the shape the optimization breaks | 6 |
| medium | subquery per-step attribution folds out-of-window steps onto step 0 | 4 |
| medium | `MergeSamplesReadFromSubquery` merges positionally on an unstated precondition | 4 |
| low | null-forgiving `func.Instance!` on an invariant nothing enforces | 4 |
| low | vacuous `GreaterOrEqual(SamplesRead, 0)` API assertion | 6 |

## Why it matters beyond precision

- **cost**: $34.60 for 5 real findings — $6.92 each, the worst in the roster
- **thread recall 0.05** — the lowest of seven tools; it agrees with expert human reviewers almost never
- **zero unique real findings** — nothing it surfaced was missed by the rest of the field
- it never cleared the ten-cluster publication floor on either subject, so it has **no precision
  figure at all**; this finding rests on demotion counts, which need no ratio

## Direction

The gate is doing its job on genuinely weak candidates — only 2 of its reported clusters were
non-substantive, and both were `low`. The problem is the threshold's *position*, not its existence.
A candidate corroborated by multiple independent reviewers should not be reachable by it; corroboration
is evidence, and the gate appears to weigh only per-finding confidence.

## Acceptance

- [ ] Identify which gate (`evidence`, the confidence screen, or the preset's `reach`) rejected those
      seven, from the cells' own reports — all fourteen are committed under `v2/runs/`
- [ ] Decide the change, recorded with reasoning
- [ ] Re-measure on the same two subjects and show the demotion loss falls without plain precision
      falling below the `audit`/`review` band


---

## The class axis changes the `ours-bugs` diagnosis (2026-08-13, [[dcc-opdr]])

All 267 clusters were backfilled with a judge-assigned `finding_class` from a closed set, graded
blind to tool identity **and blind to the verdict** — class and substance are meant to be orthogonal,
and showing the grader "this was trivia" would pull the classification style-ward.

### `ours-bugs` is doing its job in composition, and failing it in reach

What each tool **reports**, by class, both pooled subjects, counts:

| tool | defect | risk | test-gap | docs | design | style | total |
|---|---|---|---|---|---|---|---|
| `ours-audit` | 20 | 8 | 21 | 8 | 14 | 7 | 78 |
| `pr-review-toolkit` | 14 | 2 | 13 | 11 | 10 | 4 | 54 |
| `superpowers` | 13 | 2 | 12 | 8 | 8 | 2 | 45 |
| `ours-review` | 12 | 2 | 9 | 5 | 9 | 2 | 39 |
| `comprehensive-review` | 11 | 4 | 6 | 7 | 12 | 1 | 41 |
| **`ours-bugs`** | **6** | 0 | 0 | 0 | 1 | 0 | **7** |
| `anthropic-code-review` | 5 | 0 | 2 | 2 | 2 | 0 | 11 |

**`ours-bugs` has by far the purest defect focus in the roster** — 6 of its 7 reported findings are
defect-class. Every other tool sits between 26% and 45%. The preset is not confused about what it is
for, and its low volume is a design choice rather than a malfunction.

### But it is the worst defect-finder among decaf's presets

Against the 16 real defect-class clusters the whole roster found:

| tool | defects found | reported | **suppressed** | defect recall |
|---|---|---|---|---|
| `ours-audit` | 13 | 13 | **0** | 81% |
| `pr-review-toolkit` | 12 | 12 | 0 | 75% |
| `comprehensive-review` | 10 | 10 | 0 | 62% |
| `ours-review` | 10 | 9 | 1 | 56% |
| `superpowers` | 9 | 9 | 0 | 56% |
| **`ours-bugs`** | **8** | **5** | **3** | **31%** |
| `anthropic-code-review` | 6 | 5 | 1 | 31% |

`ours-bugs` **found eight real defects and reported five.** Its defect recall is the lowest of any
decaf preset — 31% against `ours-audit`'s 81% — and a third of that shortfall is self-inflicted: it
detected three more and binned them.

`ours-audit` is the counter-example that localizes the fault precisely: it suppressed 4 real findings
and **not one was a defect** (2 risk, 2 design). Its gate is correctly calibrated for correctness. So
decaf's demotion machinery *can* protect defects; the `bugs` preset's threshold does not.

### The restated conclusion

The earlier framing — "21% demotion loss" — understated it and pointed at the wrong lever. The
sharper statement is:

> The preset whose sole purpose is finding correctness flaws has the lowest defect recall of decaf's
> three presets, and it discards three of the eight real defects it manages to find.

Purity is not the problem. Reach is, and the gate is making reach worse.
