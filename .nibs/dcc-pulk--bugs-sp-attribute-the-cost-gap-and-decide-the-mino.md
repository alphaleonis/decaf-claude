---
# dcc-pulk
version: 1
title: 'bugs-sp: attribute the cost gap and decide the Minor-bucket / fail-closed questions'
status: completed
type: task
priority: normal
created_at: 2026-08-17T08:09:33Z
updated_at: 2026-08-17T10:10:52Z
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

- [x] Token attribution for the four cells: seat vs orchestrator — done 2026-08-17, recorded in
      `v2/analysis/BUGS-SP-RESULTS.md` § Cost attribution. Input side exact per lane (cache-read
      reconciles to the meter in all 8 cells); output only as a meter total (per-request
      `output_tokens` is 19–35% of the meter, non-uniform). Result: the seat costs the same as
      superpowers' agent on every measurable axis; the whole $0.84 gap is the orchestrator —
      ~35k-token SKILL.md re-read across ~10 turns, and the report emitted twice. Within-seat
      verification-vs-writing split not measurable (thinking redacted; visible emissions: ~60%
      shell inputs / ~40% report text)
- [x] Decision (operator, 2026-08-17): Minor bucket **omitted** under `bugs-sp reach=narrow` — minor
      items parked as `minor, out of reach`; tautological-test-is-defect rule kept. Brief + SKILL edited
- [x] Decision (operator, 2026-08-17): **fail closed** — a defect traced to real code behavior and
      dismissed as "documented as intended" / "unreachable today" is reported at anchor 50 with the
      counter-argument. Brief edited. Orchestrator left as is (backbone kept; cost criterion restated
      in PROPOSAL-BUGS-SP.md)
- [x] Re-run the 2×2 under the new arm `ours-bugs-sp2` (brief v2) and fold in — done 2026-08-17,
      `v2/analysis/BUGS-SP-RESULTS.md` § Brief v2. Result: not an improvement on recall (5/16
      reported vs v1 6; found 9 vs 10), composition 44%→62%, stability better (0.50/0.50), seat
      cost up $1.20 (55 turns vs 36; superpowers parity lost). Fail-closed fired on e13, under-fired
      on c07; the `minor, out of reach` label swallowed a Low (c03); e02/c05 movements are seat
      variance. Two repeats cannot separate brief effect from seat variance at this size

## Summary

**Completed 2026-08-17** — All three parts done. (1) Cost attribution: the seat costs what superpowers' agent costs; the
whole v1 gap ($0.84/cell) is the shared orchestrator backbone (~35k-token SKILL load re-read over
~10 turns; report emitted twice) — kept by operator decision, cost criterion restated. (2) Minor
bucket omitted under narrow; (3) fail closed on traced-and-dismissed defects — both applied as
brief v2 and re-measured under arm `ours-bugs-sp2` (4 cells, CLEAN). Brief v2 is not an
improvement on recall (5/16 reported vs 6; found 9 vs 10), improves composition (44%→62%) and
repeat stability (0.50/0.50), costs $1.23/cell more (all seat: 55 turns vs 36) and loses seat
parity with superpowers. Cluster-level: fail-closed fired on efcore e13 and under-fired on prom
c07; `minor, out of reach` swallowed a Low (c03); e02/c05 moved on seat variance. Two repeats do
not separate a brief effect of this size from single-seat variance. Both briefs' cells stay in the
matrix (`ours-bugs-sp` = v1, `ours-bugs-sp2` = v2). Fold-in prompts and script preserved under
`v2/scoring/prompts/` and `v2/scoring/foldin.py`; efcore calibration gap (3/12) recorded there.
Sharpened-rule candidates recorded in BUGS-SP-RESULTS.md; not re-run.
