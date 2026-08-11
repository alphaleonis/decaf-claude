---
# dcc-2gu2
version: 1
title: Re-screen replacement candidates under a human-thread density criterion
status: todo
type: task
priority: high
created_at: 2026-08-11T11:40:14Z
updated_at: 2026-08-11T11:40:14Z
parent: dcc-ho2w
blocked_by:
    - dcc-qwt3
order: 8i
---

The corpus's density criterion — **>=5 review threads** — counted threads without checking who wrote
them. The census ([[dcc-qwt3]], `v2/analysis/THREAD-AXIS.md`) showed what that admitted:
`element-web#32964` passed the bar with 4 of 5 threads written by bots; `grafana#117615` with 5 of 7;
`sveltejs/kit#15685` with 2 of 3. The criterion measured comment volume, and comment volume is now
substantially a property of which bots a repo has installed.

Before any replacement subject is searched for, the selection machinery has to count **human**
threads — and then the feasibility claim has to be re-verified under it. [[dcc-vvf0]]'s post-cutoff
candidate counts (grafana 98, mattermost 67, immich 20, element-web 19, jellyfin 6) predate the
human-thread criterion and are superseded, not carried over. Standing rule: verify claims about the
corpus; don't assert them.

## Changes to `find_candidates.sh`

- Screen on **human** thread count, filtering thread authors against the explicit bot list
  [[dcc-qwt3]] commits (a name regex does not work — none of the nine logins matches
  `(?i)bot$|\[bot\]`)
- Report per candidate: raw thread count, human thread count, bot share, and **distinct human
  reviewer count**
- Soft criterion: prefer >=2 distinct human reviewers. The census found one reviewer (`haacked`)
  supplies 36% of all human threads and 66% of all human defect statements — a single point of
  failure the axis should not repeat
- Repo-culture prior, measured not assumed: prometheus (10/10 human), efcore (10/11), immich (8/8,
  2/2), jellyfin (8/8) and mattermost (4/6) demonstrated human review culture; PostHog, element-web,
  grafana#117615's repo area and sveltejs are bot-saturated. Prefer the former; screen the latter by
  their measured bot share

## The nine target cells

| Cell | Current subject | Problem |
|---|---|---|
| backend S | jellyfin#12834 | in-window (2026-05-21) |
| backend M | grafana#124181 | in-window (2026-05-08) |
| backend L | PostHog#52408 | in-window (2026-05-06) |
| contract L | PostHog#55149 | in-window (2026-05-06) |
| app-ui M | immich#24627 | in-window (2026-05-11) |
| contract S | immich#28886 | citable but 2 human threads |
| app-ui S | grafana#117615 | citable but 2 human threads |
| app-ui L | element-web#32964 | citable but 1 human thread |
| library S | sveltejs#15685 | citable but 1 human thread |

Run the screen for all nine. A cell with no viable candidate is a **recorded result with the query
shown** — "no candidates" and "the query failed" must be distinguishable (the standing
silent-failure rule; the script already exits 4 on a failed query).

## Acceptance

- [ ] `find_candidates.sh` screens on human threads against the committed bot list; raw count, human
      count, bot share and distinct-human-reviewer count all in its output
- [ ] Screen run for all nine cells; per-cell result recorded in `CANDIDATES.md` — a candidate list,
      or an explicit none-found with the query
- [ ] [[dcc-vvf0]]'s candidate counts marked superseded by the new per-cell numbers
- [ ] A recommendation per cell: replace with X / no viable candidate / keep as-is
