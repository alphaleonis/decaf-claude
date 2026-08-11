---
# dcc-ryo4
version: 1
title: 'Replace the in-window five: the backend row and 56 of 86 human threads are locked behind vintage'
status: todo
type: task
priority: high
created_at: 2026-08-11T11:40:22Z
updated_at: 2026-08-11T11:40:22Z
parent: dcc-ho2w
blocked_by:
    - dcc-2gu2
order: 8o
---

[[dcc-vvf0]] chose keep-and-flag for the five subjects merged inside May 2026, to preserve their
audited thread sets at the price of a permanently unreportable `backend` row. **The census
([[dcc-qwt3]]) changed that trade after the fact**: the in-window five hold **56 of the corpus's 86
human threads**, while the seven citable subjects hold **30** — concentrated in two cells, with four
cells at <=2. Most of the miss detector is locked behind the vintage flag.

So replacement now buys two things where it previously bought one: a citable backend row, **and**
human-thread coverage the citable set demonstrably lacks. The keep decision predates this data and
is superseded by it.

## The five

| Cell | Subject | merged | Human threads |
|---|---|---|---|
| backend S | jellyfin#12834 | 2026-05-21 | 8 of 8 |
| backend M | grafana#124181 | 2026-05-08 | 5 of 6 |
| backend L | PostHog#52408 | 2026-05-06 | 15 of 19 |
| contract L | PostHog#55149 | 2026-05-06 | 20 of 35 |
| app-ui M | immich#24627 | 2026-05-11 | 8 of 8 |

Replacements come from the [[dcc-2gu2]] screen candidate list, built per METHODOLOGY-v2 §4c + the §4b
spine: merged >=2026-06-01, >=5 **human** threads, per-thread admission with bot threads segregated
into the second axis ([[dcc-qwt3]]), airtightness verified per build.

**Retire, don't delete.** The five become probe material — §5's retirement policy: matched vintage
pairs measure memorization effect size, and same-repo pairs (jellyfin→jellyfin, grafana→grafana...)
are exactly the matched pairs it calls for. Mark each retired fixture's status; their audited thread
sets stay with them.

## Acceptance

- [ ] 5 replacement subjects built and airtight per §4b, each merged >=2026-06-01 with >=5 human
      threads at admission
- [ ] The backend row is citable: `vintage.check_pooling()` passes on a backend figure
- [ ] The five retired fixtures marked as probe material (role recorded in the fixture), not deleted
- [ ] `CANDIDATES.md` grid updated; the 218-raw/120-admitted corpus figures superseded where cited
- [ ] Matched vintage pairs recorded where the replacement is same-repo, so the memorization probe
      becomes runnable
