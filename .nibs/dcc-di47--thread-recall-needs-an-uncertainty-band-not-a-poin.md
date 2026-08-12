---
# dcc-di47
version: 1
title: Thread recall needs an uncertainty band, not a point estimate
status: todo
type: task
priority: high
created_at: 2026-08-12T07:12:02Z
updated_at: 2026-08-12T09:51:26Z
parent: dcc-ho2w
order: z
---

Measured on the pilot's first scored subject ([[dcc-vkeh]], prometheus/prometheus#18081 r1). Two
independent blind grading passes over the SAME cells and the SAME 99 clusters moved thread recall by
up to **0.20** per tool, while precision moved at most 0.11 and kept its ranking.

| axis | max delta across passes | ranking |
|---|---|---|
| precision | 0.11 | stable (one adjacent swap between tools 0.01 apart) |
| thread recall | 0.20 | `pr-review-toolkit` 0.60 -> 0.40 |

## Why, precisely

Not judge sloppiness — the judge cleared every pre-registered stability floor (exact agreement 0.889,
real/not-real kappa 0.78). It is quantization plus shared credit:

- 10 human threads means each is worth 0.10 of recall.
- A thread is credited to every tool in the cluster the judge matched it to. Pass 1 matched thread 6
  to `c05`, raised by three tools; pass 2 matched the same thread to `c41`, raised by one. The thread
  was covered under both passes. Three tools gained or lost 0.10 on a single adjudication call that
  did not change whether the thread was found at all.

`threads.human_axis_thin` fires only at 1-2 human threads. This subject has 10 — the densest citable
cell in the corpus — and still moves this much. Every other citable subject has fewer, so the problem
is corpus-wide, not specific to a thin cell.

## What to do

Options, to be decided before any thread-recall figure is published:

1. **Report a band, not a point.** Grade every subject twice (already required for stability) and
   publish thread recall as the range across passes, per tool. Cheapest, and the data already exists.
2. **Grade the thread axis N>=3 times** and report median with spread. More expensive; each pass is a
   full adjudication.
3. **Credit threads to clusters, not tools** — report which threads were covered by the pool at all
   (stable across passes here: 8 vs 7) separately from per-tool attribution (unstable). The corpus
   miss detector is the defensible number; per-tool thread recall may simply not be one.

Option 3 deserves the most thought: `missed_by_every_tool` barely moved, and that is the axis
METHODOLOGY-v2 section 2 actually justifies the thread set for. Per-tool attribution was never the
stated purpose.

## Acceptance

- [ ] Decide which treatment thread recall gets, recorded with the reasoning
- [ ] `score_pooled.py` emits it that way, with a guard against a bare point estimate if that is the decision
- [ ] `scoring/README.md` and `/bench-analyze-v2` describe the chosen treatment


## Broadened after the second subject (2026-08-12): BOTH axes, not just thread recall

The original framing above came from prometheus alone, where precision moved 0.11 across two grading
passes and thread recall moved 0.20. **Efcore shows the reverse** — precision 0.14, thread recall
0.10 — so "precision is robust, recall is not" was a one-subject generalization and it is wrong.

| subject | max delta precision | max delta thread recall | precision ranking stable |
|---|---|---|---|
| prometheus/prometheus#18081 | 0.11 | 0.20 | no (one adjacent swap) |
| dotnet/efcore#34127 | 0.14 | 0.10 | no |

Both axes move 0.10-0.20 between independent grading passes of the SAME cells and the SAME clusters,
and the precision ranking changed on both subjects. The judge itself is stable — it cleared every
pre-registered floor on both subjects, and comfortably (exact agreement 0.889 and 0.929) — so this is
not a grader-quality problem. It is that per-tool metrics computed over 10-60 clusters are simply
sensitive to a handful of individual calls.

**Therefore: no per-tool figure from a single grading pass may be published.** That applies to
precision exactly as much as to thread recall. Options 1-3 below still stand, but they now govern
both axes.

A second consequence: the corpus-level numbers were far steadier than the per-tool ones — human
threads hit by any tool moved 8->7 on prometheus and 7->6 on efcore, and the missed-by-everyone set
grew by exactly one thread on each. Aggregate statements about what the field as a whole misses are
the most defensible output this instrument produces; per-tool rankings are the least.
