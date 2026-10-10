---
# dcc-x8ad
version: 1
title: 'resolve-architecture-review: batch mode — triage all, explore in waves, then review'
status: completed
type: feature
estimate: m
created_at: 2026-10-10T15:38:57Z
updated_at: 2026-10-10T15:40:51Z
order: zzzzzzw
---

Interactive mode makes the operator wait on each Explore: the design agents run while the operator sits idle, once per candidate. Add a `batch` mode that front-loads every decision that doesn't depend on a design, runs the explorations together, and then walks the results.

## Design

1. **Triage** — compact table of all candidates; one AskUserQuestion question per candidate (Explore / Skip / Dismiss / Defer, 4 per call). Dismiss/Defer handled immediately. Output target (5g) asked once.
2. **Framing gate** — 5d framings for all Explore candidates shown together; one stop to object/reframe/drop.
3. **Exploration wave** — stale-file check, then design agents per candidate, capped at a few candidates concurrently. Designs and the comparison/recommendation are written to `.decaf/architecture-improvements/explorations/<N>/`; only short summaries return to the orchestrator.
4. **Review** — explored candidates one at a time, read from disk: pick → RFC draft → create (today's 5f–5h).

State file gains `mode` and per-candidate `phase` (`triaged` → `framed` → `explored` → `resolved`) plus the exploration dir; resume keys off which artifacts exist.

Named `batch`, not `auto`: in sibling resolve-* skills `auto` means the agent decides; here the operator still makes every decision.

## Todo

- [x] Split Critical Behavior Requirements into Interactive / Batch / Both
- [x] Argument parsing + argument-hint for `batch`
- [x] State file: mode, phase, exploration dir; resume rules
- [x] Batch steps: triage, framing gate, wave, review
- [x] Update frontmatter description, CLAUDE.md table, README section

## Summary

**Completed 2026-10-10** — Added `batch` mode to resolve-architecture-review: B1 triage (4 candidates per AskUserQuestion call, output target asked once), B2 a single framing gate (stale-file check happens here), B3 the exploration wave with no stops (up to 3 candidates at a time, design and comparison sub-agents write to `.decaf/architecture-improvements/explorations/<stem>/<N>/`), and B4 a one-at-a-time review → RFC. The state file gained `mode`, `outputTarget` and `batch` (per-candidate phase + dir); resume treats an existing `comparison.md` as explored. Interactive mode is unchanged. README, CLAUDE.md, artifacts.md and architecture-review's output notification were updated.
