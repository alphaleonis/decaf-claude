---
# dcc-envo
version: 1
title: 'Restructure METHODOLOGY-v2: demote the checkpoint machinery'
status: todo
type: task
priority: normal
created_at: 2026-08-10T17:43:28Z
updated_at: 2026-08-10T19:59:48Z
parent: dcc-ho2w
order: 8s
---

The document still presents the review checkpoint as v2's organizing idea. Three subjects built end
to end say otherwise: **the checkpoint choice changed the answer in 1 of 3**, and in that one only
because the merged head turned out unscorable.

| | Subject 9 | Subject 11 | Subject 2 |
|---|---|---|---|
| What review did to the defect | introduced it | removed it | transformed it |
| Better checkpoint | merged head | as-opened | final head (= merged) |

What actually earned its keep is the leak-proofing and the key-building discipline, which caught
three invalid ground truths before any of them cost a review cell.

## Changes

- Lead with the leak controls and the key-building procedure; the checkpoint becomes a tool used when
  the defect's location demands it, not the frame
- Fold in the scoring-model decision, replacing the key-only framing
- Correct the stale example: the claim that mechanical filters drop the `topology.go` and
  `hollow_proxy.go` threads is true of the as-opened checkpoint and FALSE at push #2, where the file
  filter rejected 0 of 46
- Record the four procedure bugs found by execution as standing warnings (re-shallowing fetch, weak
  mechanical filters, force-pushes not enumerating heads, full-revert giving no localization)

## Acceptance

- [ ] Checkpoint section reframed as conditional, with the 1-of-3 evidence stated
- [ ] No stale examples or superseded framing remain
