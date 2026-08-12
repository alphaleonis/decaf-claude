---
# dcc-di47
version: 1
title: Thread recall needs an uncertainty band, not a point estimate
status: todo
type: task
priority: high
created_at: 2026-08-12T07:12:02Z
updated_at: 2026-08-12T07:12:26Z
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
