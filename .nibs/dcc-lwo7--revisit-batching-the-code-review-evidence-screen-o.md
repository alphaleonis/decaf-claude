---
# dcc-lwo7
version: 1
title: Revisit batching the code-review evidence screen once spend is measured
status: draft
type: research
tags:
    - code-review
created_at: 2026-11-03T15:24:35Z
updated_at: 2026-11-03T16:39:02Z
parent: dcc-b578
blocked_by:
    - dcc-k163
order: ay
---

Revisit whether the code-review evidence screen should run one screener per report instead of one per cluster, once real per-agent spend is recorded. Recommendation 7 of the dcc-s612 corpus analysis, deferred by operator decision 2026-11-03.

## Why it waits

- On final-request token figures the screen is 27% of report-side tokens; on the turn-weighted estimate it is 9.3%. Screeners make few calls on a large base context, so the final-request figure overstates them. Which number holds decides whether batching is worth it.
- The screen held 345 of 438 scored clusters below the bar, so a change to how it scores moves findings a lot.
- The `code-review` `bugs` section records, from the v2 benchmark, that a strict screen tiered real defects into Minor; batching could shift scoring the same way.

## Open questions

- Measured screen share of review-side spend, from the Spend tables dcc-k163 adds to `--report` reports.
- How to test that a batched screener scores clusters the same as per-cluster screeners (same clusters, both ways, compare scores) before any default changes.
