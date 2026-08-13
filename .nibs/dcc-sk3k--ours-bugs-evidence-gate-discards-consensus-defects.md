---
# dcc-sk3k
version: 1
title: ours-bugs' evidence gate discards consensus defects
status: todo
type: bug
priority: high
created_at: 2026-08-13T09:36:56Z
updated_at: 2026-08-13T09:37:25Z
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
