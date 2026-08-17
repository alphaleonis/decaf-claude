---
# dcc-pulk
version: 1
title: 'bugs-sp: attribute the cost gap and decide the Minor-bucket / fail-closed questions'
status: todo
type: task
priority: normal
created_at: 2026-08-17T08:09:33Z
updated_at: 2026-08-17T08:09:33Z
parent: dcc-hyxw
order: ax
---

Follow-up from the `bugs-sp` experiment (`v2/analysis/BUGS-SP-RESULTS.md`, [[dcc-1sbc]]). The
single seat found 10 of 16 pool defects (more than superpowers' 9) but reported 6, cost $5.13/cell
against superpowers' $4.30, and its reported set was 44% defect-class (70% on primary findings). Two
concrete mechanisms are unattributed and each is a bounded piece of work:

## 1. Where do the extra Opus output tokens go?

`bugs-sp` produced 62–71k Opus output per cell against superpowers' 38–55k on the same subjects,
for fewer reported findings. Candidates: the per-finding table format (Evidence field, Verified tag,
tables) vs superpowers' four bullet lines; the orchestrator's Step 6 assembly turn(s); the seat's
inline verification being more expensive than superpowers' (it built base+head worktrees in both
efcore cells). Attribute against the four cell transcripts (`v2/runs/*ours-bugs-sp*`) — the seat's
subagent usage is in the transcript separately from the orchestrator's — before changing anything.

## 2. The Minor bucket leaks under `reach=narrow`

Composition drift is almost entirely the Minor bucket (8 of 18 reported clusters: 4 design, 2 docs,
1 risk, 1 defect) — one-liners the `bugs` funnel would have routed to Considered But Not Flagged.
Decide whether `bugs-sp` under `narrow` should emit the Minor bucket at all (the deliverable is
"high-confidence defects introduced by the changed lines"), or only its Consistency sub-bucket, and
whether the brief's "tautological test = defect" rule should stay (the judge classes those
test-gap; 3 of the 10 primary clusters).

## 3. Three defects the seat argued away

prom c05, c07 and efcore e13 were found and parked with a stated reason each ("deliberate and
documented", "design choice", "unreachable today"); the human reviewer and judge disagreed on all
three. Whether the brief should bias toward reporting a traced-but-dismissed defect (fail closed) is
a calibration decision — note superpowers' agent reached the same conclusion on e13.

## Acceptance

- [ ] Token attribution for the four cells: seat vs orchestrator, and within the seat verification
      vs report writing (from transcripts, not `modelUsage`)
- [ ] Decision recorded on the Minor bucket under `bugs-sp reach=narrow`, with the brief/SKILL edited
      if it changes
- [ ] Decision recorded on the fail-closed question, with the brief edited if it changes
- [ ] If any brief/SKILL change lands: re-run the 2×2 (operator-gated) and re-fold; do not compare a
      changed brief against these cells without saying so
