---
# dcc-vi86
version: 1
title: 'auto-deliver: lap-limited mode so an outer loop can restart it fresh per phase'
status: draft
type: feature
priority: normal
estimate: l
created_at: 2026-09-24T17:03:06Z
updated_at: 2026-09-24T17:03:11Z
parent: dcc-fq6j
blocked_by:
    - dcc-qdxo
order: ay
---

## Description

auto-deliver runs every phase in one growing context: breakdown, batch-dev, review triage and close-out for phase after phase. `state.json` plus the tracker already make a restart safe, but nothing ever restarts it, and continuing to the next phase depends on the wording of invariant 1. Commit aae57af (#dcc-d76g) shows that "lap death" at a phase boundary is a real failure.

Add a lap-limited mode (for example `--laps N`) that exits cleanly after MERGE with `state.json` back at SELECT. An outer driver can then relaunch a fresh process per phase: a bash loop over `claude -p "/decaf-build:auto-deliver <plan> --laps 1"` with `--max-turns` and `--max-budget-usd`, a scheduled routine, or `/goal`. This is the hybrid the research recommends: an outer loop picks one bounded unit, a fresh-context worker does it, deterministic gates check it. It also answers lap death mechanically, since the outer loop owns continuation.

Blocked by #dcc-qdxo (unattended auto-code-review), because a `-p` run cannot answer `AskUserQuestion`.

## Open questions

- How does the outer driver tell "lap done", "plan complete" and "escalated" apart: distinct exit wording, or a `state.json` field it reads?
- How does a lap limit sit with invariant 1 ("no gate-stops")? It should read as an operator-chosen bound, not a gate the loop invents.
- What does `-p` withhold that batch-dev relies on? A Workflow cluster needs a `Workflow` allow rule, and agent teams do not form in `-p`.
- Ship a reference driver script in the decaf-build README?
