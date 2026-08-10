---
# dcc-plsq
version: 1
title: Full v2 bench-run
status: todo
type: task
priority: normal
created_at: 2026-08-10T17:43:28Z
updated_at: 2026-08-10T18:42:12Z
parent: dcc-ho2w
blocked_by:
    - dcc-vkeh
    - dcc-5xad
    - dcc-ixyy
order: Hz
---

The terminal item. Do not start until every sibling is complete — in particular the ground-truth
audit ([[dcc-5xad]]), the scoring pipeline, and the pilot.

Blocked by construction: a scoring pipeline run over unaudited ground truth is worse than useless,
because it produces confident numbers graded against defects that may not be in the reviewed diff.
Two of the first three subjects examined had exactly that problem.

## Preconditions

- [ ] All subjects audited, with failures replaced rather than repaired
- [ ] Scoring pipeline reproduces hand-graded results
- [ ] Pilot shows the roster separates
- [ ] Leak audit clean on a sample of cells before authorising the rest
- [ ] Cost estimated from pilot cell costs and agreed in advance

## Acceptance

- [ ] Full roster x audited corpus x repeats
- [ ] Per-cell leak audit recorded
- [ ] Synthesis published with the caveats that survive: memorization exposure per subject, build
      availability per cell, and reported-vs-found recall
