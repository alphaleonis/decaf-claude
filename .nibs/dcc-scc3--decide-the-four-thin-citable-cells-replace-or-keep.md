---
# dcc-scc3
version: 1
title: 'Decide the four thin citable cells: replace or keep-thin, recorded'
status: todo
type: task
priority: normal
created_at: 2026-08-11T11:40:30Z
updated_at: 2026-08-11T11:40:30Z
parent: dcc-ho2w
blocked_by:
    - dcc-2gu2
order: 8q
---

Four citable cells are too thin to carry a per-cell miss-detector number: **app-ui L**
(element-web#32964, 1 human thread), **library S** (sveltejs#15685, 1), **app-ui S**
(grafana#117615, 2), **contract S** (immich#28886, 2). All four passed the density criterion on bot
volume ([[dcc-qwt3]]).

These cells still work for the **ranking instrument** — pooled adjudication needs no threads — so
replacement is opportunistic, not mandatory. What IS mandatory is deciding before [[dcc-plsq]]
spends: a subject replaced after the full run means paying for its cells twice.

Replace a cell only where the [[dcc-2gu2]] screen found a same-cell candidate with >=5 human threads from
>=2 reviewers. **Keep-thin is a valid outcome** — the cell ranks and calibrates against the null
arm; it just contributes nothing to thread recall — and it is recorded with its reason, not left
implicit.

## Acceptance

- [ ] Each of the four cells has a recorded decision: replaced (built per §4c/§4b, human-thread
      criterion at admission) or kept-thin with the reason
- [ ] No replacement admitted that fails the human-thread criterion
- [ ] The "What survives" table in `THREAD-AXIS.md` updated to the post-decision corpus
