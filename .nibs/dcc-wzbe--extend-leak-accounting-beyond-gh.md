---
# dcc-wzbe
version: 1
title: Extend leak accounting beyond gh
status: todo
type: task
priority: normal
created_at: 2026-08-10T17:43:02Z
updated_at: 2026-08-10T17:43:41Z
parent: dcc-ho2w
order: Zk
---

`v2/shim-log/gh` makes `gh` measurable in the control arm, but it is a `gh` accounting instrument,
not a general leak detector. Channels currently unmeasured:

- **WebFetch / WebSearch** — disallowed in both arms today, so covered by denial rather than
  measurement. If a future arm allows them, there is no log.
- **`docs-at`** — logs its own calls, but nothing verifies the Wayback snapshot actually predates the
  checkpoint. A page can be archived later than requested and served anyway; the returned snapshot
  date is printed but not enforced.
- **MCP servers** (context7 etc.) — serve current docs with no date parameter. Denied by default, but
  nothing detects one being connected.
- **Raw network from bash** — `curl`, `wget`, a language package manager. Nothing stops or logs it.
- **Training-data memorization** — unfalsifiable by construction. Not fixable here; bounded only by
  subject vintage.

Note the reason this matters: output-grepping was shown to UNDERCOUNT leaks — a cell read two
post-checkpoint comments and cited none of them, so it scored clean. Any channel without its own log
has the same blind spot.

## Acceptance

- [ ] Each channel is either logged, denied at the harness level, or explicitly documented as
      unmeasured
- [ ] `docs-at` verifies and enforces the returned snapshot date rather than only printing it
- [ ] The leak audit reports which channels were instrumented for that run
