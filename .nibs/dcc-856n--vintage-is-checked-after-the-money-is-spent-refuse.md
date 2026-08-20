---
# dcc-856n
version: 1
title: 'Vintage is checked after the money is spent: refuse an in-window subject at selection time'
status: todo
type: bug
created_at: 2026-08-20T18:35:48Z
updated_at: 2026-08-20T18:36:20Z
parent: dcc-ho2w
order: zzzV
---

`vintage.py` runs inside `score_pooled.py`, at ANALYSIS time. Nothing at subject-selection time
refuses or warns about an in-window subject.

## What it cost

[[dcc-fm7x]] selected `PostHog/posthog#55149` explicitly to be the **third poolable subject** for two
withheld conclusions (`reach=norm`, `review` vs `bugs`), and recorded "the subject is out-of-window"
among its satisfied prerequisites. It is in-window: merged 2026-05-06 against `claude-opus-5`'s
month-granular 2026-05 cutoff, so provably clean only from 2026-06-01. **$203.54** was spent before
anything said so.

The per-subject readout is real and worth having. The cross-subject unlock the spend was authorized
for is not obtainable from this subject, and never was.

## Why it was missable

- `fixture.json` carries a `vintage` dict, but it holds only `{merged, note}` — the note says "status
  is computed per model at analysis time", so the field looks answered while carrying no verdict.
- `audit_subject.sh` and the candidate screening do not surface it.
- The nib asserted the status in prose instead of deriving it, which the project's own ground rule
  warns about: verify claims about the corpus, do not assert them.

## Fix

- `vintage.describe()` at fixture-build and at cell-run time: `run_cell_v2.sh` should print the status
  per cell, and refuse without an explicit override when a subject is in-window and the stated purpose
  is a pooled comparison.
- `bench-status` should list in-window subjects as a standing warning, not only inside metrics.
- Selection tooling should state, per candidate, the earliest model cutoff that makes it poolable.

## Acceptance

- [ ] `run_cell_v2.sh` prints vintage status and refuses an in-window subject without an override
- [ ] `bench-status` shows which scored subjects may not be pooled
- [ ] `fixture.json`'s `vintage` block carries a computed status per known model, not just `merged`
- [ ] The five in-window pooled subjects are listed somewhere a person planning a run will see
