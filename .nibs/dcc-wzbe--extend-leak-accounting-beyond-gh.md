---
# dcc-wzbe
version: 1
title: Extend leak accounting beyond gh
status: completed
type: task
priority: normal
created_at: 2026-08-10T17:43:02Z
updated_at: 2026-08-10T21:15:01Z
parent: dcc-ho2w
order: "8"
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
## Acceptance

- [x] **Each channel is either logged, denied at the harness level, or explicitly documented as
      unmeasured** — full matrix in METHODOLOGY-v2 Tier 3 and printed per cell by
      `v2/leak_audit.sh`. `curl`/`wget` are now shimmed (GitHub denied, rest logged); MCP is denied
      via `--strict-mcp-config`; memorization and non-curl HTTP clients are named as unmeasured
      rather than omitted.
- [x] **`docs-at` verifies and enforces the returned snapshot date** — it now bounds the query
      through the Wayback CDX index (`to=<stamp>&limit=-1`) to take the most recent capture at or
      before the checkpoint, and still refuses if a later snapshot arrives. Both paths tested: a
      2026-05-01 checkpoint serves a 2026-03-02 capture; a 2015-01-01 checkpoint correctly finds none.
- [x] **The leak audit reports which channels were instrumented** — `v2/leak_audit.sh <cell-dir>`,
      verified against a real treatment cell (2 denials listed) and a real control cell (no denials;
      the would-have-denied call listed separately).

## Summary

**Completed 2026-08-10** — Three live holes, all found by testing rather than reasoning about the design.

**`curl` bypassed the entire `gh` shim.** `curl https://api.github.com/repos/O/R/pulls/N/comments`
returns exactly the review threads the shim exists to withhold — and those threads are now a *scored
target*, so this was a hole in scoring, not just hygiene. Cells need real network for package restore
([[dcc-fhp1]]), so `curl`/`wget` are shimmed to deny GitHub hosts and log everything else, rather
than denied outright.

**`docs-at` printed its pin without enforcing it.** Wayback's `/web/<stamp>/` returns the *closest*
snapshot, usually a later one: a request for 2015 returned a 2021 capture, and 2026-05-01 returned
2026-05-21. Enforcing the date naively made it refuse almost everything, so it now bounds the query
through the CDX index and takes the most recent capture at or before the checkpoint — with the
redirect check kept as a second line of defence.

**MCP servers were inherited by every cell.** This machine has `context7` (current library docs),
`playwright` (a full browser, so any URL including the PR page) and `erinra` (a memory store, i.e. a
cross-cell contamination path) connected. Verified by invocation rather than by asking the model:
without `--strict-mcp-config` the tool exists and is stopped only by a *permission* prompt, so a
permissive `PERM_FLAGS` would have let it through; with the flag the tool does not exist at all.

`v2/leak_audit.sh` prints per-cell coverage including the unmeasured rows — memorization, and HTTP
clients other than curl/wget — because a leak audit that omitted them would claim more coverage than
it has.

Note for [[dcc-3cm6]]: writing this reporter reproduced the harness's recurring bug a **fifth** time.
`grep -c` prints `0` AND exits 1, so `|| echo 0` appended a second zero and every count rendered as
"0\n0"; separately, `grep DENY` matched the control arm's `would=[DENY ...]` annotation and listed a
PASS as a denial. Both are the empty-versus-failed confusion. The review should treat it as a class
to sweep, not five incidents.
